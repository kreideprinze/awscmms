"""Reliability Engine (AWS - Advance Warning System) + Predictive Maintenance Engine.
Statistical reliability engineering - NOT AI/ML.

PER-CATEGORY HEALTH POOLS — each machine tracks THREE independent reliability pools,
aligned with the Breakdown Type field, so each maintenance discipline monitors its own
failure category without cross-contamination:
    • MECHANICAL
    • ELECTRICAL
    • CONTROL_PLC

Maturity model (per category):
  Level 1 (1 failure)   -> MTBF + operating hours since failure
  Level 2 (2-4 failures)-> Rolling MTBF, Weighted MTBF, Failure Trend
  Level 3 (5+ failures) -> Weibull, Hazard Rate, Reliability Curve, Failure Probability

Prediction tiers: Initial=MTBF, Intermediate=Weighted MTBF, Advanced=Weibull mean life.
Health: Healthy 0-70%, Watch 70-80%, Inspection Due 80-100%, Overdue 100%+.

PREDICTIVE WORK ORDERS (admin-configurable threshold, default 80%):
  At >= predictive_trigger_pct of predicted life a category auto-creates ONE
  'Predictive' work order (UNASSIGNED — any technician can claim it).
  • Closing that Predictive WO resets the category pool to 0% (aws_resets anchor).
  • A breakdown in the category while the Predictive WO is outstanding cancels it
    (handled in routers_maintenance) and the pool restarts from the new failure.
"""
import logging
import math
import uuid
from datetime import datetime, timezone, timedelta

from database import db
from events import create_notification, create_timeline_event, broadcast_machine_update, next_counter, now_iso

logger = logging.getLogger(__name__)

CATEGORIES = ['MECHANICAL', 'ELECTRICAL', 'CONTROL_PLC']
CATEGORY_LABELS = {'MECHANICAL': 'Mechanical', 'ELECTRICAL': 'Electrical', 'CONTROL_PLC': 'PLC / Control'}
HEALTH_RANK = {'healthy': 0, 'watch': 1, 'inspection_due': 2, 'overdue': 3}

PM_SUGGESTIONS = {
    'Bearing Failure': 'Inspect Bearings',
    'Belt Failure': 'Check Belt Tension & Wear',
    'Chain Failure': 'Lubricate & Inspect Chain',
    'Gearbox Failure': 'Check Gearbox Oil & Condition',
    'Motor Failure': 'Check Motor Current & Insulation',
    'Seal Leakage': 'Inspect Mechanical Seals',
    'Shaft Misalignment': 'Verify Alignment',
    'Excessive Vibration': 'Check Vibration Levels',
    'Overheating': 'Check Cooling & Temperature',
    'Lubrication Failure': 'Verify Lubrication Schedule',
    'Coupling Failure': 'Inspect Couplings',
    'Electrical Fault': 'Inspect Panel & Connections',
    'Sensor Failure': 'Test & Calibrate Sensors',
    'VFD / Drive Fault': 'Check Drive Parameters & Cooling',
    'Instrumentation Fault': 'Verify Instrument Loop',
}
DEFAULT_SUGGESTIONS = {
    'MECHANICAL': ['Inspect Bearings', 'Check Gearbox', 'Lubricate Chain', 'Verify Alignment'],
    'ELECTRICAL': ['Thermal-scan Panel', 'Check Motor Current', 'Inspect Cable Glands'],
    'CONTROL_PLC': ['Test Sensors & I/O', 'Verify PLC Battery & Backups', 'Check Comms / Network'],
}


