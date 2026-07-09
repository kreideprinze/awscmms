"""
Focused test for auto-create work order feature
"""
import requests
import sys

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

def test_auto_wo_feature():
    print("="*60)
    print("Testing Auto-Create Work Order Feature")
    print("="*60)
    
    # Login
    print("\n1. Login as admin...")
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
    if r.status_code != 200:
        print(f"❌ Login failed: {r.status_code}")
        return False
    
    token = r.json()['token']
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    print("✅ Login successful")
    
    # Get machines
    print("\n2. Getting machines...")
    r = requests.get(f"{BASE_URL}/machines", headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"❌ Failed to get machines: {r.status_code}")
        return False
    
    machines = r.json()
    if not machines:
        print("❌ No machines found")
        return False
    
    test_machine = machines[0]
    print(f"✅ Using machine: {test_machine['name']} ({test_machine['code']})")
    
    # Create breakdown with auto_create_work_order=true
    print("\n3. Creating breakdown with auto_create_work_order=true...")
    breakdown_data = {
        "machine_id": test_machine['id'],
        "description": "Test breakdown for auto WO verification",
        "breakdown_type": "MECHANICAL",
        "reporter_name": "Test Admin",
        "auto_create_work_order": True
    }
    
    r = requests.post(f"{BASE_URL}/breakdowns", json=breakdown_data, headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"❌ Failed to create breakdown: {r.status_code}")
        print(f"   Response: {r.text}")
        return False
    
    breakdown = r.json()
    print(f"✅ Breakdown created: {breakdown.get('ticket_number')}")
    
    # Verify response contains work_order_id and work_order_number
    if 'work_order_id' not in breakdown:
        print("❌ Response missing 'work_order_id'")
        return False
    
    if 'work_order_number' not in breakdown:
        print("❌ Response missing 'work_order_number'")
        return False
    
    if not breakdown['work_order_id']:
        print("❌ work_order_id is null")
        return False
    
    if not breakdown['work_order_number']:
        print("❌ work_order_number is null")
        return False
    
    print(f"✅ Auto-created WO: {breakdown['work_order_number']}")
    print(f"   WO ID: {breakdown['work_order_id']}")
    
    # Get work orders and verify the WO exists
    print("\n4. Verifying work order was created...")
    r = requests.get(f"{BASE_URL}/work-orders", headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"❌ Failed to get work orders: {r.status_code}")
        return False
    
    wo_data = r.json()
    items = wo_data.get('items', wo_data if isinstance(wo_data, list) else [])
    
    wo = next((w for w in items if w.get('wo_number') == breakdown['work_order_number']), None)
    if not wo:
        print(f"❌ Work order {breakdown['work_order_number']} not found in list")
        return False
    
    print(f"✅ Work order found: {wo['wo_number']}")
    
    # Verify WO properties
    print("\n5. Verifying work order properties...")
    checks = [
        ('wo_type', 'Corrective'),
        ('status', 'ASSIGNED'),
        ('source_breakdown_id', breakdown['id']),
    ]
    
    all_passed = True
    for field, expected in checks:
        actual = wo.get(field)
        if actual == expected:
            print(f"✅ {field}: {actual}")
        else:
            print(f"❌ {field}: expected '{expected}', got '{actual}'")
            all_passed = False
    
    # Check title contains breakdown ticket
    if breakdown['ticket_number'] in wo.get('title', ''):
        print(f"✅ title contains breakdown ticket: {wo['title']}")
    else:
        print(f"❌ title missing breakdown ticket: {wo['title']}")
        all_passed = False
    
    if all_passed:
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("❌ SOME TESTS FAILED")
        print("="*60)
        return False

if __name__ == "__main__":
    success = test_auto_wo_feature()
    sys.exit(0 if success else 1)
