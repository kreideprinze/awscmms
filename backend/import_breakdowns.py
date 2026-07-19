"""One-time historical breakdown import from 'Process Breakdown Entry_ Pune' Excel.
Usage:  python import_breakdowns.py            -> DRY RUN (report only, no writes)
        python import_breakdowns.py --commit   -> actually insert
Direct DB insert of CLOSED breakdowns only: no WOs, notifications, timers or machine
status changes are triggered. reporter='excel-import' tags every imported record.
"""
import os, sys, asyncio, uuid, difflib
from datetime import datetime, timedelta, timezone
import openpyxl
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
IST = timezone(timedelta(hours=5, minutes=30))
XLSX = '/tmp/bd.xlsx'
LINE_COL = {'PC21': 7, 'PC32': 8, 'PC36': 9, 'KKR': 10, 'TWZ': 11, 'BCP': 12}  # 0-based
TYPE_MAP = {'electrical': 'ELECTRICAL', 'mechanical': 'MECHANICAL', 'plc': 'CONTROL_PLC',
            'control': 'CONTROL_PLC', 'instrumentation': 'CONTROL_PLC'}

def norm(s):
    return ' '.join(str(s or '').replace('\xa0', ' ').split()).strip()

def parse_hhmm(v):
    v = norm(v).replace('.', ':').replace(';', ':')
    if not v:
        return None
    try:
        parts = v.split(':')
        return int(parts[0]) % 24, (int(parts[1]) % 60 if len(parts) > 1 and parts[1].strip() else 0)
    except Exception:
        return None

