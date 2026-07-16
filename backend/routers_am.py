"""Autonomous Maintenance (AM) checklists — operator-driven, SHIFT-BASED routine
checks. Deliberately separate from PM:
  • Frequency model is PER SHIFT (A/B/C, potentially 3× a day) — never the PM
    Daily/Weekly/Monthly enum.
  • Per-item response is TRI-STATE: OK / NOT_OK / NA (PM is two-state).
    Remarks are MANDATORY on NOT_OK (consistent with the PM rule), optional otherwise.
  • Fillable WITHOUT login (public kiosk) — operators identify via Name + GPID + Shift;
    email autofills for logged-in users and defaults to 'anonymous' publicly.
Templates reuse the SAME Sub-Component → items builder structure as PM checklists.

FUTURE SCOPE (documented, intentionally NOT implemented): repeated NOT_OK results
on the same check item are a leading degradation indicator that could later feed
the AWS predictive health pools (Mechanical/Electrical/PLC).
"""
import re as _re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user, require_admin
from database import db
from events import create_timeline_event, create_notification, now_iso
from routers_maintenance import _normalize_groups

router = APIRouter()

SHIFTS = ('A', 'B', 'C')
AM_STATUSES = ('OK', 'NOT_OK', 'NA')


# ============ TEMPLATES (admin-managed, per machine) ============

class AMTemplateCreate(BaseModel):
    machine_id: str
    template_name: str
    checklist_groups: List[dict]  # [{description(sub-component), items: [{checked_for, parameter}]}]


class AMTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    checklist_groups: Optional[List[dict]] = None
    active: Optional[bool] = None


class AMTemplateDuplicate(BaseModel):
    target_machine_id: str
    template_name: Optional[str] = None  # defaults to "AM — <target machine>"


async def _machine_or_404(machine_id: str):
    m = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    return m


def _template_doc(machine: dict, name: str, groups: list, username: str) -> dict:
    return {
        'id': str(uuid.uuid4()), 'machine_id': machine['id'], 'machine_name': machine['name'],
        'line': machine.get('line'), 'department': machine.get('department'),
        'process_group': machine.get('process_group'),
        'template_name': name, 'checklist_groups': groups,
        'frequency': 'per_shift',  # AM's own model — deliberately NOT the PM enum
        'active': True, 'created_at': now_iso(), 'created_by': username,
        'updated_at': None, 'updated_by': None,
    }


@router.get('/am-templates')
async def list_am_templates(machine_id: Optional[str] = None, active: Optional[bool] = None,
                            user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if active is not None:
        q['active'] = active
    return await db.am_templates.find(q, {'_id': 0}).sort('machine_name', 1).to_list(500)


@router.post('/am-templates')
async def create_am_template(req: AMTemplateCreate, user: dict = Depends(require_admin)):
    machine = await _machine_or_404(req.machine_id)
    name = str(req.template_name or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='Template name is required')
    groups = _normalize_groups(req.checklist_groups)
    if not groups:
        raise HTTPException(status_code=400, detail='At least one sub-component with a check item is required')
    doc = _template_doc(machine, name, groups, user['username'])
    await db.am_templates.insert_one(dict(doc))
    return doc


@router.put('/am-templates/{template_id}')
async def update_am_template(template_id: str, req: AMTemplateUpdate, user: dict = Depends(require_admin)):
    t = await db.am_templates.find_one({'id': template_id}, {'_id': 0})
    if not t:
        raise HTTPException(status_code=404, detail='AM template not found')
    updates = {'updated_at': now_iso(), 'updated_by': user['username']}
    if req.template_name is not None:
        name = req.template_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail='Template name cannot be empty')
        updates['template_name'] = name
    if req.checklist_groups is not None:
        groups = _normalize_groups(req.checklist_groups)
        if not groups:
            raise HTTPException(status_code=400, detail='At least one sub-component with a check item is required')
        updates['checklist_groups'] = groups
    if req.active is not None:
        updates['active'] = req.active
    await db.am_templates.update_one({'id': template_id}, {'$set': updates})
    return await db.am_templates.find_one({'id': template_id}, {'_id': 0})


