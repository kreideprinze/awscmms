"""Shared KPI engine — the SINGLE runtime source of truth for the whole platform.

PLANNED-RUNTIME MODEL (authoritative per Line × Date):
  • Manual input: ONE value per line-day — `planned_hours` (scheduled production
    hours for that line that day; varies with production planning, NOT fixed 24h).
  • Downtime: derived LIVE at read time from BREAKDOWN records only (union-merged
    so concurrent breakdowns don't double count). Warnings live in a separate
    collection and NEVER count as downtime — they do not affect Availability.
  • Availability = ((Planned − Downtime) ÷ Planned) × 100, clamped at 0%.
    When downtime exceeds planned a `clamped` data-quality flag is surfaced
    instead of failing silently.
  • Unlogged days: visibly marked missing in the Runtime calendar. Live KPI
    windows (Control Room / Analytics) fall back to a 24/7 assumption
    (planned = 24h) ONLY for unlogged days so real-time figures keep ticking.

No other module may recompute availability independently — Control Room line
cards, Line Availability/Downtime sections, Plant Totals, Analytics and the
AWS/reliability engine all read from the helpers in this file.
"""
from datetime import datetime, timezone, timedelta

from database import db


def parse_iso(s):
    try:
        dt = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def merged_minutes(intervals):
    """Union of intervals in minutes — concurrent breakdowns don't double count."""
    ivs = [(s, e) for s, e in intervals if (e - s).total_seconds() > 0]
    if not ivs:
        return 0.0
    total = 0.0
    cur_s, cur_e = None, None
    for s, e in sorted(ivs):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds() / 60.0
            cur_s, cur_e = s, e
        elif e > cur_e:
            cur_e = e
    total += (cur_e - cur_s).total_seconds() / 60.0
    return total


def clip_minutes(intervals, win_start, win_end):
    """Union-merged minutes of `intervals` clipped to [win_start, win_end]."""
    clipped = []
    for s, e in intervals:
        cs, ce = max(s, win_start), min(e, win_end)
        if (ce - cs).total_seconds() > 0:
            clipped.append((cs, ce))
    return merged_minutes(clipped)


async def load_line_breakdown_intervals(date_from_dt, date_to_dt, lines=None):
    """{line: [(start, end)]} for BREAKDOWNS overlapping [date_from_dt, date_to_dt).
    Downtime source is db.breakdowns ONLY — warnings are a separate collection and
    are excluded from downtime by design (they never affect Availability).
    Open breakdowns tick live (end = now)."""
    now = datetime.now(timezone.utc)
    q = {'$or': [{'end_time': None}, {'end_time': {'$gte': date_from_dt.isoformat()}}]}
    if lines is not None:
        q['line'] = {'$in': list(lines)}
    out = {}
    async for bd in db.breakdowns.find(q, {'_id': 0, 'line': 1, 'start_time': 1, 'end_time': 1}):
        start = parse_iso(bd.get('start_time') or '')
        if not start or start >= date_to_dt:
            continue
        end = parse_iso(bd.get('end_time') or '') or now  # open breakdown → live ticking
        if end <= start:
            continue
        out.setdefault(bd.get('line'), []).append((start, end))
    return out


def derive_day(planned_hours, downtime_minutes):
    """Authoritative line-day math: Availability = (Planned − Downtime)/Planned × 100,
    clamped at 0%. `clamped` flags the data-quality case downtime > planned."""
    planned_min = max(float(planned_hours or 0), 0.0) * 60.0
    run_min = max(planned_min - downtime_minutes, 0.0)
    return {
        'planned_hours': round(planned_min / 60.0, 2),
        'downtime_hours': round(downtime_minutes / 60.0, 2),
        'run_hours': round(run_min / 60.0, 2),
        'availability': round(run_min / planned_min * 100, 1) if planned_min > 0 else None,
        'clamped': downtime_minutes > planned_min + 1e-6,
    }


async def derive_line_day_rows(line=None, lines=None, date_from=None, date_to=None, logs=None):
    """Derived rows for LOGGED line-days: planned (manual) + downtime (live from
    breakdowns) + run/availability/clamped. This feeds the Runtime calendar,
    Analytics and machine summaries — the one authoritative per-day figure."""
    if logs is None:
        q = {}
        if line:
            q['line'] = line
        elif lines is not None:
            q['line'] = {'$in': list(lines)}
        if date_from or date_to:
            q['date'] = {}
            if date_from:
                q['date']['$gte'] = date_from
            if date_to:
                q['date']['$lte'] = date_to
        logs = await db.line_runtime_logs.find(q, {'_id': 0}).sort('date', -1).to_list(100000)
    if not logs:
        return []
    dmin = min(l['date'] for l in logs)
    dmax = max(l['date'] for l in logs)
    from_dt = datetime.fromisoformat(dmin).replace(tzinfo=timezone.utc)
    to_dt = datetime.fromisoformat(dmax).replace(tzinfo=timezone.utc) + timedelta(days=1)
    iv_map = await load_line_breakdown_intervals(from_dt, to_dt, lines={l['line'] for l in logs})
    rows = []
    for lg in logs:
        ds = datetime.fromisoformat(lg['date']).replace(tzinfo=timezone.utc)
        down_min = clip_minutes(iv_map.get(lg['line'], []), ds, ds + timedelta(days=1))
        rows.append({**lg, **derive_day(lg.get('planned_hours'), down_min)})
    return rows


