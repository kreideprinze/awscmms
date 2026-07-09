"""POC test: core operational loop in isolation.
1. Login as admin (seeded users)
2. Open WebSocket connection
3. Create a breakdown via API
4. Verify: WS push received (machine_update + timeline + notification),
   timeline event persisted, notification persisted, machine status updated.
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE = 'http://localhost:8001/api'
WS_URL = 'ws://localhost:8001/api/ws'

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}: {name} {detail}")


async def main():
    async with httpx.AsyncClient(timeout=15) as http:
        # 1. Login
        r = await http.post(f'{BASE}/auth/login', json={'username': 'admin', 'password': 'admin123'})
        check('admin login', r.status_code == 200, str(r.status_code))
        token = r.json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        # bad login
        r = await http.post(f'{BASE}/auth/login', json={'username': 'admin', 'password': 'wrong'})
        check('bad login rejected', r.status_code == 401)

        # operator + tech login
        for u, p in [('tech', 'tech123'), ('operator', 'operator123')]:
            r = await http.post(f'{BASE}/auth/login', json={'username': u, 'password': p})
            check(f'{u} login', r.status_code == 200)

        # 2. Machines seeded (never empty)
        r = await http.get(f'{BASE}/machines', headers=headers)
        machines = r.json()
        check('machines seeded', len(machines) >= 3, f'{len(machines)} machines')
        target = machines[0]

        # unauthorized access blocked
        r = await http.get(f'{BASE}/machines')
        check('unauth blocked', r.status_code in (401, 403))

        # 3. WS connect + create breakdown
        received = []
        async with websockets.connect(f'{WS_URL}?token={token}') as ws:
            r = await http.post(f'{BASE}/breakdowns', headers=headers,
                                json={'machine_id': target['id'], 'description': 'Abnormal vibration near gearbox', 'failure_mode': 'Bearing Failure'})
            check('breakdown created', r.status_code == 200, r.json().get('ticket_number', ''))
            bd = r.json()

            # collect WS messages (expect machine_update, timeline_event, notification)
            try:
                for _ in range(3):
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    received.append(json.loads(msg))
            except asyncio.TimeoutError:
                pass

        types = {m['type'] for m in received}
        check('WS machine_update received', 'machine_update' in types, str(types))
        check('WS timeline_event received', 'timeline_event' in types)
        check('WS notification received', 'notification' in types)

        # 4. Persistence checks
        r = await http.get(f'{BASE}/timeline', headers=headers)
        tl = r.json()
        check('timeline persisted', any(e['reference_id'] == bd['id'] for e in tl))

        r = await http.get(f'{BASE}/notifications', headers=headers)
        nf = r.json()
        check('notification persisted', any(n['reference_id'] == bd['id'] for n in nf))

        r = await http.get(f'{BASE}/machines', headers=headers)
        m = next(x for x in r.json() if x['id'] == target['id'])
        check('machine status updated to failed', m['status'] == 'failed', m['status'])

        # WS auth: invalid token rejected
        try:
            async with websockets.connect(f'{WS_URL}?token=bogus') as ws2:
                await asyncio.wait_for(ws2.recv(), timeout=3)
            check('WS invalid token rejected', False, 'connection stayed open')
        except Exception:
            check('WS invalid token rejected', True)

    failed = [r for r in results if not r[1]]
    print(f"\n{'='*50}\nTOTAL: {len(results)}  PASS: {len(results)-len(failed)}  FAIL: {len(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    asyncio.run(main())
