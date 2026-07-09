"""Reliability Engine (AWS - Advance Warning System) + Predictive Maintenance Engine.
Statistical reliability engineering - NOT AI/ML.
Calculations begin immediately after the first recorded breakdown.

Maturity model:
  Level 1 (1 failure)   -> MTBF + operating hours since failure
  Level 2 (2-4 failures)-> Rolling MTBF, Weighted MTBF, Failure Trend
  Level 3 (5+ failures) -> Weibull, Hazard Rate, Reliability Curve, Failure Probability

Prediction tiers: Initial=MTBF, Intermediate=Weighted MTBF, Advanced=Weibull mean life.
Health: Healthy 0-70%, Watch 70-80%, Inspection Due 80-100%, Overdue 100%+.
At >=80%: Inspection Recommended flag + Notification + Suggested PM Task.
"""
import logging
import math
import uuid
from datetime import datetime, timezone

from database import db
from events import create_notification, create_timeline_event, broadcast_machine_update, now_iso

logger = logging.getLogger(__name__)

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
}
DEFAULT_SUGGESTIONS = ['Inspect Bearings', 'Check Gearbox', 'Lubricate Chain', 'Verify Alignment', 'Check Vibration']


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


async def run_hours_between(machine_id, start_dt, end_dt):
    """Operating hours between two datetimes from runtime_logs; fallback to calendar hours."""
    q = {'machine_id': machine_id}
    logs = await db.runtime_logs.find(q, {'_id': 0}).to_list(100000)
    if logs:
        total = 0.0
        for lg in logs:
            d = parse_dt(lg.get('date'))
            if d and (start_dt is None or d >= start_dt) and (end_dt is None or d <= end_dt):
                total += float(lg.get('run_hours', 0))
        return total
    # fallback: calendar elapsed hours
    if start_dt and end_dt:
        return max((end_dt - start_dt).total_seconds() / 3600.0, 0.0)
    return 0.0


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