def parse_dt(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def run_hours_between(start_dt, end_dt, ctx=None):
    """Operating hours between two datetimes — PLANNED-RUNTIME single source of
    truth (same model as kpi_engine):
      • For each calendar day overlapping [start_dt, end_dt]:
          - if a PLANNED line-runtime log exists for that day, the effective run
            hours are max(planned − derived line breakdown downtime, 0), prorated
            by the fraction of that day inside the range and capped at the
            elapsed overlap;
          - otherwise the plant is assumed to run continuously (24/7), so the
            full calendar overlap counts as run time.
    `ctx` comes from kpi_engine.build_line_runtime_ctx(line):
      {'planned': {date: hours}, 'downtime_h': {date: hours}}.
    This makes 'hours since failure' (and therefore AWS Life %) tick in real
    time instead of freezing at 0 until the next end-of-day log."""
    if start_dt is None or end_dt is None or end_dt <= start_dt:
        return 0.0
    planned_map = (ctx or {}).get('planned') or {}
    downtime_map = (ctx or {}).get('downtime_h') or {}
    total = 0.0
    day = start_dt.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end_dt:
        day_end = day + timedelta(days=1)
        o_start = max(day, start_dt)
        o_end = min(day_end, end_dt)
        overlap_h = max((o_end - o_start).total_seconds() / 3600.0, 0.0)
        if overlap_h > 0:
            key = day.date().isoformat()
            if key in planned_map:
                eff_run = max(planned_map[key] - downtime_map.get(key, 0.0), 0.0)
                total += min(eff_run * (overlap_h / 24.0), overlap_h)
            else:
                total += overlap_h
        day = day_end
    return total


def weibull_fit(tbfs):
    """2-parameter Weibull MLE fit. Returns (beta, eta) or None."""
    try:
        from scipy import stats
        clean = [max(float(t), 0.1) for t in tbfs]
        beta, loc, eta = stats.weibull_min.fit(clean, floc=0)
        if not (0.05 < beta < 20) or eta <= 0:
            return None
        return round(beta, 4), round(eta, 2)
    except Exception as e:
        logger.warning(f'Weibull fit failed: {e}')
        return None


async def _compute_category(machine, cat, failures, settings, runtime_ctx, now):
    """Compute one category's reliability pool. Returns dict or None."""
    machine_id = machine['id']
    commissioned = parse_dt(machine.get('commissioned_at')) or parse_dt(machine.get('created_at'))

    tbfs = []
    prev = commissioned
    for f in failures:
        f_start = parse_dt(f.get('start_time'))
        if not f_start:
            continue
        hours = run_hours_between(prev, f_start, ctx=runtime_ctx)
        tbfs.append(max(hours, 0.1))
        prev = parse_dt(f.get('end_time')) or f_start
    if not tbfs:
        return None

    n = len(failures)
    repaired = [f for f in failures if f.get('downtime_minutes') is not None]
    mttr_hours = round(sum(f['downtime_minutes'] for f in repaired) / len(repaired) / 60.0, 2) if repaired else None
    mtbf = round(sum(tbfs) / len(tbfs), 2)

    l2 = settings.get('level2_min_failures', 2)
    l3 = settings.get('level3_min_failures', 5)
    level = 1 if n < l2 else (2 if n < l3 else 3)

    rolling_mtbf = weighted_mtbf = trend = None
    if level >= 2:
        window = settings.get('rolling_window', 3)
        rolling_mtbf = round(sum(tbfs[-window:]) / len(tbfs[-window:]), 2)
        weights = list(range(1, len(tbfs) + 1))
        weighted_mtbf = round(sum(t * w for t, w in zip(tbfs, weights)) / sum(weights), 2)
        half = max(len(tbfs) // 2, 1)
        older, recent = tbfs[:half], tbfs[half:]
        if recent and older:
            ratio = (sum(recent) / len(recent)) / max(sum(older) / len(older), 0.01)
            trend = 'improving' if ratio > 1.15 else ('degrading' if ratio < 0.85 else 'stable')

    weibull = None
    if level >= 3:
        fit = weibull_fit(tbfs)
        if fit:
            beta, eta = fit
            mean_life = round(eta * math.gamma(1 + 1 / beta), 2)
            b10 = round(eta * (-math.log(0.9)) ** (1 / beta), 2)
            weibull = {'beta': beta, 'eta': eta, 'mean_life': mean_life, 'b10_life': b10}
            await db.weibull_models.insert_one({
                'id': str(uuid.uuid4()), 'machine_id': machine_id, 'machine_name': machine['name'],
                'category': cat, 'beta': beta, 'eta': eta, 'mean_life': mean_life, 'b10_life': b10,
                'failures_used': n, 'fitted_at': now_iso(),
            })

    # ---- Pool anchor: last failure end OR AWS reset (Predictive WO closed), whichever is later
    last_failure = failures[-1]
    last_end = parse_dt(last_failure.get('end_time')) or parse_dt(last_failure.get('start_time'))
    reset_iso = (machine.get('aws_resets') or {}).get(cat)
    reset_at = parse_dt(reset_iso)
    anchor = max([d for d in (last_end, reset_at) if d], default=None)
    hours_since = run_hours_between(anchor, now, ctx=runtime_ctx)

    if weibull:
        predicted_life, tier = weibull['mean_life'], 'advanced'
    elif weighted_mtbf:
        predicted_life, tier = weighted_mtbf, 'intermediate'
    else:
        predicted_life, tier = mtbf, 'initial'

    life_pct = round(hours_since / predicted_life * 100, 1) if predicted_life and predicted_life > 0 else 0

    reliability_now = failure_probability = hazard_rate = None
    if weibull and predicted_life:
        t = max(hours_since, 0.1)
        beta, eta = weibull['beta'], weibull['eta']
        reliability_now = round(math.exp(-((t / eta) ** beta)), 4)
        failure_probability = round(1 - reliability_now, 4)
        hazard_rate = round((beta / eta) * ((t / eta) ** (beta - 1)), 6)

    if life_pct < settings.get('healthy_threshold_pct', 70):
        health = 'healthy'
    elif life_pct < settings.get('watch_threshold_pct', 80):
        health = 'watch'
    elif life_pct < settings.get('inspection_threshold_pct', 100):
        health = 'inspection_due'
    else:
        health = 'overdue'

    # cycle key: one predictive alert per (last failure, reset anchor) cycle
    cycle_key = f"{last_failure['id']}:{reset_iso or ''}"

    # suggestions from this category's failure history
    mode_counts = {}
    for f in failures:
        fm = f.get('failure_mode')
        if fm:
            mode_counts[fm] = mode_counts.get(fm, 0) + 1
    top_modes = sorted(mode_counts, key=mode_counts.get, reverse=True)[:3]
    suggestions = [PM_SUGGESTIONS[m] for m in top_modes if m in PM_SUGGESTIONS]
    if not suggestions:
        suggestions = DEFAULT_SUGGESTIONS.get(cat, [])[:3]

    return {
        'category': cat, 'label': CATEGORY_LABELS.get(cat, cat),
        'failures_count': n, 'level': level, 'tier': tier,
        'mtbf': mtbf, 'mttr_hours': mttr_hours,
        'rolling_mtbf': rolling_mtbf, 'weighted_mtbf': weighted_mtbf, 'trend': trend,
        'weibull': weibull, 'hazard_rate': hazard_rate,
        'reliability_now': reliability_now, 'failure_probability': failure_probability,
        'predicted_failure_life': predicted_life,
        'hours_since_last_failure': round(hours_since, 2),
        'life_pct': life_pct, 'health': health,
        'tbf_history': [round(t, 2) for t in tbfs],
        'reset_at': reset_iso, 'cycle_key': cycle_key, 'suggestions': suggestions,
    }


async def _ensure_predictive_wo(machine, cat_metrics, trigger_pct, existing_metric):
    """Create ONE Predictive WO per category cycle when the pool crosses the threshold.
    Returns the outstanding predictive WO id (existing or new) or None."""
    cat = cat_metrics['category']
    # outstanding predictive WO for this machine+category?
    open_wo = await db.work_orders.find_one(
        {'machine_id': machine['id'], 'wo_type': 'Predictive', 'aws_category': cat,
         'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_ADMIN_CLOSURE']}},
        {'_id': 0, 'id': 1, 'wo_number': 1})
    if open_wo:
        return open_wo['id']
    if cat_metrics['life_pct'] < trigger_pct:
        return None
    sent_cycles = (existing_metric or {}).get('alert_cycles') or {}
    if sent_cycles.get(cat) == cat_metrics['cycle_key']:
        return None  # already alerted this cycle (WO may have been cancelled by a breakdown)

    life_pct = cat_metrics['life_pct']
    predicted_life = cat_metrics['predicted_failure_life']
    tier = cat_metrics['tier']
    suggestions = cat_metrics['suggestions']
    wo_num = await next_counter('work_orders', 'WO')
    wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': 'Predictive',
        'title': f"Predictive \u2014 {machine['name']} [{CATEGORY_LABELS.get(cat, cat)}]",
        'description': (f"eWACS-90 auto-generated: {CATEGORY_LABELS.get(cat, cat)} pool at {life_pct}% of predicted "
                        f"failure life ({predicted_life:.0f}h, {tier} tier, threshold {trigger_pct:.0f}%). "
                        f"Suggested: {', '.join(suggestions) or 'inspection'}."),
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine.get('department'), 'line': machine.get('line'),
        'assigned_to': None, 'priority': 'high', 'status': 'OPEN',
        'aws_category': cat, 'aws_life_pct': life_pct,
        'root_cause': None, 'action_taken': None, 'spare_parts': [],
        'duration_minutes': None, 'source': 'aws_predictive', 'auto_generated': True,
        'created_at': now_iso(),
    }
    await db.work_orders.insert_one(dict(wo))
    await db.reliability_metrics.update_one({'machine_id': machine['id']},
                                            {'$set': {f'alert_cycles.{cat}': cat_metrics['cycle_key']}}, upsert=True)
    await create_notification('inspection_recommended', f"Predictive WO: {machine['name']} [{CATEGORY_LABELS.get(cat, cat)}]",
                              f"{wo_num} \u2014 {CATEGORY_LABELS.get(cat, cat)} pool at {life_pct}% of predicted life ({predicted_life:.0f}h). "
                              f"Suggested: {', '.join(suggestions)}",
                              severity='warning', machine_id=machine['id'], machine_name=machine['name'],
                              reference_id=wo['id'], reference_type='work_order')
    await create_timeline_event('reliability_alert', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"eWACS-90 alert [{CATEGORY_LABELS.get(cat, cat)}]: {life_pct}% \u2014 Predictive WO {wo_num} created",
                                description=f"Predicted failure life {predicted_life:.0f}h ({tier} tier). Unassigned \u2014 claimable by any technician.",
                                user='system', reference_id=wo['id'], reference_type='work_order',
                                department=machine.get('department'), line=machine.get('line'))
    return wo['id']