@router.delete('/am-templates/{template_id}')
async def delete_am_template(template_id: str, user: dict = Depends(require_admin)):
    res = await db.am_templates.delete_one({'id': template_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail='AM template not found')
    return {'ok': True}


@router.post('/am-templates/{template_id}/duplicate')
async def duplicate_am_template(template_id: str, req: AMTemplateDuplicate, user: dict = Depends(require_admin)):
    """Copy a template to ANOTHER machine (there is no machine-type concept —
    duplication is how one checklist design is reused across similar machines)."""
    t = await db.am_templates.find_one({'id': template_id}, {'_id': 0})
    if not t:
        raise HTTPException(status_code=404, detail='AM template not found')
    machine = await _machine_or_404(req.target_machine_id)
    name = (req.template_name or '').strip() or f"AM — {machine['name']}"
    doc = _template_doc(machine, name, t['checklist_groups'], user['username'])
    await db.am_templates.insert_one(dict(doc))
    return doc


# ============ SUBMISSIONS (tri-state, shift-based) ============

class AMSubmit(BaseModel):
    template_id: str
    name: str
    gpid: str
    shift: str  # A | B | C
    started_at: Optional[str] = None  # captured client-side when the checklist was opened
    row_results: List[dict] = []      # [{description, checked_for, status: OK|NOT_OK|NA, remarks}]


def _validate_rows(template: dict, rows: list) -> tuple:
    """Every template item must be answered with a tri-state status.
    Remarks are MANDATORY for NOT_OK rows (same rule as PM), optional for OK/NA."""
    expected = {(g['description'], i['checked_for'])
                for g in template.get('checklist_groups', []) for i in g['items']}
    cleaned, seen, not_ok = [], set(), 0
    for r in rows or []:
        key = (r.get('description'), r.get('checked_for'))
        if key not in expected or key in seen:
            continue
        seen.add(key)
        status = str(r.get('status') or '').upper().replace(' ', '_')
        if status not in AM_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status for '{key[1]}' — must be OK, NOT_OK or NA")
        remarks = str(r.get('remarks') or '').strip()
        if status == 'NOT_OK':
            not_ok += 1
            if not remarks:
                raise HTTPException(status_code=400, detail=f"Remarks are required for NOT OK item: {key[0]} — {key[1]}")
        cleaned.append({'description': key[0], 'checked_for': key[1],
                        'parameter': r.get('parameter') or '', 'status': status, 'remarks': remarks})
    missing = expected - seen
    if missing:
        d, c = sorted(missing)[0]
        raise HTTPException(status_code=400, detail=f"All items need a status — missing: {d} — {c} ({len(missing)} unanswered)")
    return cleaned, not_ok


async def _create_submission(req: AMSubmit, email: str, via: str) -> dict:
    template = await db.am_templates.find_one({'id': req.template_id, 'active': True}, {'_id': 0})
    if not template:
        raise HTTPException(status_code=404, detail='AM template not found or inactive')
    name = req.name.strip()
    gpid = req.gpid.strip()
    shift = str(req.shift or '').strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail='Name is required')
    if not gpid:
        raise HTTPException(status_code=400, detail='GPID (employee ID) is required')
    if shift not in SHIFTS:
        raise HTTPException(status_code=400, detail='Shift must be A, B or C')
    rows, not_ok = _validate_rows(template, req.row_results)

    completed_at = now_iso()
    started_at = req.started_at or completed_at
    try:
        s = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        e = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
        duration = round(max((e - s).total_seconds() / 60, 0), 1)
        if duration > 24 * 60:  # ignore stale/clock-skewed open times
            started_at, duration = completed_at, 0.0
    except (ValueError, TypeError):
        started_at, duration = completed_at, 0.0

    sub = {
        'id': str(uuid.uuid4()), 'template_id': template['id'], 'template_name': template['template_name'],
        'machine_id': template['machine_id'], 'machine_name': template['machine_name'],
        'line': template.get('line'), 'department': template.get('department'),
        'process_group': template.get('process_group'),
        'name': name, 'gpid': gpid, 'shift': shift, 'email': email,
        'started_at': started_at, 'completed_at': completed_at, 'duration_minutes': duration,
        'row_results': rows, 'not_ok_count': not_ok,
        'submitted_via': via, 'created_at': completed_at,
    }
    await db.am_submissions.insert_one(dict(sub))
    await create_timeline_event('am_submitted', machine_id=template['machine_id'], machine_name=template['machine_name'],
                                title=f"AM checklist submitted — {template['machine_name']} (Shift {shift})",
                                description=f"{name} (GPID {gpid}) · {len(rows)} items · {not_ok} NOT OK",
                                user=name, reference_id=sub['id'], reference_type='am_submission',
                                department=template.get('department'), line=template.get('line'))
    if not_ok:
        flagged = '; '.join(f"{r['description']} — {r['checked_for']}" for r in rows if r['status'] == 'NOT_OK')[:300]
        await create_notification('am_checklist', f"AM Checklist flagged issues: {template['machine_name']}",
                                  f"Shift {shift} AM check by {name} (GPID {gpid}) marked {not_ok} item(s) NOT OK: {flagged}",
                                  severity='warning', machine_id=template['machine_id'],
                                  machine_name=template['machine_name'], reference_id=sub['id'],
                                  reference_type='am_submission')
    return sub


