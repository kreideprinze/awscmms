"""Test warnings system and WO lifecycle changes.
Tests:
1. POST /api/warnings (authenticated) - creates warning WRN-xxx, machine status becomes 'watch', WO auto-created
2. POST /api/public/warnings (no auth) - public warning submission
3. GET /api/warnings - list warnings
4. WO lifecycle: tech complete -> PENDING_ADMIN_CLOSURE, admin close -> CLOSED, tech close -> 403
5. POST /api/breakdowns as operator - forces auto_create_work_order=true
6. Admin closing warning-sourced WO restores machine from watch to running
"""
import asyncio
import sys
import httpx

BASE = 'https://content-extractor-75.preview.emergentagent.com/api'

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    status = 'PASS' if ok else 'FAIL'
    print(f"{status}: {name} {detail}")


async def main():
    async with httpx.AsyncClient(timeout=30) as http:
        # 1. Login as admin
        r = await http.post(f'{BASE}/auth/login', json={'username': 'admin', 'password': 'admin123'})
        check('admin login', r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"Login failed: {r.text}")
            sys.exit(1)
        admin_token = r.json()['token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}

        # 2. Login as tech user
        r = await http.post(f'{BASE}/auth/login', json={'username': 'tech', 'password': 'tech123'})
        check('tech login', r.status_code == 200)
        tech_token = r.json()['token']
        tech_headers = {'Authorization': f'Bearer {tech_token}'}

        # 3. Login as operator
        r = await http.post(f'{BASE}/auth/login', json={'username': 'operator', 'password': 'operator123'})
        check('operator login', r.status_code == 200)
        operator_token = r.json()['token']
        operator_headers = {'Authorization': f'Bearer {operator_token}'}

        # Get a running machine for testing
        r = await http.get(f'{BASE}/machines?limit=1', headers=admin_headers)
        check('get machines', r.status_code == 200)
        machines = r.json()
        if not machines:
            print("No machines found")
            sys.exit(1)
        machine_id = machines[0]['id']
        machine_name = machines[0]['name']
        print(f"Using machine: {machine_name} ({machine_id})")

        # Ensure machine is running before warning test
        r = await http.put(f'{BASE}/machines/{machine_id}/status', headers=admin_headers, json={'status': 'running'})
        check('set machine to running', r.status_code == 200)

        # ---- WARNINGS TESTS ----
        print("\n=== WARNINGS TESTS ===")

        # Test authenticated warning creation
        r = await http.post(f'{BASE}/warnings', headers=admin_headers, json={
            'machine_id': machine_id,
            'description': 'Abnormal vibration detected',
            'warning_type': 'MECHANICAL',
            'wo_type': 'Inspection'
        })
        check('create warning (authenticated)', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            warning = r.json()
            check('warning has tag_number', 'tag_number' in warning and warning['tag_number'].startswith('WRN-'))
            check('warning has work_order_id', 'work_order_id' in warning and warning['work_order_id'] is not None)
            check('warning has work_order_number', 'work_order_number' in warning and warning['work_order_number'] is not None)
            check('warning status is OPEN', warning.get('status') == 'OPEN')
            warning_id = warning['id']
            warning_wo_id = warning['work_order_id']
            print(f"Created warning: {warning['tag_number']} with WO: {warning['work_order_number']}")

            # Verify machine status changed to 'watch'
            r = await http.get(f'{BASE}/machines/{machine_id}', headers=admin_headers)
            if r.status_code == 200:
                machine = r.json()
                check('machine status changed to watch', machine.get('machine', {}).get('status') == 'watch', 
                      f"status={machine.get('machine', {}).get('status')}")

        # Test GET warnings
        r = await http.get(f'{BASE}/warnings', headers=admin_headers)
        check('list warnings', r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            check('warnings has items', 'items' in data and isinstance(data['items'], list))
            check('warnings has total', 'total' in data)

        # Test public warning creation (no auth)
        r = await http.post(f'{BASE}/public/warnings', json={
            'machine_id': machine_id,
            'description': 'Strange noise from public kiosk',
            'warning_type': 'ELECTRICAL',
            'reporter_name': 'Floor Operator John',
            'wo_type': 'Corrective'
        })
        check('create public warning (no auth)', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            public_warning = r.json()
            check('public warning has tag_number', 'tag_number' in public_warning)
            check('public warning submitted_via is public_kiosk', public_warning.get('submitted_via') == 'public_kiosk')
            check('public warning has work_order', public_warning.get('work_order_id') is not None)
            print(f"Created public warning: {public_warning['tag_number']}")

        # Test public warning without reporter_name (should fail)
        r = await http.post(f'{BASE}/public/warnings', json={
            'machine_id': machine_id,
            'description': 'Test warning',
            'warning_type': 'MECHANICAL',
            'reporter_name': '',
            'wo_type': 'Inspection'
        })
        check('public warning requires reporter_name', r.status_code == 400, str(r.status_code))

        # ---- WO LIFECYCLE TESTS ----
        print("\n=== WO LIFECYCLE TESTS ===")

        # Create a test work order
        r = await http.post(f'{BASE}/work-orders', headers=admin_headers, json={
            'machine_id': machine_id,
            'title': 'Test WO for lifecycle',
            'description': 'Testing PENDING_ADMIN_CLOSURE flow',
            'wo_type': 'Corrective',
            'priority': 'medium',
            'assigned_to': 'tech'
        })
        check('create test work order', r.status_code == 200)
        if r.status_code == 200:
            test_wo = r.json()
            test_wo_id = test_wo['id']
            test_wo_number = test_wo['wo_number']
            print(f"Created test WO: {test_wo_number}")

            # Tech starts the WO
            r = await http.put(f'{BASE}/work-orders/{test_wo_id}', headers=tech_headers, json={'action': 'start'})
            check('tech starts WO', r.status_code == 200)

            # Tech completes the WO (should go to PENDING_ADMIN_CLOSURE)
            r = await http.put(f'{BASE}/work-orders/{test_wo_id}', headers=tech_headers, json={
                'action': 'complete',
                'action_taken': 'Replaced bearing and realigned shaft'
            })
            check('tech completes WO', r.status_code == 200)
            if r.status_code == 200:
                result = r.json()
                check('WO status is PENDING_ADMIN_CLOSURE', result.get('status') == 'PENDING_ADMIN_CLOSURE',
                      f"status={result.get('status')}")

            # Tech tries to close the WO (should fail with 403)
            r = await http.put(f'{BASE}/work-orders/{test_wo_id}', headers=tech_headers, json={'action': 'close'})
            check('tech cannot close WO (403)', r.status_code == 403, str(r.status_code))

            # Admin closes the WO
            r = await http.put(f'{BASE}/work-orders/{test_wo_id}', headers=admin_headers, json={'action': 'close'})
            check('admin closes WO', r.status_code == 200)
            if r.status_code == 200:
                result = r.json()
                check('WO status is CLOSED', result.get('status') == 'CLOSED', f"status={result.get('status')}")

        # Test warning-sourced WO closure restores machine status
        if warning_wo_id:
            print(f"\n=== Testing warning WO closure restores machine status ===")
            # Get the warning WO
            r = await http.get(f'{BASE}/work-orders', headers=admin_headers)
            if r.status_code == 200:
                wos = r.json()['items']
                warning_wo = next((wo for wo in wos if wo['id'] == warning_wo_id), None)
                if warning_wo:
                    # Complete as tech
                    r = await http.put(f'{BASE}/work-orders/{warning_wo_id}', headers=tech_headers, json={
                        'action': 'start'
                    })
                    r = await http.put(f'{BASE}/work-orders/{warning_wo_id}', headers=tech_headers, json={
                        'action': 'complete',
                        'action_taken': 'Inspected and tightened bolts'
                    })
                    check('complete warning WO as tech', r.status_code == 200)

                    # Close as admin
                    r = await http.put(f'{BASE}/work-orders/{warning_wo_id}', headers=admin_headers, json={
                        'action': 'close'
                    })
                    check('admin closes warning WO', r.status_code == 200)

                    # Verify machine status restored from watch to running
                    r = await http.get(f'{BASE}/machines/{machine_id}', headers=admin_headers)
                    if r.status_code == 200:
                        machine = r.json()
                        check('machine status restored to running', 
                              machine.get('machine', {}).get('status') == 'running',
                              f"status={machine.get('machine', {}).get('status')}")

        # ---- OPERATOR BREAKDOWN AUTO-WO TEST ----
        print("\n=== OPERATOR BREAKDOWN AUTO-WO TEST ===")

        # Operator creates breakdown with auto_create_work_order=false (should be forced to true)
        r = await http.post(f'{BASE}/breakdowns', headers=operator_headers, json={
            'machine_id': machine_id,
            'description': 'Operator reported breakdown',
            'breakdown_type': 'MECHANICAL',
            'auto_create_work_order': False  # Operator cannot opt out
        })
        check('operator creates breakdown', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            bd = r.json()
            check('operator breakdown has work_order_id', bd.get('work_order_id') is not None,
                  f"work_order_id={bd.get('work_order_id')}")
            check('operator breakdown WO is assigned', bd.get('work_order_number') is not None)
            print(f"Operator breakdown: {bd['ticket_number']} with WO: {bd.get('work_order_number')}")

            # Clean up: close the breakdown
            r = await http.put(f'{BASE}/breakdowns/{bd["id"]}', headers=admin_headers, json={
                'action': 'complete',
                'action_taken': 'Fixed by admin for test cleanup'
            })

        # Admin creates breakdown with auto_create_work_order=false (should respect choice)
        r = await http.post(f'{BASE}/breakdowns', headers=admin_headers, json={
            'machine_id': machine_id,
            'description': 'Admin reported breakdown without WO',
            'breakdown_type': 'ELECTRICAL',
            'auto_create_work_order': False
        })
        check('admin creates breakdown without WO', r.status_code == 200)
        if r.status_code == 200:
            bd = r.json()
            check('admin breakdown respects auto_create_work_order=false', 
                  bd.get('work_order_id') is None,
                  f"work_order_id={bd.get('work_order_id')}")
            print(f"Admin breakdown without WO: {bd['ticket_number']}")

            # Clean up
            r = await http.put(f'{BASE}/breakdowns/{bd["id"]}', headers=admin_headers, json={
                'action': 'complete',
                'action_taken': 'Fixed by admin for test cleanup'
            })

    # Summary
    failed = [r for r in results if not r[1]]
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(results)}  PASS: {len(results)-len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("\nFAILED TESTS:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
    print('='*60)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    asyncio.run(main())