async def recompute_machine_reliability(machine_id, trigger='manual'):
    """Full recompute of reliability metrics + predictive health for one machine."""
    machine = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not machine:
        return None

    settings = await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0}) or {}
    alert_pct = settings.get('alert_trigger_pct', 80)

    # failures = breakdowns that reached COMPLETED/CLOSED (repairs done) plus open FAILED ones count as events too
    failures = await db.breakdowns.find(
        {'machine_id': machine_id}, {'_id': 0}
    ).sort('start_time', 1).to_list(10000)

    n = len(failures)
    now = datetime.now(timezone.utc)

    if n == 0:
        await db.reliability_metrics.delete_many({'machine_id': machine_id})
        await db.machines.update_one({'id': machine_id}, {'$set': {'reliability_state': 'no_data', 'health': 'healthy', 'inspection_recommended': False}})
        return None

    commissioned = parse_dt(machine.get('commissioned_at')) or parse_dt(machine.get('created_at'))

    # Time Between Failures list (operating hours)
    tbfs = []
    prev = commissioned
    for f in failures:
        f_start = parse_dt(f.get('start_time'))
        if not f_start:
            continue
        hours = await run_hours_between(machine_id, prev, f_start)
        tbfs.append(max(hours, 0.1))
        prev = parse_dt(f.get('end_time')) or f_start

    if not tbfs:
        return None

    # MTTR from closed breakdowns
    repaired = [f for f in failures if f.get('downtime_minutes') is not None]
    mttr_hours = round(sum(f['downtime_minutes'] for f in repaired) / len(repaired) / 60.0, 2) if repaired else None

    mtbf = round(sum(tbfs) / len(tbfs), 2)

    # maturity level
    l2 = settings.get('level2_min_failures', 2)
    l3 = settings.get('level3_min_failures', 5)
    level = 1 if n < l2 else (2 if n < l3 else 3)

    rolling_mtbf = None
    weighted_mtbf = None
    trend = None
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
    hazard_rate = None
    reliability_now = None
    failure_probability = None
    if level >= 3:
        fit = weibull_fit(tbfs)
        if fit:
            beta, eta = fit
            mean_life = round(eta * math.gamma(1 + 1 / beta), 2)
            b10 = round(eta * (-math.log(0.9)) ** (1 / beta), 2)
            weibull = {'beta': beta, 'eta': eta, 'mean_life': mean_life, 'b10_life': b10}
            await db.weibull_models.insert_one({
                'id': str(uuid.uuid4()), 'machine_id': machine_id, 'machine_name': machine['name'],
                'beta': beta, 'eta': eta, 'mean_life': mean_life, 'b10_life': b10,
                'failures_used': n, 'fitted_at': now_iso(),
            })

    # hours since last failure (operating hours)
    last_failure = failures[-1]
    last_end = parse_dt(last_failure.get('end_time')) or parse_dt(last_failure.get('start_time'))
    hours_since = await run_hours_between(machine_id, last_end, now)

    # prediction tier
    if weibull:
        predicted_life = weibull['mean_life']
        tier = 'advanced'
    elif weighted_mtbf:
        predicted_life = weighted_mtbf
        tier = 'intermediate'
    else:
        predicted_life = mtbf
        tier = 'initial'

    life_pct = round(hours_since / predicted_life * 100, 1) if predicted_life and predicted_life > 0 else 0

    if weibull and predicted_life:
        t = max(hours_since, 0.1)
        beta, eta = weibull['beta'], weibull['eta']
        reliability_now = round(math.exp(-((t / eta) ** beta)), 4)
        failure_probability = round(1 - reliability_now, 4)
        hazard_rate = round((beta / eta) * ((t / eta) ** (beta - 1)), 6)

    # health state
    if life_pct < settings.get('healthy_threshold_pct', 70):
        health = 'healthy'
    elif life_pct < settings.get('watch_threshold_pct', 80):
        health = 'watch'
    elif life_pct < settings.get('inspection_threshold_pct', 100):
        health = 'inspection_due'
    else:
        health = 'overdue'

    alert_cycle = f"{last_failure['id']}"  # one alert per failure cycle
    existing = await db.reliability_metrics.find_one({'machine_id': machine_id}, {'_id': 0})
    alert_already_sent = existing and existing.get('alert_cycle_sent') == alert_cycle

    metrics = {
        'machine_id': machine_id,
        'machine_name': machine['name'],
        'department': machine.get('department'),
        'line': machine.get('line'),
        'process_group': machine.get('process_group'),
        'criticality': machine.get('criticality'),
        'failures_count': n,
        'level': level,
        'tier': tier,
        'mtbf': mtbf,
        'mttr_hours': mttr_hours,
        'rolling_mtbf': rolling_mtbf,
        'weighted_mtbf': weighted_mtbf,
        'trend': trend,
        'weibull': weibull,
        'hazard_rate': hazard_rate,
        'reliability_now': reliability_now,
        'failure_probability': failure_probability,
        'predicted_failure_life': predicted_life,
        'hours_since_last_failure': round(hours_since, 2),
        'life_pct': life_pct,
        'health': health,
        'tbf_history': [round(t, 2) for t in tbfs],
        'alert_cycle_sent': existing.get('alert_cycle_sent') if existing else None,
        'last_computed': now_iso(),
        'last_trigger': trigger,
    }

    await db.reliability_metrics.update_one({'machine_id': machine_id}, {'$set': metrics}, upsert=True)

    # update machine derived fields
    update = {'health': health, 'reliability_state': f'level_{level}'}
    # only shift operational status for health if machine is in a normal state
    if machine.get('status') in ('running', 'watch', 'inspection_due'):
        if health == 'watch':
            update['status'] = 'watch'
        elif health in ('inspection_due', 'overdue'):
            update['status'] = 'inspection_due'
        elif health == 'healthy' and machine.get('status') in ('watch', 'inspection_due'):
            update['status'] = 'running'
    await db.machines.update_one({'id': machine_id}, {'$set': update})
    machine.update(update)
    await broadcast_machine_update(machine)

    # ---------- Predictive alerts at >= alert_pct ----------
    if life_pct >= alert_pct and not alert_already_sent:
        await db.reliability_metrics.update_one({'machine_id': machine_id}, {'$set': {'alert_cycle_sent': alert_cycle}})
        await db.machines.update_one({'id': machine_id}, {'$set': {'inspection_recommended': True}})

        # suggested actions from failure history
        mode_counts = {}
        for f in failures:
            fm = f.get('failure_mode')
            if fm:
                mode_counts[fm] = mode_counts.get(fm, 0) + 1
        top_modes = sorted(mode_counts, key=mode_counts.get, reverse=True)[:3]
        suggestions = [PM_SUGGESTIONS.get(m) for m in top_modes if PM_SUGGESTIONS.get(m)]
        if not suggestions:
            suggestions = DEFAULT_SUGGESTIONS[:3]

        # Suggested PM task
        pm_task = {
            'id': str(uuid.uuid4()),
            'task_name': f"Predictive Inspection \u2014 {machine['name']}",
            'description': f"Auto-generated: machine at {life_pct}% of predicted failure life ({predicted_life}h {tier} tier). Suggested: {', '.join(suggestions)}.",
            'priority': 'high',
            'machine_id': machine_id, 'machine_name': machine['name'],
            'department': machine.get('department'), 'line': machine.get('line'),
            'assigned_to': None, 'frequency': 'once',
            'checklist': suggestions,
            'reminder_offset_days': 0,
            'status': 'suggested', 'source': 'predictive', 'auto_generated': True,
            'active': True, 'next_due_date': now_iso()[:10],
            'created_at': now_iso(),
        }
        await db.pm_tasks.insert_one(dict(pm_task))

        await create_notification('inspection_recommended', f"Inspection Recommended: {machine['name']}",
                                  f"{machine['name']} ({machine.get('line')}) is at {life_pct}% of predicted failure life ({predicted_life:.0f}h). Suggested: {', '.join(suggestions)}",
                                  severity='warning', machine_id=machine_id, machine_name=machine['name'],
                                  reference_id=pm_task['id'], reference_type='pm_task')
        await create_timeline_event('reliability_alert', machine_id=machine_id, machine_name=machine['name'],
                                    title=f"Reliability alert: {life_pct}% of predicted life",
                                    description=f"Predicted failure life {predicted_life:.0f}h ({tier} tier). Suggested PM task created.",
                                    user='system', reference_id=pm_task['id'], reference_type='pm_task',
                                    department=machine.get('department'), line=machine.get('line'))
    return metrics


async def recompute_all(trigger='batch'):
    ids = await db.breakdowns.distinct('machine_id')
    for mid in ids:
        try:
            await recompute_machine_reliability(mid, trigger=trigger)
        except Exception as e:
            logger.error(f'reliability recompute failed for {mid}: {e}')