async def create_manual_predictive_wo(machine_id, category, username):
    """MANUAL eWACS-90 work order — identical in shape/behavior to the auto-generated
    Predictive WO, but triggered on demand by an admin/technician regardless of threshold."""
    machine = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not machine:
        return {'error': 'Machine not found'}
    if category not in CATEGORY_LABELS:
        return {'error': f'Invalid category. Valid: {list(CATEGORY_LABELS)}'}
    open_wo = await db.work_orders.find_one(
        {'machine_id': machine_id, 'wo_type': 'Predictive', 'aws_category': category,
         'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_ADMIN_CLOSURE']}},
        {'_id': 0, 'wo_number': 1})
    if open_wo:
        return {'error': f"An open eWACS-90 WO already exists for this machine/category ({open_wo['wo_number']})"}
    cm = ((await db.reliability_metrics.find_one({'machine_id': machine_id}, {'_id': 0}) or {})
          .get('categories') or {}).get(category) or {}
    life_pct = cm.get('life_pct', 0)
    predicted_life = cm.get('predicted_failure_life') or 0
    tier = cm.get('tier', 'initial')
    suggestions = cm.get('suggestions') or []
    label = CATEGORY_LABELS.get(category, category)
    wo_num = await next_counter('work_orders', 'WO')
    wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': 'Predictive',
        'title': f"Predictive \u2014 {machine['name']} [{label}]",
        'description': (f"eWACS-90 manual request by {username}: {label} pool at {life_pct}% of predicted "
                        f"failure life ({predicted_life:.0f}h, {tier} tier). "
                        f"Suggested: {', '.join(suggestions) or 'inspection'}."),
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine.get('department'), 'line': machine.get('line'),
        'assigned_to': None, 'priority': 'high', 'status': 'OPEN',
        'aws_category': category, 'aws_life_pct': life_pct,
        'root_cause': None, 'action_taken': None, 'spare_parts': [],
        'duration_minutes': None, 'source': 'aws_predictive', 'auto_generated': False,
        'created_by': username, 'created_at': now_iso(),
    }
    await db.work_orders.insert_one(dict(wo))
    await create_notification('inspection_recommended', f"Predictive WO: {machine['name']} [{label}]",
                              f"{wo_num} \u2014 manually generated from eWACS-90 by {username} ({label} pool at {life_pct}%).",
                              severity='warning', machine_id=machine['id'], machine_name=machine['name'],
                              reference_id=wo['id'], reference_type='work_order')
    await create_timeline_event('reliability_alert', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"eWACS-90 manual WO [{label}]: Predictive WO {wo_num} created by {username}",
                                description=f"Pool at {life_pct}% of predicted life ({predicted_life:.0f}h, {tier} tier). Unassigned \u2014 claimable by any technician.",
                                user=username, reference_id=wo['id'], reference_type='work_order',
                                department=machine.get('department'), line=machine.get('line'))
    wo.pop('_id', None)
    return wo


