"""Shared KPI engine — the SINGLE runtime source of truth for the whole platform.

Rules (applied identically in Control Room, Analytics and anywhere availability is shown):
  • Live default — the plant is assumed to run 24/7. Calendar hours accumulate
    continuously off the real clock; downtime for un-logged periods is the merged
    (union) overlap of breakdown open-time with the window.
  • Logged override — once a line-runtime log exists for a (line, date), that logged
    figure is AUTHORITATIVE for that date and replaces the live/assumed calculation
    everywhere that references the date.
"""
from datetime import datetime, timezone, timedelta

from database import db


def parse_iso(s):
    try:
        dt = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def merged_minutes(intervals, exclude_ranges=None):
    """Union of intervals in minutes — concurrent breakdowns don't double count.
    `exclude_ranges` carves out periods governed by logged runtime data."""
    clipped = []
    for s, e in intervals:
        parts = [(s, e)]
        for xs, xe in (exclude_ranges or []):
            nxt = []
            for ps, pe in parts:
                if pe <= xs or ps >= xe:
                    nxt.append((ps, pe))
                else:
                    if ps < xs:
                        nxt.append((ps, xs))
                    if pe > xe:
                        nxt.append((xe, pe))
            parts = nxt
        clipped.extend(p for p in parts if (p[1] - p[0]).total_seconds() > 0)
    if not clipped:
        return 0.0
    total = 0.0
    cur_s, cur_e = None, None
    for s, e in sorted(clipped):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds() / 60.0
            cur_s, cur_e = s, e
        elif e > cur_e:
            cur_e = e
    total += (cur_e - cur_s).total_seconds() / 60.0
    return total


async def compute_line_kpis(since, until):
    """Availability + downtime per line & per section over [since, until].
    Returns {'window_minutes', 'lines': [...], 'plant_availability'}."""
    now = datetime.now(timezone.utc)
    until = min(until, now)
    window_min = max((until - since).total_seconds() / 60.0, 0.0)

    machines = await db.machines.find({}, {'_id': 0, 'id': 1, 'line': 1, 'process_group': 1, 'department': 1, 'status': 1}).to_list(100000)
    lines = {}
    for m in machines:
        ln = lines.setdefault(m['line'], {
            'line': m['line'], 'department': m.get('department'), 'machines': 0,
            'running': 0, 'failed': 0, 'intervals': [], 'sections': {},
        })
        ln['machines'] += 1
        if m['status'] == 'running':
            ln['running'] += 1
        elif m['status'] == 'failed':
            ln['failed'] += 1
        pg = ln['sections'].setdefault(m.get('process_group') or '—', {
            'process_group': m.get('process_group') or '—', 'machines': 0, 'intervals': [],
        })
        pg['machines'] += 1

    # authoritative logged line-runtime days inside the window
    day0 = since.date()
    day_last = (until - timedelta(seconds=1)).date()
    date_list = []
    d = day0
    while d <= day_last:
        date_list.append(d.isoformat())
        d += timedelta(days=1)
    logged = {}
    async for lg in db.line_runtime_logs.find({'date': {'$in': date_list}}, {'_id': 0}):
        logged[(lg['line'], lg['date'])] = lg

    def day_overlap_minutes(date_str):
        ds = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        de = ds + timedelta(days=1)
        s, e = max(ds, since), min(de, until)
        return max((e - s).total_seconds() / 60.0, 0.0)

    def logged_day_ranges(line_name):
        out = []
        for date_str in date_list:
            if (line_name, date_str) in logged:
                ds = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                out.append((max(ds, since), min(ds + timedelta(days=1), until)))
        return out

    since_iso = since.isoformat()
    active_bd = {}  # line -> (earliest open breakdown start, breakdown id, ticket) for the live timer ribbon
    q = {'$or': [{'end_time': None}, {'end_time': {'$gte': since_iso}}]}
    async for bd in db.breakdowns.find(q, {'_id': 0, 'id': 1, 'ticket_number': 1, 'line': 1, 'process_group': 1, 'start_time': 1, 'end_time': 1, 'status': 1}):
        start = parse_iso(bd.get('start_time') or '') or since
        end = parse_iso(bd.get('end_time') or '') or now
        if not bd.get('end_time') and bd.get('status') in ('OPEN', 'ASSIGNED', 'IN_PROGRESS'):
            prev = active_bd.get(bd.get('line'))
            if prev is None or start < prev[0]:
                active_bd[bd.get('line')] = (start, bd.get('id'), bd.get('ticket_number'))
        s, e = max(start, since), min(end, until)
        if (e - s).total_seconds() <= 0:
            continue
        ln = lines.get(bd.get('line'))
        if not ln:
            continue
        ln['intervals'].append((s, e))
        pg = ln['sections'].get(bd.get('process_group') or '—')
        if pg:
            pg['intervals'].append((s, e))

    def avail(downtime_min):
        dt = min(downtime_min, window_min)
        return round(max(0.0, (window_min - dt) / window_min) * 100, 1) if window_min else None

    order = {'PC21': 0, 'PC32': 1, 'PC36': 2, 'KKR': 3, 'TWZ': 4, 'BCP': 5}
    out = []
    plant_down = 0.0
    for ln in lines.values():
        sections = []
        for pg in ln['sections'].values():
            pg_down = min(merged_minutes(pg['intervals']), window_min)
            sections.append({
                'process_group': pg['process_group'], 'machines': pg['machines'],
                'downtime_minutes': round(pg_down, 1),
                'availability': avail(pg_down),
            })
        sections.sort(key=lambda s: (-(s['downtime_minutes']), s['process_group']))
        # line downtime = live breakdown downtime OUTSIDE logged days + logged dark time INSIDE
        excl = logged_day_ranges(ln['line'])
        live_down = merged_minutes(ln['intervals'], exclude_ranges=excl)
        logged_down = 0.0
        for date_str in date_list:
            lg = logged.get((ln['line'], date_str))
            if not lg:
                continue
            cal = float(lg.get('calendar_hours') or 24)
            run = float(lg.get('run_hours') or 0)
            frac = day_overlap_minutes(date_str) / (24 * 60.0)
            logged_down += max(cal - run, 0) * 60.0 * frac
        ln_down = min(live_down + logged_down, window_min)
        plant_down += ln_down
        active_since = active_bd.get(ln['line'])
        out.append({
            'line': ln['line'], 'department': ln['department'], 'machines': ln['machines'],
            'running': ln['running'], 'failed': ln['failed'],
            'downtime_minutes': round(ln_down, 1),
            'availability': avail(ln_down),
            'logged_days': len(excl),
            'active_breakdown_since': active_since[0].isoformat() if active_since else None,
            'active_breakdown_id': active_since[1] if active_since else None,
            'active_breakdown_ticket': active_since[2] if active_since else None,
            'sections': sections,
        })
    out.sort(key=lambda x: (order.get(x['line'], 99), x['department'] or '', x['line']))
    plant_availability = None
    if out and window_min:
        plant_availability = round(max(0.0, (window_min * len(out) - plant_down) / (window_min * len(out))) * 100, 1)
    return {'window_minutes': window_min, 'since': since_iso, 'until': until.isoformat(),
            'plant_availability': plant_availability, 'lines': out}