@router.post('/am-submissions')
async def submit_am_checklist(req: AMSubmit, user: dict = Depends(get_current_user)):
    email = user.get('email') or user.get('username') or 'anonymous'
    return await _create_submission(req, email, 'authenticated')


@router.get('/am-submissions')
async def list_am_submissions(machine_id: Optional[str] = None, template_id: Optional[str] = None,
                              shift: Optional[str] = None, date_from: Optional[str] = None,
                              date_to: Optional[str] = None, limit: int = Query(200, le=1000),
                              user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if template_id:
        q['template_id'] = template_id
    if shift and shift.upper() in SHIFTS:
        q['shift'] = shift.upper()
    if date_from or date_to:
        rng = {}
        if date_from:
            rng['$gte'] = date_from
        if date_to:
            rng['$lte'] = date_to + 'T23:59:59'
        q['completed_at'] = rng
    return await db.am_submissions.find(q, {'_id': 0}).sort('completed_at', -1).limit(limit).to_list(limit)


@router.get('/am-coverage')
async def am_coverage(date: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Today's (or a given date's) per-shift coverage board: which A/B/C shift
    submissions exist for every machine that has an active AM template."""
    day = (date or now_iso()[:10])[:10]
    templates = await db.am_templates.find({'active': True}, {'_id': 0}).sort('machine_name', 1).to_list(500)
    subs = await db.am_submissions.find(
        {'completed_at': {'$gte': day, '$lte': day + 'T23:59:59'}},
        {'_id': 0, 'template_id': 1, 'shift': 1, 'completed_at': 1, 'name': 1}).to_list(2000)
    by_tpl = {}
    for s in subs:
        by_tpl.setdefault(s['template_id'], {}).setdefault(s['shift'], []).append(s)
    rows = []
    for t in templates:
        done = by_tpl.get(t['id'], {})
        rows.append({
            'template_id': t['id'], 'template_name': t['template_name'],
            'machine_id': t['machine_id'], 'machine_name': t['machine_name'], 'line': t.get('line'),
            'shifts': {sh: {'done': sh in done, 'count': len(done.get(sh, [])),
                            'last_by': done[sh][-1]['name'] if sh in done else None} for sh in SHIFTS},
        })
    return {'date': day, 'rows': rows}


# ============ PDF EXPORT (mirrors the PM printable sheet format) ============

@router.get('/am-templates/{template_id}/pdf')
async def am_pdf(template_id: str, submission_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Printable AM checklist sheet — blank template by default; pass submission_id
    (or 'latest') for a completed instance. Same tabular format as the PM sheet:
    Sub-Component / Check Item / Status / Remarks + Machine/Line/Shift/Date header
    and a Done-By (Name + GPID) signature line."""
    import base64 as _b64
    from io import BytesIO
    from fastapi.responses import Response
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    template = await db.am_templates.find_one({'id': template_id}, {'_id': 0})
    if not template:
        raise HTTPException(status_code=404, detail='AM template not found')
    submission = None
    if submission_id:
        q = {'template_id': template_id} if submission_id == 'latest' else {'id': submission_id, 'template_id': template_id}
        submission = await db.am_submissions.find_one(q, {'_id': 0}, sort=[('completed_at', -1)])
        if not submission:
            raise HTTPException(status_code=404, detail='AM submission not found')
    branding = await db.branding.find_one({'id': 'branding'}, {'_id': 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    cell = ParagraphStyle('cell', parent=styles['Normal'], fontSize=8, leading=10)
    cell_b = ParagraphStyle('cellb', parent=cell, fontName='Helvetica-Bold')
    title_style = ParagraphStyle('t', parent=styles['Title'], fontSize=14, spaceAfter=2)
    story = []

    logo_flowable = None
    logo_data = branding.get('logo_data') or ''
    if logo_data.startswith('data:image') and ';base64,' in logo_data and 'svg' not in logo_data.split(';')[0]:
        try:
            raw = _b64.b64decode(logo_data.split(';base64,', 1)[1])
            img_reader = ImageReader(BytesIO(raw))
            iw, ih = img_reader.getSize()
            h = 14 * mm
            w = min(h * (iw / ih) if ih else h, 45 * mm)
            logo_flowable = RLImage(BytesIO(raw), width=w, height=h)
        except Exception:
            logo_flowable = None
    title_block = [
        Paragraph(branding.get('app_name') or 'Factory Operations', ParagraphStyle('org', parent=styles['Normal'], fontSize=9, textColor=colors.grey)),
        Paragraph('AUTONOMOUS MAINTENANCE (AM) CHECKLIST', title_style),
        Paragraph(template['template_name'], ParagraphStyle('sub', parent=styles['Heading2'], fontSize=11, spaceAfter=0)),
    ]
    if logo_flowable:
        hdr = Table([[logo_flowable, title_block]], colWidths=[50 * mm, 136 * mm])
        hdr.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (0, 0), 0)]))
        story.append(hdr)
        story.append(Spacer(1, 3 * mm))
    else:
        story.extend(title_block)
        story.append(Spacer(1, 2 * mm))

    shift_val = submission['shift'] if submission else '_' * 6
    date_val = submission['completed_at'][:10] if submission else '_' * 16
    info = [[
        Paragraph(f"<b>Machine:</b> {template['machine_name']}", cell),
        Paragraph(f"<b>Line:</b> {template.get('line', '')}", cell),
        Paragraph('<b>Frequency:</b> Per Shift', cell),
        Paragraph(f"<b>Shift:</b> {shift_val}", cell),
        Paragraph(f"<b>Date:</b> {date_val}", cell),
    ]]
    info_t = Table(info, colWidths=[46 * mm, 34 * mm, 34 * mm, 26 * mm, 46 * mm])
    info_t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 4 * mm))

    def status_boxes():
        """Outlined EMPTY tri-state checkboxes: ☐ OK ☐ NOT OK ☐ NA."""
        t = Table([['', 'OK', '', 'NOT OK', '', 'NA']],
                  colWidths=[3.6 * mm, 6 * mm, 3.6 * mm, 10.5 * mm, 3.6 * mm, 6 * mm], rowHeights=[3.6 * mm])
        t.setStyle(TableStyle([
            ('BOX', (0, 0), (0, 0), 0.7, colors.black),
            ('BOX', (2, 0), (2, 0), 0.7, colors.black),
            ('BOX', (4, 0), (4, 0), 0.7, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1), ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return t

    result_map = {}
    if submission:
        for r in submission.get('row_results') or []:
            result_map[(r.get('description'), r.get('checked_for'))] = r

    header = [Paragraph(f'<b>{h}</b>', cell_b) for h in ['S.N.', 'Sub-Component', 'Check Item', 'Parameter / Process', 'Status', 'Remarks']]
    data = [header]
    span_cmds = []
    idx = 0
    for gi, g in enumerate(template.get('checklist_groups', []), start=1):
        for ii, item in enumerate(g['items']):
            idx += 1
            res = result_map.get((g['description'], item['checked_for']))
            status_txt = (res['status'].replace('_', ' ') if res else '')
            status_cell = Paragraph(status_txt, cell) if submission else status_boxes()
            data.append([
                Paragraph(str(gi) if ii == 0 else '', cell),
                Paragraph(g['description'] if ii == 0 else '', cell_b if ii == 0 else cell),
                Paragraph(item['checked_for'], cell), Paragraph(item.get('parameter', ''), cell),
                status_cell, Paragraph(res.get('remarks', '') if res else '', cell),
            ])
            if ii == 0 and len(g['items']) > 1:
                span_cmds.append(('SPAN', (0, idx), (0, idx + len(g['items']) - 1)))
                span_cmds.append(('SPAN', (1, idx), (1, idx + len(g['items']) - 1)))
    if len(data) == 1:
        data.append([Paragraph('—', cell)] * 6)
    tbl = Table(data, colWidths=[11 * mm, 34 * mm, 42 * mm, 34 * mm, 30 * mm, 35 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.88, 0.88, 0.88)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ] + span_cmds))
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))

    done_name = submission.get('name', '') if submission else ''
    done_gpid = submission.get('gpid', '') if submission else ''
    times = ''
    if submission:
        times = f"Start: {submission['started_at'][11:16]}  ·  End: {submission['completed_at'][11:16]}  ·  {submission['duration_minutes']} min"
    sig = [[
        Paragraph('<b>Done By</b>', cell_b), Paragraph('<b>Checked By</b>', cell_b),
    ], [
        Paragraph(f"Name: {done_name or '_' * 24} &nbsp;&nbsp; GPID: {done_gpid or '_' * 12}", cell),
        Paragraph('Name: ' + '_' * 28, cell),
    ], [
        Paragraph(f"Signature: {'_' * 24} &nbsp;&nbsp; {times}", cell), Paragraph('Signature: ' + '_' * 28, cell),
    ]]
    sig_t = Table(sig, colWidths=[103 * mm, 83 * mm])
    sig_t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(sig_t)
    doc.build(story)

    suffix = 'completed' if submission else 'blank'
    safe_name = _re.sub(r'[^A-Za-z0-9._-]+', '_', template['template_name'])[:40].strip('_') or 'template'
    fname = f"AM_{safe_name}_{suffix}.pdf"
    return Response(content=buf.getvalue(), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


# ============ PUBLIC (no-login kiosk) ENDPOINTS ============

@router.get('/public/am-context')
async def public_am_context():
    """Machines that have an active AM template — minimal payload for the public
    kiosk machine picker. No auth (shift-floor operators may not have accounts)."""
    templates = await db.am_templates.find(
        {'active': True},
        {'_id': 0, 'id': 1, 'template_name': 1, 'machine_id': 1, 'machine_name': 1, 'line': 1, 'process_group': 1},
    ).sort('machine_name', 1).to_list(500)
    return {'templates': templates}


@router.get('/public/am-templates/{template_id}')
async def public_am_template(template_id: str):
    t = await db.am_templates.find_one({'id': template_id, 'active': True}, {'_id': 0})
    if not t:
        raise HTTPException(status_code=404, detail='AM template not found or inactive')
    return t


@router.post('/public/am-submissions')
async def public_submit_am(req: AMSubmit):
    """No-login submission — operator accountability via Name + GPID + Shift;
    email defaults to 'anonymous' (matches the public breakdown kiosk rationale)."""
    sub = await _create_submission(req, 'anonymous', 'public_kiosk')
    return {'ok': True, 'id': sub['id'], 'machine_name': sub['machine_name'],
            'shift': sub['shift'], 'not_ok_count': sub['not_ok_count'],
            'duration_minutes': sub['duration_minutes']}