async def recompute_machine_reliability(machine_id, trigger='manual'):
    """Full recompute of per-category reliability pools + predictive triggers for one machine."""
    machine = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not machine:
        return None

    settings = await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0}) or {}
    trigger_pct = settings.get('predictive_trigger_pct', settings.get('alert_trigger_pct', 80))

    all_failures = await db.breakdowns.find({'machine_id': machine_id}, {'_id': 0}).sort('start_time', 1).to_list(10000)
    now = datetime.now(timezone.utc)

    if not all_failures:
        await db.reliability_metrics.delete_many({'machine_id': machine_id})
        await db.machines.update_one({'id': machine_id}, {'$set': {'reliability_state': 'no_data', 'health': 'healthy', 'inspection_recommended': False}})
        return None

    # Planned-runtime context for this machine's LINE (machines inherit line runtime):
    # logged days → max(planned − derived breakdown downtime, 0); unlogged → 24/7.
    from kpi_engine import build_line_runtime_ctx
    runtime_ctx = await build_line_runtime_ctx(machine.get('line'))
    existing = await db.reliability_metrics.find_one({'machine_id': machine_id}, {'_id': 0})

    categories = {}
    for cat in CATEGORIES:
        failures = [f for f in all_failures if (f.get('breakdown_type') or 'MECHANICAL') == cat]
        if not failures:
            continue
        c = await _compute_category(machine, cat, failures, settings, runtime_ctx, now)
        if c:
            categories[cat] = c

    if not categories:
        return None

    # Predictive WO management per category
    for cat, c in categories.items():
        c['predictive_wo_id'] = await _ensure_predictive_wo(machine, c, trigger_pct, existing)

    # driving category = riskiest pool (highest life %)
    driving_cat = max(categories, key=lambda c: categories[c]['life_pct'])
    d = categories[driving_cat]
    worst_health = max((c['health'] for c in categories.values()), key=lambda h: HEALTH_RANK.get(h, 0))
    max_level = max(c['level'] for c in categories.values())

    metrics = {
        'machine_id': machine_id,
        'machine_name': machine['name'],
        'department': machine.get('department'),
        'line': machine.get('line'),
        'process_group': machine.get('process_group'),
        'criticality': machine.get('criticality'),
        # top-level fields mirror the DRIVING (riskiest) category for at-a-glance sorting
        'driving_category': driving_cat,
        'failures_count': len(all_failures),
        'level': max_level,
        'tier': d['tier'],
        'mtbf': d['mtbf'],
        'mttr_hours': d['mttr_hours'],
        'rolling_mtbf': d['rolling_mtbf'],
        'weighted_mtbf': d['weighted_mtbf'],
        'trend': d['trend'],
        'weibull': d['weibull'],
        'hazard_rate': d['hazard_rate'],
        'reliability_now': d['reliability_now'],
        'failure_probability': d['failure_probability'],
        'predicted_failure_life': d['predicted_failure_life'],
        'hours_since_last_failure': d['hours_since_last_failure'],
        'life_pct': d['life_pct'],
        'health': worst_health,
        'tbf_history': d['tbf_history'],
        'categories': {k: {kk: vv for kk, vv in v.items() if kk not in ('cycle_key',)} for k, v in categories.items()},
        'predictive_trigger_pct': trigger_pct,
        'last_computed': now_iso(),
        'last_trigger': trigger,
    }
    await db.reliability_metrics.update_one({'machine_id': machine_id}, {'$set': metrics}, upsert=True)

    # update machine derived fields — overall health is the WORST category pool
    update = {'health': worst_health, 'reliability_state': f'level_{max_level}',
              'inspection_recommended': any(c['life_pct'] >= trigger_pct for c in categories.values())}
    if machine.get('status') in ('running', 'watch', 'inspection_due'):
        if worst_health == 'watch':
            update['status'] = 'watch'
        elif worst_health in ('inspection_due', 'overdue'):
            update['status'] = 'inspection_due'
        elif worst_health == 'healthy' and machine.get('status') in ('watch', 'inspection_due'):
            update['status'] = 'running'
    await db.machines.update_one({'id': machine_id}, {'$set': update})
    machine.update(update)
    await broadcast_machine_update(machine)
    return metrics


async def recompute_all(trigger='batch'):
    ids = await db.breakdowns.distinct('machine_id')
    for mid in ids:
        try:
            await recompute_machine_reliability(mid, trigger=trigger)
        except Exception as e:
            logger.error(f'reliability recompute failed for {mid}: {e}')
