"""Seed deterministic Weibull demo data so reliability calculations can be verified.

Creates for 3 machines (one per profile):
  - 320 days of historical runtime logs at exactly 20.0 run-hours/day
  - 8 CLOSED historical breakdowns whose Time-Between-Failures follow known
    Weibull(beta, eta) median-rank quantiles:
      * wear-out          beta = 3.0, eta = 700 h  (failures cluster with age)
      * random/constant   beta = 1.0, eta = 600 h  (exponential)
      * infant mortality  beta = 0.8, eta = 500 h  (early failures)
  - Triggers reliability recompute and prints fitted beta/eta vs expected.

Because TBFs are ideal median-rank samples, the MLE fit should recover the
target parameters closely — that is the verification.

Idempotent: machines already holding 'weibull_demo' breakdowns are skipped.
Run:  cd /app/backend && python seed_weibull_demo.py
"""
import asyncio
import math
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

from database import db  # noqa: E402
from events import next_counter, now_iso  # noqa: E402
from reliability import recompute_machine_reliability  # noqa: E402

DAILY_RUN_HOURS = 20.0
HISTORY_DAYS = 320
N_FAILURES = 8

PROFILES = [
    {'line': 'PC21', 'beta': 3.0, 'eta': 700.0, 'label': 'wear-out'},
    {'line': 'PC32', 'beta': 1.0, 'eta': 600.0, 'label': 'random'},
    {'line': 'KKR', 'beta': 0.8, 'eta': 500.0, 'label': 'infant-mortality'},
]


def weibull_tbfs(beta, eta, n):
    """Deterministic TBF sample at median ranks: p_i = (i-0.3)/(n+0.4)."""
    return [round(eta * (-math.log(1 - (i - 0.3) / (n + 0.4))) ** (1 / beta), 1) for i in range(1, n + 1)]


async def seed_machine(machine, beta, eta, label, start_date):
    tbfs = weibull_tbfs(beta, eta, N_FAILURES)
    print(f"\n{machine['name']} ({machine['line']}) — profile {label}: beta={beta} eta={eta}")
    print(f"  target TBFs (h): {tbfs}  (mean {round(sum(tbfs)/len(tbfs),1)})")

    # 1) historical runtime logs (skip dates that already have a log)
    existing = {l['date'] for l in await db.runtime_logs.find(
        {'machine_id': machine['id']}, {'_id': 0, 'date': 1}).to_list(100000)}
    logs = []
    for d in range(HISTORY_DAYS):
        date = (start_date + timedelta(days=d)).date().isoformat()
        if date in existing:
            continue
        logs.append({
            'id': str(uuid.uuid4()), 'machine_id': machine['id'], 'machine_name': machine['name'],
            'machine_code': machine.get('code'), 'department': machine['department'],
            'line': machine['line'], 'process_group': machine.get('process_group'),
            'date': date, 'calendar_hours': 24.0, 'run_hours': DAILY_RUN_HOURS,
            'dark_hours': 0.0, 'availability': round(DAILY_RUN_HOURS / 24.0 * 100, 1),
            'entered_by': 'weibull_demo', 'source': 'weibull_demo', 'created_at': now_iso(),
        })
    if logs:
        await db.runtime_logs.insert_many(logs)
    print(f"  runtime logs inserted: {len(logs)} ({HISTORY_DAYS} days @ {DAILY_RUN_HOURS}h/day)")

    # 2) commissioned_at anchors the first TBF interval
    await db.machines.update_one({'id': machine['id']}, {'$set': {'commissioned_at': start_date.isoformat()}})

    # 3) breakdowns at cumulative run-hour offsets
    cum_hours = 0.0
    created = []
    for i, tbf in enumerate(tbfs, start=1):
        cum_hours += tbf
        days_off = cum_hours / DAILY_RUN_HOURS
        start_dt = start_date + timedelta(days=days_off)
        end_dt = start_dt + timedelta(hours=3)
        ticket = await next_counter('breakdowns', 'BD')
        bd = {
            'id': str(uuid.uuid4()), 'ticket_number': ticket,
            'machine_id': machine['id'], 'machine_name': machine['name'],
            'department': machine['department'], 'line': machine['line'],
            'process_group': machine.get('process_group'),
            'failure_mode': 'Bearing Failure' if label == 'wear-out' else ('Electrical Trip' if label == 'random' else 'Seal Leak'),
            'breakdown_type': 'MECHANICAL' if label != 'random' else 'ELECTRICAL',
            'description': f'[Weibull demo #{i}] Historical failure ({label} profile)',
            'reporter': 'weibull_demo', 'status': 'CLOSED', 'assigned_to': 'tech',
            'start_time': start_dt.isoformat(), 'end_time': end_dt.isoformat(),
            'downtime_minutes': 180.0, 'repair_duration_minutes': 150.0,
            'root_cause': f'Demo seeded failure ({label})', 'action_taken': 'Component replaced',
            'consumed_spares': [], 'rca_task_id': None, 'work_order_id': None,
            'source': 'weibull_demo', 'created_at': now_iso(),
        }
        await db.breakdowns.insert_one(bd)
        created.append(ticket)
    print(f"  breakdowns inserted: {', '.join(created)}")

    # 4) recompute + report fitted vs expected
    await recompute_machine_reliability(machine['id'], trigger='weibull_demo_seed')
    metrics = await db.reliability_metrics.find_one({'machine_id': machine['id']}, {'_id': 0})
    w = (metrics or {}).get('weibull')
    mean_expected = round(eta * math.gamma(1 + 1 / beta), 1)
    if w:
        print(f"  FITTED  : beta={w['beta']}  eta={w['eta']}  mean_life={w['mean_life']}h  b10={w['b10_life']}h")
        print(f"  EXPECTED: beta={beta}  eta={eta}  mean_life~{mean_expected}h")
        print(f"  MTBF={metrics.get('mtbf')}h  level={metrics.get('maturity_level')}  n={metrics.get('failure_count')}")
    else:
        print(f"  !! no weibull fit produced — metrics: {metrics}")


async def main():
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=HISTORY_DAYS + 5)).replace(hour=6, minute=0, second=0, microsecond=0)
    for profile in PROFILES:
        machine = await db.machines.find_one(
            {'line': profile['line'], 'status': {'$ne': 'failed'}}, {'_id': 0}, sort=[('code', 1)])
        if not machine:
            print(f"no machine found on line {profile['line']} — skipped")
            continue
        already = await db.breakdowns.count_documents({'machine_id': machine['id'], 'source': 'weibull_demo'})
        if already:
            print(f"{machine['name']} ({profile['line']}) already has {already} demo breakdowns — skipped")
            continue
        await seed_machine(machine, profile['beta'], profile['eta'], profile['label'], start_date)
    print('\nWeibull demo seed complete.')


if __name__ == '__main__':
    asyncio.run(main())
