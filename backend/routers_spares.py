"""Spares & Inventory: SAP-centric master, transaction ledger, CSV import (preview+apply),
consumption from BD/WO/PM, machine-spare recommendations, analytics."""
import csv
import io
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user, require_admin, require_admin_or_tech
from database import db
from events import create_timeline_event, now_iso

router = APIRouter()


# ---------- Transaction ledger core (inventory never modified directly) ----------
async def record_transaction(sap_code: str, qty_change: float, tx_type: str, reference_id: str = None,
                             reference_label: str = None, machine_id: str = None, machine_name: str = None,
                             performed_by: str = 'system', old_qty: float = None, new_qty: float = None, notes: str = None):
    tx = {
        'id': str(uuid.uuid4()), 'sap_code': sap_code, 'quantity_change': qty_change,
        'transaction_type': tx_type, 'reference_id': reference_id, 'reference_label': reference_label,
        'machine_id': machine_id, 'machine_name': machine_name,
        'old_quantity': old_qty, 'new_quantity': new_qty,
        'performed_by': performed_by, 'notes': notes, 'created_at': now_iso(),
    }
    await db.spare_transactions.insert_one(dict(tx))
    tx.pop('_id', None)
    return tx


async def consume_spares(spares: list, tx_type: str, reference_id: str, reference_label: str,
                         machine_id: str, machine_name: str, username: str):
    """Subtract inventory, create transactions, link to source. Returns enriched consumption list."""
    enriched = []
    for s in spares:
        sap = str(s['sap_code'])
        qty = float(s['quantity'])
        if qty <= 0:
            continue
        item = await db.spares_inventory.find_one({'sap_code': sap}, {'_id': 0})
        if not item:
            raise HTTPException(status_code=400, detail=f'Unknown SAP code: {sap}')
        old_q = float(item.get('quantity', 0))
        if qty > old_q:
            raise HTTPException(status_code=400, detail=f'Insufficient stock for {sap} ({item["material_name"]}): have {old_q}, need {qty}')
        new_q = round(old_q - qty, 3)
        await db.spares_inventory.update_one({'sap_code': sap}, {'$set': {'quantity': new_q, 'updated_at': now_iso()}, '$inc': {'total_consumed': qty}})
        await record_transaction(sap, -qty, tx_type, reference_id, reference_label, machine_id, machine_name, username, old_q, new_q)
        enriched.append({'sap_code': sap, 'material_name': item['material_name'], 'quantity': qty, 'uom': item.get('uom')})
    return enriched


# ---------- Spare master ----------
class SpareCreate(BaseModel):
    sap_code: str
    material_name: str
    long_text: Optional[str] = None
    location: Optional[str] = None
    quantity: float = 0
    uom: str = 'EA'
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    vendor: Optional[str] = None


@router.post('/spares')
async def create_spare(req: SpareCreate, user: dict = Depends(require_admin)):
    if await db.spares_inventory.find_one({'sap_code': req.sap_code}):
        raise HTTPException(status_code=400, detail=f'SAP code {req.sap_code} already exists')
    item = {**req.model_dump(), 'id': str(uuid.uuid4()), 'active': True, 'total_consumed': 0,
            'created_at': now_iso(), 'updated_at': now_iso()}
    await db.spares_inventory.insert_one(dict(item))
    if req.quantity > 0:
        await record_transaction(req.sap_code, req.quantity, 'STOCK_ADDITION', None, 'Initial stock', None, None, user['username'], 0, req.quantity)
    item.pop('_id', None)
    return item