async def build_line_runtime_ctx(line):
    """Runtime context for the RELIABILITY engine (per-machine run-hour math).
    For each LOGGED day of the line: planned hours + live-derived breakdown
    downtime hours. Machines inherit max(planned − downtime, 0) as effective
    run hours; unlogged days keep the 24/7 fallback (applied by the caller)."""
    ctx = {'planned': {}, 'downtime_h': {}}
    if not line:
        return ctx
    logs = await db.line_runtime_logs.find({'line': line}, {'_id': 0, 'date': 1, 'planned_hours': 1}).to_list(100000)
    if not logs:
        return ctx
    ctx['planned'] = {str(l['date'])[:10]: float(l.get('planned_hours') or 0) for l in logs}
    dmin, dmax = min(ctx['planned']), max(ctx['planned'])
    from_dt = datetime.fromisoformat(dmin).replace(tzinfo=timezone.utc)
    to_dt = datetime.fromisoformat(dmax).replace(tzinfo=timezone.utc) + timedelta(days=1)
    iv_map = await load_line_breakdown_intervals(from_dt, to_dt, lines=[line])
    ivs = iv_map.get(line, [])
    for d in ctx['planned']:
        ds = datetime.fromisoformat(d).replace(tzinfo=timezone.utc)
        ctx['downtime_h'][d] = clip_minutes(ivs, ds, ds + timedelta(days=1)) / 60.0
    return ctx


async def compute_line_kpis(since, until):
    """Availability + downtime per line & per section over [since, until].
    Window Availability = (Σ planned − Σ downtime) ÷ Σ planned, where planned is
    prorated per day-overlap (24h fallback ONLY for unlogged days) and downtime
    is the live union-merged breakdown overlap. Clamped at 0% with a `clamped`
    flag when downtime exceeds planned.
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

    # planned-runtime logs inside the window (the ONE manual input per line-day)
    day0 = since.date()
    day_last = (until - timedelta(seconds=1)).date()
    date_list = []
    d = day0
    while d <= day_last:
        date_list.append(d.isoformat())
        d += timedelta(days=1)
    logged = {}
    async for lg in db.line_runtime_logs.find({'date': {'$in': date_list}}, {'_id': 0, 'line': 1, 'date': 1, 'planned_hours': 1}):
        logged[(lg['line'], lg['date'])] = float(lg.get('planned_hours') or 0)

    def day_overlap_minutes(date_str):
        ds = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        de = ds + timedelta(days=1)
        s, e = max(ds, since), min(de, until)
        return max((e - s).total_seconds() / 60.0, 0.0)

    def planned_minutes(line_name):
        """Σ planned minutes in the window: logged days use planned_hours prorated by
        day-overlap; UNLOGGED days fall back to 24/7 (full overlap) so live windows tick."""
        total = 0.0
        n_logged = 0
        for date_str in date_list:
            ov = day_overlap_minutes(date_str)
            if ov <= 0:
                continue
            key = (line_name, date_str)
            if key in logged:
                total += ov * (logged[key] / 24.0)
                n_logged += 1
            else:
                total += ov
        return total, n_logged

    # downtime is ALWAYS derived live from breakdowns (never manual, never warnings)
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

    def avail(down_min, planned_min):
        if planned_min <= 0:
            return None
        return round(max(0.0, (planned_min - down_min) / planned_min) * 100, 1)

    order = {'PC21': 0, 'PC32': 1, 'PC36': 2, 'KKR': 3, 'TWZ': 4, 'BCP': 5}
    out = []
    plant_down = 0.0
    plant_planned = 0.0
    for ln in lines.values():
        planned_min, n_logged = planned_minutes(ln['line'])
        sections = []
        for pg in ln['sections'].values():
            pg_down = min(merged_minutes(pg['intervals']), window_min)
            sections.append({
                'process_group': pg['process_group'], 'machines': pg['machines'],
                'downtime_minutes': round(pg_down, 1),
                'availability': avail(pg_down, planned_min),
            })
        sections.sort(key=lambda s: (-(s['downtime_minutes']), s['process_group']))
        ln_down = min(merged_minutes(ln['intervals']), window_min)
        plant_down += ln_down
        plant_planned += planned_min
        active_since = active_bd.get(ln['line'])
        out.append({
            'line': ln['line'], 'department': ln['department'], 'machines': ln['machines'],
            'running': ln['running'], 'failed': ln['failed'],
            'planned_minutes': round(planned_min, 1),
            'downtime_minutes': round(ln_down, 1),
            'availability': avail(ln_down, planned_min),
            'clamped': ln_down > planned_min + 1e-6,  # data-quality: downtime exceeds planned
            'logged_days': n_logged,
            'active_breakdown_since': active_since[0].isoformat() if active_since else None,
            'active_breakdown_id': active_since[1] if active_since else None,
            'active_breakdown_ticket': active_since[2] if active_since else None,
            'sections': sections,
        })
    out.sort(key=lambda x: (order.get(x['line'], 99), x['department'] or '', x['line']))
    plant_availability = avail(plant_down, plant_planned) if out else None
    return {'window_minutes': window_min, 'since': since_iso, 'until': until.isoformat(),
            'plant_availability': plant_availability, 'lines': out}
