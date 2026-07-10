"""Test PM Work Order lifecycle and time edit features.
Tests:
1. PM task completion transitions linked WO to PENDING_ADMIN_CLOSURE
2. Admin notification created with target_role='admin'
3. PUT /api/work-orders/{id} with started_at/completed_at - duration recomputation
4. Validation: 400 when end < start
5. Authorization: 403 for non-assigned tech, admin can always edit
6. Tech cannot close PENDING_ADMIN_CLOSURE WO (403), admin can close
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

import httpx

BASE = 'https://content-extractor-75.preview.emergentagent.com/api'

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    status = '✓ PASS' if ok else '✗ FAIL'
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
        if r.status_code != 200:
            print(f"Tech login failed: {r.text}")
            sys.exit(1)
        tech_token = r.json()['token']
        tech_headers = {'Authorization': f'Bearer {tech_token}'}

        # 3. Login as operator (for permission tests)
        r = await http.post(f'{BASE}/auth/login', json={'username': 'operator', 'password': 'operator123'})
        check('operator login', r.status_code == 200)
        operator_token = r.json()['token']
        operator_headers = {'Authorization': f'Bearer {operator_token}'}

        print("\n=== PM WORK ORDER LIFECYCLE TESTS ===")

        # 4. Get a machine for testing
        r = await http.get(f'{BASE}/machines', headers=admin_headers)
        check('get machines', r.status_code == 200)
        machines_data = r.json()
        machines = machines_data if isinstance(machines_data, list) else machines_data.get('items', [])
        if not machines:
            print("No machines found, cannot continue tests")
            sys.exit(1)
        test_machine = machines[0]
        print(f"Using test machine: {test_machine['name']} ({test_machine['id']})")

        # 5. Create a PM task
        pm_payload = {
            'task_name': 'Test PM Task for WO Lifecycle',
            'description': 'Testing PM completion -> WO PENDING_ADMIN_CLOSURE',
            'priority': 'medium',
            'machine_id': test_machine['id'],
            'assigned_to': 'tech',
            'frequency': 'monthly',
            'checklist_groups': [
                {
                    'description': 'Motor Inspection',
                    'items': [
                        {'checked_for': 'Bearing condition', 'parameter': 'Visual + sound'},
                        {'checked_for': 'Vibration level', 'parameter': '<2mm/s'}
                    ]
                }
            ],
            'next_due_date': (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        }
        r = await http.post(f'{BASE}/pm-tasks', headers=admin_headers, json=pm_payload)
        check('create PM task', r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"Failed to create PM task: {r.text}")
            sys.exit(1)
        pm_task = r.json()
        pm_task_id = pm_task['id']
        print(f"Created PM task: {pm_task_id}")

        # 6. Create a Preventive Work Order linked to this PM task
        wo_payload = {
            'machine_id': test_machine['id'],
            'title': f"Preventive WO for {pm_task['task_name']}",
            'description': 'Linked to PM task for lifecycle testing',
            'wo_type': 'Preventive',
            'priority': 'medium',
            'assigned_to': 'tech'
        }
        r = await http.post(f'{BASE}/work-orders', headers=admin_headers, json=wo_payload)
        check('create preventive WO', r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"Failed to create WO: {r.text}")
            sys.exit(1)
        wo = r.json()
        wo_id = wo['id']
        wo_number = wo['wo_number']
        print(f"Created WO: {wo_number} ({wo_id})")

        # 7. Manually link the WO to the PM task (simulate pm_task_id field)
        # We need to update MongoDB directly or use an update endpoint
        # For now, let's use the database directly via a helper endpoint or assume seeded data
        # Since we can't directly modify MongoDB, let's find an existing PM WO or create via seed
        
        # Alternative: Find existing PM tasks and WOs from seed data
        r = await http.get(f'{BASE}/pm-tasks?status=active', headers=admin_headers)
        check('get PM tasks', r.status_code == 200)
        pm_tasks = r.json().get('items', [])
        
        # Find a PM task with linked WO
        pm_task_with_wo = None
        linked_wo = None
        
        for task in pm_tasks:
            # Get WOs for this machine
            r = await http.get(f'{BASE}/work-orders?machine_id={task["machine_id"]}&wo_type=Preventive', headers=admin_headers)
            if r.status_code == 200:
                wos = r.json().get('items', [])
                for w in wos:
                    if w.get('pm_task_id') == task['id'] and w['status'] in ['OPEN', 'ASSIGNED', 'IN_PROGRESS']:
                        pm_task_with_wo = task
                        linked_wo = w
                        break
            if pm_task_with_wo:
                break
        
        if not pm_task_with_wo or not linked_wo:
            print("⚠ No existing PM task with linked open WO found in seed data")
            print("Creating test scenario with manual WO...")
            # Use the WO we created earlier and assume it's linked
            pm_task_with_wo = pm_task
            linked_wo = wo
            # We'll need to manually set pm_task_id - this is a limitation
            # For testing purposes, we'll proceed with the assumption
        else:
            print(f"Found PM task with linked WO: {pm_task_with_wo['task_name']} -> {linked_wo['wo_number']}")
        
        pm_task_id = pm_task_with_wo['id']
        wo_id = linked_wo['id']
        wo_number = linked_wo['wo_number']
        initial_wo_status = linked_wo['status']

        # 8. Start the WO if not already started
        if linked_wo['status'] in ['OPEN', 'ASSIGNED']:
            r = await http.put(f'{BASE}/work-orders/{wo_id}', headers=tech_headers, json={'action': 'start'})
            check('start WO before PM completion', r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                print(f"Started WO {wo_number}")

        # 9. Complete the PM task as tech
        completion_payload = {
            'remarks': 'All checks completed successfully',
            'row_results': [
                {
                    'sn': '1',
                    'description': 'Motor Inspection',
                    'checked_for': 'Bearing condition',
                    'parameter': 'Visual + sound',
                    'status': 'OK',
                    'remarks': 'No abnormal noise'
                },
                {
                    'sn': '1',
                    'description': 'Motor Inspection',
                    'checked_for': 'Vibration level',
                    'parameter': '<2mm/s',
                    'status': 'OK',
                    'remarks': 'Within limits'
                }
            ],
            'done_by': 'Tech User',
            'checked_by': 'Supervisor'
        }
        
        r = await http.post(f'{BASE}/pm-tasks/{pm_task_id}/complete', headers=tech_headers, json=completion_payload)
        check('complete PM task as tech', r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"PM completion failed: {r.text}")
        else:
            print(f"PM task {pm_task_id} completed")

        # 10. Verify linked WO status changed to PENDING_ADMIN_CLOSURE
        r = await http.get(f'{BASE}/work-orders?search={wo_number}', headers=admin_headers)
        check('fetch WO after PM completion', r.status_code == 200)
        if r.status_code == 200:
            wos = r.json().get('items', [])
            updated_wo = next((w for w in wos if w['id'] == wo_id), None)
            if updated_wo:
                check('WO status is PENDING_ADMIN_CLOSURE', updated_wo['status'] == 'PENDING_ADMIN_CLOSURE', 
                      f"Expected PENDING_ADMIN_CLOSURE, got {updated_wo['status']}")
                check('WO has completed_at timestamp', 'completed_at' in updated_wo and updated_wo['completed_at'] is not None)
                check('WO has duration_minutes', 'duration_minutes' in updated_wo and updated_wo['duration_minutes'] is not None)
                print(f"✓ WO {wo_number} transitioned to PENDING_ADMIN_CLOSURE")
            else:
                check('WO found after PM completion', False, 'WO not found')

        # 11. Verify admin notification was created
        r = await http.get(f'{BASE}/notifications?limit=50', headers=admin_headers)
        check('fetch notifications', r.status_code == 200)
        if r.status_code == 200:
            notif_data = r.json()
            notifications = notif_data if isinstance(notif_data, list) else notif_data.get('items', [])
            admin_notif = next((n for n in notifications if 
                               n.get('reference_id') == wo_id and 
                               n.get('target_role') == 'admin' and
                               'Admin Review Required' in n.get('title', '')), None)
            check('admin notification created with target_role=admin', admin_notif is not None,
                  f"Found: {admin_notif['title'] if admin_notif else 'None'}")
            if admin_notif:
                print(f"✓ Admin notification: {admin_notif['title']}")

        # 12. Verify tech cannot close PENDING_ADMIN_CLOSURE WO (403)
        r = await http.put(f'{BASE}/work-orders/{wo_id}', headers=tech_headers, json={'action': 'close'})
        check('tech cannot close PENDING_ADMIN_CLOSURE WO (403)', r.status_code == 403, str(r.status_code))
        if r.status_code == 403:
            print(f"✓ Tech correctly blocked from closing WO (403)")

        # 13. Verify admin CAN close the WO
        r = await http.put(f'{BASE}/work-orders/{wo_id}', headers=admin_headers, json={'action': 'close'})
        check('admin can close PENDING_ADMIN_CLOSURE WO', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            print(f"✓ Admin successfully closed WO {wo_number}")

        print("\n=== WORK ORDER TIME EDIT TESTS ===")

        # 14. Create a new WO for time edit tests
        wo_payload = {
            'machine_id': test_machine['id'],
            'title': 'Test WO for Time Edits',
            'description': 'Testing started_at/completed_at edits',
            'wo_type': 'Corrective',
            'priority': 'medium',
            'assigned_to': 'tech'
        }
        r = await http.post(f'{BASE}/work-orders', headers=admin_headers, json=wo_payload)
        check('create WO for time edit tests', r.status_code == 200)
        time_test_wo = r.json()
        time_wo_id = time_test_wo['id']
        time_wo_number = time_test_wo['wo_number']
        print(f"Created time test WO: {time_wo_number}")

        # 15. Start the WO to set started_at
        r = await http.put(f'{BASE}/work-orders/{time_wo_id}', headers=tech_headers, json={'action': 'start'})
        check('start time test WO', r.status_code == 200)

        # 16. Get current WO state
        r = await http.get(f'{BASE}/work-orders?search={time_wo_number}', headers=admin_headers)
        check('fetch time test WO', r.status_code == 200)
        wo_data = r.json()
        wos = wo_data.get('items', []) if isinstance(wo_data, dict) else wo_data
        time_test_wo = next((w for w in wos if w['id'] == time_wo_id), None)
        original_started_at = time_test_wo.get('started_at')
        print(f"Original started_at: {original_started_at}")

        # 17. Test: Admin can edit times
        new_start = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        new_end = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        r = await http.put(f'{BASE}/work-orders/{time_wo_id}', headers=admin_headers, 
                          json={'action': 'update', 'started_at': new_start, 'completed_at': new_end})
        check('admin can edit WO times', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            updated = r.json().get('work_order', {})
            check('duration_minutes recomputed', 'duration_minutes' in updated and updated['duration_minutes'] == 60.0,
                  f"Expected 60.0, got {updated.get('duration_minutes')}")
            print(f"✓ Admin edited times, duration: {updated.get('duration_minutes')} min")

        # 18. Test: Assigned tech can edit times
        new_start2 = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        new_end2 = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        
        r = await http.put(f'{BASE}/work-orders/{time_wo_id}', headers=tech_headers,
                          json={'action': 'update', 'started_at': new_start2, 'completed_at': new_end2})
        check('assigned tech can edit WO times', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            updated = r.json().get('work_order', {})
            expected_duration = 150.0  # 2.5 hours = 150 minutes
            actual_duration = updated.get('duration_minutes')
            check('duration recomputed for tech edit', abs(actual_duration - expected_duration) < 1,
                  f"Expected ~{expected_duration}, got {actual_duration}")
            print(f"✓ Tech edited times, duration: {actual_duration} min")

        # 19. Test: 400 when end < start
        bad_start = datetime.now(timezone.utc).isoformat()
        bad_end = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        r = await http.put(f'{BASE}/work-orders/{time_wo_id}', headers=admin_headers,
                          json={'action': 'update', 'started_at': bad_start, 'completed_at': bad_end})
        check('400 when end time < start time', r.status_code == 400, str(r.status_code))
        if r.status_code == 400:
            print(f"✓ Correctly rejected end < start with 400")

        # 20. Create another WO assigned to a different tech for permission test
        wo_payload2 = {
            'machine_id': test_machine['id'],
            'title': 'WO assigned to other tech',
            'description': 'For testing non-assigned tech cannot edit',
            'wo_type': 'Corrective',
            'priority': 'medium',
            'assigned_to': 'admin'  # Assigned to admin, not tech
        }
        r = await http.post(f'{BASE}/work-orders', headers=admin_headers, json=wo_payload2)
        check('create WO for permission test', r.status_code == 200)
        perm_wo = r.json()
        perm_wo_id = perm_wo['id']
        
        # Start it
        r = await http.put(f'{BASE}/work-orders/{perm_wo_id}', headers=admin_headers, json={'action': 'start'})
        check('start permission test WO', r.status_code == 200)

        # 21. Test: Non-assigned tech cannot edit times (403)
        r = await http.put(f'{BASE}/work-orders/{perm_wo_id}', headers=tech_headers,
                          json={'action': 'update', 'started_at': new_start, 'completed_at': new_end})
        check('non-assigned tech cannot edit times (403)', r.status_code == 403, str(r.status_code))
        if r.status_code == 403:
            print(f"✓ Non-assigned tech correctly blocked (403)")

        # 22. Test: Operator (non-tech, non-admin) cannot edit times (403)
        r = await http.put(f'{BASE}/work-orders/{time_wo_id}', headers=operator_headers,
                          json={'action': 'update', 'started_at': new_start, 'completed_at': new_end})
        check('operator cannot edit times (403)', r.status_code == 403, str(r.status_code))
        if r.status_code == 403:
            print(f"✓ Operator correctly blocked (403)")

    # Summary
    failed = [r for r in results if not r[1]]
    print(f"\n{'='*70}")
    print(f"TOTAL: {len(results)}  PASS: {len(results)-len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("\n❌ FAILED TESTS:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
    else:
        print("\n✅ ALL TESTS PASSED")
    print('='*70)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    asyncio.run(main())