async def main(commit=False):
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ.get('DB_NAME', 'factory_ops')]
    machines = await db.machines.find({}, {'_id': 0, 'id': 1, 'name': 1, 'line': 1, 'department': 1,
                                           'process_group': 1, 'commissioned_at': 1}).to_list(500)
    by_line = {}
    for m in machines:
        by_line.setdefault(m['line'], {})[norm(m['name']).lower()] = m
    techs = {u['username'].strip().lower(): u['username'] for u in
             await db.users.find({'role': 'technician', 'active': True}, {'_id': 0, 'username': 1}).to_list(100)}

    ws = openpyxl.load_workbook(XLSX)[ 'Sheet1']
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    ok, unmatched, badrow, pre_comm = [], {}, [], []
    type_other = {}
    for r in rows:
        rid = r[0]
        line = norm(r[6]).upper().replace(' ', '')
        col = LINE_COL.get(line)
        equip = norm(r[col]) if col is not None else ''
        if not equip:
            badrow.append((rid, f'no equipment (line={line})')); continue
        pool = by_line.get(line, {})
        m = pool.get(equip.lower())
        if not m:  # fuzzy
            cand = difflib.get_close_matches(equip.lower(), list(pool.keys()), n=1, cutoff=0.75)
            if cand:
                m = pool[cand[0]]
        if not m:
            unmatched.setdefault(f'{line} :: {equip}', 0)
            unmatched[f'{line} :: {equip}'] += 1
            continue
        # date + times (IST -> UTC)
        d = r[16]
        if not isinstance(d, datetime):
            badrow.append((rid, f'bad date {d!r}')); continue
        st, et = parse_hhmm(r[17]), parse_hhmm(r[18])
        if not st:
            badrow.append((rid, f'bad start time {r[17]!r}')); continue
        start = datetime(d.year, d.month, d.day, st[0], st[1], tzinfo=IST)
        try:
            dur = float(norm(r[19]) or 0)
        except Exception:
            dur = 0
        if et:
            end = datetime(d.year, d.month, d.day, et[0], et[1], tzinfo=IST)
            if end <= start:
                end += timedelta(days=1)
        else:
            end = start + timedelta(minutes=dur or 5)
        minutes = round((end - start).total_seconds() / 60.0, 1)
        if dur and abs(minutes - dur) > 720:  # sanity: trust explicit duration on wild mismatch
            end = start + timedelta(minutes=dur)
            minutes = dur
        raw_type = norm(r[15]).lower()
        btype = next((v for k, v in TYPE_MAP.items() if k in raw_type), None)
        if not btype:
            type_other.setdefault(norm(r[15]) or '(blank)', 0)
            type_other[norm(r[15]) or '(blank)'] += 1
            btype = 'MECHANICAL'
        attended = norm(r[21])
        tech = None
        if attended:
            c = difflib.get_close_matches(attended.lower().split()[0], list(techs.keys()), n=1, cutoff=0.85)
            tech = techs[c[0]] if c else None
        comm = m.get('commissioned_at')
        if comm:
            cdt = datetime.fromisoformat(str(comm).replace('Z', '+00:00'))
            if start.astimezone(timezone.utc) < cdt:
                pre_comm.append((rid, m['name'], m['line'], start.date().isoformat(), str(cdt.date())))
        action = norm(r[20])
        if attended and not tech:
            action = (action + f' [Attended by: {attended}]').strip()
        ok.append({
            'id': str(uuid.uuid4()), 'machine_id': m['id'], 'machine_name': m['name'],
            'department': m.get('department'), 'line': m['line'], 'process_group': m.get('process_group'),
            'failure_mode': norm(r[15]) or btype.title(), 'breakdown_type': btype,
            'description': norm(r[13]) or '(no description)', 'reporter': 'excel-import',
            'status': 'CLOSED', 'assigned_to': tech,
            'start_time': start.astimezone(timezone.utc).isoformat(),
            'end_time': end.astimezone(timezone.utc).isoformat(),
            'downtime_minutes': minutes, 'repair_duration_minutes': minutes,
            'root_cause': None, 'action_taken': action or None, 'consumed_spares': [],
            'rca_task_id': None, 'work_order_id': None, 'closed_by': 'excel-import',
            'closed_at': end.astimezone(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(), 'imported': True,
        })

    dates = sorted(b['start_time'] for b in ok)
    print(f'ROWS: {len(rows)} | importable: {len(ok)} | unmatched-machine rows: {sum(unmatched.values())} | bad rows: {len(badrow)}')
    if dates:
        print(f'date range: {dates[0][:10]} .. {dates[-1][:10]}')
    print(f'assigned to existing technician: {sum(1 for b in ok if b["assigned_to"])} rows')
    print(f'\nPRE-COMMISSIONING rows (would poison MTBF unless commissioned_at is backdated): {len(pre_comm)}')
    for p in pre_comm[:15]: print('  ', p)
    print('\nUNMATCHED equipment (line :: excel name -> count):')
    for k, v in sorted(unmatched.items()): print(f'   {k} x{v}')
    print('\nUnknown breakdown types (defaulted to MECHANICAL):', type_other)
    print('\nBAD ROWS:')
    for b in badrow[:15]: print('  ', b)

    if commit:
        # backdate commissioned_at for affected machines to the earliest imported breakdown
        earliest = {}
        for b in ok:
            k = b['machine_id']
            earliest[k] = min(earliest.get(k, b['start_time']), b['start_time'])
        n_back = 0
        for mid, e in earliest.items():
            m = next(x for x in machines if x['id'] == mid)
            comm = m.get('commissioned_at')
            if comm and datetime.fromisoformat(str(comm).replace('Z', '+00:00')) > datetime.fromisoformat(e):
                await db.machines.update_one({'id': mid}, {'$set': {'commissioned_at':
                    (datetime.fromisoformat(e) - timedelta(days=1)).isoformat()}})
                n_back += 1
        # ticket numbers via counter
        for b in ok:
            c = await db.counters.find_one_and_update({'id': 'breakdowns'}, {'$inc': {'seq': 1}}, upsert=True, return_document=True)
            b['ticket_number'] = f"BD-{c['seq']:05d}"
        await db.breakdowns.insert_many([dict(b) for b in ok])
        print(f'\nCOMMITTED: {len(ok)} breakdowns inserted, commissioned_at backdated on {n_back} machines')
    else:
        print('\nDRY RUN ONLY — nothing written. Re-run with --commit to import.')

asyncio.run(main('--commit' in sys.argv))