@router.get('/spares')
async def list_spares(search: Optional[str] = None, location: Optional[str] = None, category: Optional[str] = None,
                      stock: Optional[str] = None, limit: int = Query(500, le=5000), skip: int = 0,
                      user: dict = Depends(require_admin_or_tech)):
    q = {}
    if search:
        q['$or'] = [{'sap_code': {'$regex': search, '$options': 'i'}}, {'material_name': {'$regex': search, '$options': 'i'}},
                    {'long_text': {'$regex': search, '$options': 'i'}}, {'location': {'$regex': search, '$options': 'i'}}]
    if location:
        q['location'] = location
    if category:
        q['category'] = category
    if stock == 'in':
        q['quantity'] = {'$gt': 0}
    elif stock == 'out':
        q['quantity'] = {'$lte': 0}
    total = await db.spares_inventory.count_documents(q)
    items = await db.spares_inventory.find(q, {'_id': 0}).sort('material_name', 1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': total}


class SpareUpdate(BaseModel):
    material_name: Optional[str] = None
    long_text: Optional[str] = None
    location: Optional[str] = None
    uom: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    vendor: Optional[str] = None
    active: Optional[bool] = None


@router.put('/spares/{sap_code}')
async def update_spare(sap_code: str, req: SpareUpdate, user: dict = Depends(require_admin)):
    item = await db.spares_inventory.find_one({'sap_code': sap_code}, {'_id': 0})
    if not item:
        raise HTTPException(status_code=404, detail='Spare not found')
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        updates['updated_at'] = now_iso()
        await db.spares_inventory.update_one({'sap_code': sap_code}, {'$set': updates})
        changed = ', '.join(f'{k}: {item.get(k)} \u2192 {v}' for k, v in updates.items() if k != 'updated_at')
        await record_transaction(sap_code, 0, 'MANUAL_ADJUSTMENT', None, 'Material info update', None, None,
                                 user['username'], item.get('quantity'), item.get('quantity'), notes=changed)
    return await db.spares_inventory.find_one({'sap_code': sap_code}, {'_id': 0})


class StockAdjust(BaseModel):
    quantity_change: float
    notes: Optional[str] = None


@router.post('/spares/{sap_code}/adjust')
async def adjust_stock(sap_code: str, req: StockAdjust, user: dict = Depends(require_admin)):
    item = await db.spares_inventory.find_one({'sap_code': sap_code}, {'_id': 0})
    if not item:
        raise HTTPException(status_code=404, detail='Spare not found')
    old_q = float(item.get('quantity', 0))
    new_q = round(old_q + req.quantity_change, 3)
    if new_q < 0:
        raise HTTPException(status_code=400, detail=f'Adjustment would make quantity negative ({new_q})')
    await db.spares_inventory.update_one({'sap_code': sap_code}, {'$set': {'quantity': new_q, 'updated_at': now_iso()}})
    tx_type = 'STOCK_ADDITION' if req.quantity_change > 0 else 'STOCK_REDUCTION'
    await record_transaction(sap_code, req.quantity_change, tx_type, None, 'Manual adjustment', None, None,
                             user['username'], old_q, new_q, notes=req.notes)
    return {'ok': True, 'old_quantity': old_q, 'new_quantity': new_q}


# ---------- Transactions ----------
@router.get('/spare-transactions')
async def list_transactions(sap_code: Optional[str] = None, machine_id: Optional[str] = None,
                            transaction_type: Optional[str] = None, limit: int = Query(200, le=2000), skip: int = 0,
                            user: dict = Depends(require_admin_or_tech)):
    q = {}
    if sap_code:
        q['sap_code'] = sap_code
    if machine_id:
        q['machine_id'] = machine_id
    if transaction_type:
        q['transaction_type'] = transaction_type
    total = await db.spare_transactions.count_documents(q)
    items = await db.spare_transactions.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': total}


# ---------- Dashboard + analytics ----------
@router.get('/spares/dashboard')
async def spares_dashboard(user: dict = Depends(require_admin_or_tech)):
    total_materials = await db.spares_inventory.count_documents({})
    agg = await db.spares_inventory.aggregate([{'$group': {'_id': None, 'qty': {'$sum': '$quantity'}}}]).to_list(1)
    total_qty = round(agg[0]['qty'], 1) if agg else 0
    in_stock = await db.spares_inventory.count_documents({'quantity': {'$gt': 0}})
    out_stock = await db.spares_inventory.count_documents({'quantity': {'$lte': 0}})
    recent_tx = await db.spare_transactions.find({}, {'_id': 0}).sort('created_at', -1).limit(15).to_list(15)
    recently_used = await db.spare_transactions.aggregate([
        {'$match': {'quantity_change': {'$lt': 0}}}, {'$sort': {'created_at': -1}}, {'$limit': 50},
        {'$group': {'_id': '$sap_code', 'last_used': {'$first': '$created_at'}, 'qty': {'$sum': {'$abs': '$quantity_change'}}}},
        {'$sort': {'last_used': -1}}, {'$limit': 10},
    ]).to_list(10)
    most_used = await db.spare_transactions.aggregate([
        {'$match': {'quantity_change': {'$lt': 0}, 'transaction_type': {'$in': ['BREAKDOWN_CONSUMPTION', 'WORKORDER_CONSUMPTION', 'PM_CONSUMPTION']}}},
        {'$group': {'_id': '$sap_code', 'total_consumed': {'$sum': {'$abs': '$quantity_change'}}, 'tx_count': {'$sum': 1}}},
        {'$sort': {'total_consumed': -1}}, {'$limit': 10},
    ]).to_list(10)
    # enrich names
    saps = list({r['_id'] for r in recently_used} | {r['_id'] for r in most_used})
    names = {s['sap_code']: s['material_name'] for s in await db.spares_inventory.find({'sap_code': {'$in': saps}}, {'_id': 0}).to_list(1000)}
    for r in recently_used:
        r['sap_code'] = r.pop('_id')
        r['material_name'] = names.get(r['sap_code'], '')
    for r in most_used:
        r['sap_code'] = r.pop('_id')
        r['material_name'] = names.get(r['sap_code'], '')
    top_machines = await db.spare_transactions.aggregate([
        {'$match': {'quantity_change': {'$lt': 0}, 'machine_name': {'$ne': None}}},
        {'$group': {'_id': '$machine_name', 'total_consumed': {'$sum': {'$abs': '$quantity_change'}}}},
        {'$sort': {'total_consumed': -1}}, {'$limit': 10},
    ]).to_list(10)
    return {'total_materials': total_materials, 'total_quantity': total_qty, 'in_stock': in_stock, 'out_of_stock': out_stock,
            'recent_transactions': recent_tx, 'recently_used': recently_used, 'most_used': most_used,
            'top_machines': [{'machine_name': t['_id'], 'total_consumed': t['total_consumed']} for t in top_machines]}


@router.get('/spares/{sap_code}/analytics')
async def spare_analytics(sap_code: str, user: dict = Depends(require_admin_or_tech)):
    item = await db.spares_inventory.find_one({'sap_code': sap_code}, {'_id': 0})
    if not item:
        raise HTTPException(status_code=404, detail='Spare not found')
    by_month = await db.spare_transactions.aggregate([
        {'$match': {'sap_code': sap_code, 'quantity_change': {'$lt': 0}}},
        {'$group': {'_id': {'$substr': ['$created_at', 0, 7]}, 'consumed': {'$sum': {'$abs': '$quantity_change'}}}},
        {'$sort': {'_id': 1}},
    ]).to_list(100)
    by_machine = await db.spare_transactions.aggregate([
        {'$match': {'sap_code': sap_code, 'quantity_change': {'$lt': 0}, 'machine_name': {'$ne': None}}},
        {'$group': {'_id': '$machine_name', 'consumed': {'$sum': {'$abs': '$quantity_change'}}}},
        {'$sort': {'consumed': -1}}, {'$limit': 10},
    ]).to_list(10)
    by_source = await db.spare_transactions.aggregate([
        {'$match': {'sap_code': sap_code, 'quantity_change': {'$lt': 0}}},
        {'$group': {'_id': '$transaction_type', 'consumed': {'$sum': {'$abs': '$quantity_change'}}}},
    ]).to_list(20)
    return {'spare': item,
            'by_month': [{'month': m['_id'], 'consumed': m['consumed']} for m in by_month],
            'by_machine': [{'machine': m['_id'], 'consumed': m['consumed']} for m in by_machine],
            'by_source': [{'source': s['_id'], 'consumed': s['consumed']} for s in by_source]}


# ---------- Machine-spare relationship ----------
@router.get('/machines/{machine_id}/spares')
async def machine_spares(machine_id: str, user: dict = Depends(get_current_user)):
    recs = await db.machine_spares.find({'machine_id': machine_id}, {'_id': 0}).to_list(1000)
    saps = [r['sap_code'] for r in recs]
    inv = {s['sap_code']: s for s in await db.spares_inventory.find({'sap_code': {'$in': saps}}, {'_id': 0}).to_list(1000)}
    recommended = [{**r, 'material_name': inv.get(r['sap_code'], {}).get('material_name', ''),
                    'quantity': inv.get(r['sap_code'], {}).get('quantity', 0),
                    'location': inv.get(r['sap_code'], {}).get('location', '')} for r in recs]
    usage = await db.spare_transactions.find({'machine_id': machine_id, 'quantity_change': {'$lt': 0}}, {'_id': 0}).sort('created_at', -1).limit(50).to_list(50)
    most_consumed = await db.spare_transactions.aggregate([
        {'$match': {'machine_id': machine_id, 'quantity_change': {'$lt': 0}}},
        {'$group': {'_id': '$sap_code', 'consumed': {'$sum': {'$abs': '$quantity_change'}}}},
        {'$sort': {'consumed': -1}}, {'$limit': 10},
    ]).to_list(10)
    names = {s['sap_code']: s['material_name'] for s in await db.spares_inventory.find({'sap_code': {'$in': [m['_id'] for m in most_consumed]}}, {'_id': 0}).to_list(100)}
    return {'recommended': recommended, 'recent_usage': usage,
            'most_consumed': [{'sap_code': m['_id'], 'material_name': names.get(m['_id'], ''), 'consumed': m['consumed']} for m in most_consumed]}


class MachineSpareAdd(BaseModel):
    sap_code: str


@router.post('/machines/{machine_id}/spares')
async def add_machine_spare(machine_id: str, req: MachineSpareAdd, user: dict = Depends(require_admin)):
    m = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    if not await db.spares_inventory.find_one({'sap_code': req.sap_code}):
        raise HTTPException(status_code=404, detail='SAP code not found')
    if await db.machine_spares.find_one({'machine_id': machine_id, 'sap_code': req.sap_code}):
        raise HTTPException(status_code=400, detail='Already recommended')
    rec = {'id': str(uuid.uuid4()), 'machine_id': machine_id, 'machine_name': m['name'], 'sap_code': req.sap_code, 'created_at': now_iso()}
    await db.machine_spares.insert_one(dict(rec))
    rec.pop('_id', None)
    return rec


@router.delete('/machines/{machine_id}/spares/{sap_code}')
async def remove_machine_spare(machine_id: str, sap_code: str, user: dict = Depends(require_admin)):
    await db.machine_spares.delete_one({'machine_id': machine_id, 'sap_code': sap_code})
    return {'ok': True}


# ---------- CSV import ----------
class SparesCSV(BaseModel):
    csv_text: str
    mode: str = 'add'  # replace | add | subtract | adjustment
    apply: bool = False


@router.post('/spares/import')
async def import_spares_csv(req: SparesCSV, user: dict = Depends(require_admin)):
    """Full format: sap_code, material_name, quantity[, location, uom, long_text, category]
    Adjustment format: sap_code, quantity_change. Always previews unless apply=true."""
    if req.mode not in ('replace', 'add', 'subtract', 'adjustment'):
        raise HTTPException(status_code=400, detail='Invalid mode')
    reader = csv.DictReader(io.StringIO(req.csv_text.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail='Empty CSV')
    cols = [c.strip().lower() for c in reader.fieldnames]

    if req.mode == 'adjustment':
        if not {'sap_code', 'quantity_change'}.issubset(set(cols)):
            raise HTTPException(status_code=400, detail=f'Adjustment CSV requires: sap_code, quantity_change. Found: {cols}')
    else:
        if not {'sap_code', 'quantity'}.issubset(set(cols)):
            raise HTTPException(status_code=400, detail=f'CSV requires: sap_code, quantity. Found: {cols}')

    existing = {s['sap_code']: s for s in await db.spares_inventory.find({}, {'_id': 0}).to_list(100000)}
    rows, errors, seen = [], [], set()
    for i, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or '').strip() for k, v in raw.items()}
        sap = row.get('sap_code', '')
        if not sap:
            errors.append(f'Row {i}: missing sap_code')
            continue
        if sap in seen:
            errors.append(f'Row {i}: duplicate sap_code {sap}')
            continue
        seen.add(sap)
        try:
            qty = float(row['quantity_change'] if req.mode == 'adjustment' else row['quantity'])
        except (ValueError, KeyError):
            errors.append(f'Row {i}: invalid quantity for {sap}')
            continue
        item = existing.get(sap)
        if req.mode == 'adjustment' or req.mode == 'subtract':
            if not item:
                errors.append(f'Row {i}: unknown sap_code {sap}')
                continue
        old_q = float(item['quantity']) if item else 0
        if req.mode == 'replace':
            if qty < 0:
                errors.append(f'Row {i}: negative quantity for {sap}')
                continue
            new_q = qty
        elif req.mode == 'add':
            if qty < 0:
                errors.append(f'Row {i}: negative quantity for {sap} (use subtract/adjustment mode)')
                continue
            new_q = old_q + qty
        elif req.mode == 'subtract':
            new_q = old_q - qty
        else:  # adjustment: +/- allowed
            new_q = old_q + qty
        if new_q < 0:
            errors.append(f'Row {i}: resulting quantity negative for {sap} ({old_q} \u2192 {new_q})')
            continue
        rows.append({'sap_code': sap, 'material_name': row.get('material_name') or (item['material_name'] if item else ''),
                     'is_new': item is None, 'old_quantity': old_q, 'new_quantity': round(new_q, 3),
                     'change': round(new_q - old_q, 3),
                     'location': row.get('location') or (item.get('location') if item else ''),
                     'uom': row.get('uom') or (item.get('uom') if item else 'EA'),
                     'long_text': row.get('long_text') or (item.get('long_text') if item else ''),
                     'category': row.get('category') or (item.get('category') if item else '')})

    if not req.apply:
        return {'preview': True, 'mode': req.mode, 'valid_rows': len(rows), 'errors': errors, 'rows': rows[:200]}
    if errors:
        raise HTTPException(status_code=400, detail=f'{len(errors)} validation errors; fix before applying: ' + '; '.join(errors[:5]))

    for r in rows:
        if r['is_new']:
            await db.spares_inventory.insert_one({
                'id': str(uuid.uuid4()), 'sap_code': r['sap_code'], 'material_name': r['material_name'] or r['sap_code'],
                'long_text': r['long_text'], 'location': r['location'], 'quantity': r['new_quantity'], 'uom': r['uom'],
                'category': r['category'], 'manufacturer': None, 'vendor': None, 'active': True, 'total_consumed': 0,
                'created_at': now_iso(), 'updated_at': now_iso()})
        else:
            await db.spares_inventory.update_one({'sap_code': r['sap_code']}, {'$set': {'quantity': r['new_quantity'], 'updated_at': now_iso()}})
        await record_transaction(r['sap_code'], r['change'], 'CSV_IMPORT', None, f'CSV import ({req.mode})', None, None,
                                 user['username'], r['old_quantity'], r['new_quantity'])
    await create_timeline_event('inventory_imported', title=f'Spares CSV imported ({len(rows)} rows, mode={req.mode})', user=user['username'])
    return {'preview': False, 'imported': len(rows)}


# ---------- Spare locations ----------
@router.get('/spare-locations')
async def list_locations(user: dict = Depends(require_admin_or_tech)):
    return await db.spare_locations.find({}, {'_id': 0}).sort('name', 1).to_list(1000)


class LocationCreate(BaseModel):
    name: str


@router.post('/spare-locations')
async def create_location(req: LocationCreate, user: dict = Depends(require_admin)):
    if await db.spare_locations.find_one({'name': req.name}):
        raise HTTPException(status_code=400, detail='Location already exists')
    loc = {'id': str(uuid.uuid4()), 'name': req.name, 'active': True, 'created_at': now_iso()}
    await db.spare_locations.insert_one(dict(loc))
    loc.pop('_id', None)
    return loc


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


@router.put('/spare-locations/{loc_id}')
async def update_location(loc_id: str, req: LocationUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        await db.spare_locations.update_one({'id': loc_id}, {'$set': updates})
    return {'ok': True}
