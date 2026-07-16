"""
Test mid-repair handoff with admin creating second technician
"""
import requests
import sys
from datetime import datetime, timedelta, timezone

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

def login(username, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if r.status_code == 200:
        return r.json().get("token")
    raise Exception(f"Login failed: {r.status_code}")

def test_handoff():
    print("🔍 Testing mid-repair handoff...")
    
    # Login
    admin_token = login("admin", "admin123")
    tech_token = login("tech", "tech123")
    
    # Get machines
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE_URL}/machines", headers=headers)
    machine_id = r.json()[0]["id"]
    
    # Create second technician
    print("🔍 Creating second technician...")
    r = requests.post(f"{BASE_URL}/users", headers=headers, json={
        "username": "tech2",
        "password": "tech123",
        "name": "Tech Two",
        "role": "technician"
    })
    if r.status_code in (200, 201):
        print("✅ Second technician created")
    elif r.status_code == 400 and "already exists" in r.text:
        print("✅ Second technician already exists")
    else:
        print(f"❌ Failed to create technician: {r.status_code} {r.text}")
        return False
    
    tech2_token = login("tech2", "tech123")
    
    # Test 1: WO mid-repair handoff
    print("\n🔍 Test 1: WO mid-repair handoff requires pass_on_note")
    r = requests.post(f"{BASE_URL}/work-orders", headers=headers, json={
        "machine_id": machine_id,
        "title": "Test handoff",
        "wo_type": "Corrective",
        "assigned_to": "tech"
    })
    wo_id = r.json()["id"]
    
    # Start WO
    headers_tech = {"Authorization": f"Bearer {tech_token}", "Content-Type": "application/json"}
    r = requests.put(f"{BASE_URL}/work-orders/{wo_id}", headers=headers_tech, json={"action": "start"})
    
    # Try transfer without note -> should fail
    r = requests.put(f"{BASE_URL}/work-orders/{wo_id}", headers=headers_tech, json={
        "action": "assign",
        "assigned_to": "tech2"
    })
    if r.status_code == 400:
        print("✅ Transfer without note correctly rejected (400)")
    else:
        print(f"❌ Expected 400, got {r.status_code}")
        return False
    
    # Transfer with note -> should work
    r = requests.put(f"{BASE_URL}/work-orders/{wo_id}", headers=headers_tech, json={
        "action": "assign",
        "assigned_to": "tech2",
        "pass_on_note": "Motor bearings replaced, test alignment"
    })
    if r.status_code == 200:
        print("✅ Transfer with note successful")
        result = r.json()
        if result["assigned_to"] == "tech2":
            print("✅ WO transferred to tech2")
        else:
            print(f"❌ Expected tech2, got {result['assigned_to']}")
            return False
    else:
        print(f"❌ Transfer failed: {r.status_code} {r.text}")
        return False
    
    # Verify handoff recorded
    r = requests.get(f"{BASE_URL}/work-orders/{wo_id}", headers=headers)
    wo = r.json()
    if "handoffs" in wo and len(wo["handoffs"]) == 1:
        handoff = wo["handoffs"][0]
        if handoff["from"] == "tech" and handoff["to"] == "tech2" and handoff["mid_repair"]:
            print(f"✅ Handoff recorded: {handoff['from']} -> {handoff['to']}, note: {handoff['note'][:30]}...")
        else:
            print(f"❌ Handoff data incorrect: {handoff}")
            return False
    else:
        print(f"❌ Handoffs not recorded properly")
        return False
    
    # Test 2: Pre-start transfer (no note required)
    print("\n🔍 Test 2: Pre-start transfer (ASSIGNED) no note required")
    r = requests.post(f"{BASE_URL}/work-orders", headers=headers, json={
        "machine_id": machine_id,
        "title": "Test pre-start",
        "wo_type": "Corrective",
        "assigned_to": "tech"
    })
    wo_id2 = r.json()["id"]
    
    # Transfer without starting (ASSIGNED status) -> should work without note
    r = requests.put(f"{BASE_URL}/work-orders/{wo_id2}", headers=headers_tech, json={
        "action": "assign",
        "assigned_to": "tech2"
    })
    if r.status_code == 200 and r.json()["assigned_to"] == "tech2":
        print("✅ Pre-start transfer works without note")
    else:
        print(f"❌ Pre-start transfer failed: {r.status_code}")
        return False
    
    # Test 3: Breakdown handoff
    print("\n🔍 Test 3: Breakdown mid-repair handoff")
    r = requests.post(f"{BASE_URL}/breakdowns", headers=headers_tech, json={
        "machine_id": machine_id,
        "description": "Test breakdown handoff",
        "breakdown_type": "MECHANICAL",
        "assigned_to": "tech"
    })
    bd_id = r.json()["id"]
    
    # Start repair
    r = requests.put(f"{BASE_URL}/breakdowns/{bd_id}", headers=headers_tech, json={"action": "start"})
    
    # Try transfer without note -> should fail
    r = requests.put(f"{BASE_URL}/breakdowns/{bd_id}", headers=headers_tech, json={
        "action": "assign",
        "assigned_to": "tech2"
    })
    if r.status_code == 400:
        print("✅ Breakdown transfer without note correctly rejected (400)")
    else:
        print(f"❌ Expected 400, got {r.status_code}")
        return False
    
    # Transfer with note -> should work
    r = requests.put(f"{BASE_URL}/breakdowns/{bd_id}", headers=headers_tech, json={
        "action": "assign",
        "assigned_to": "tech2",
        "pass_on_note": "Breakdown handoff note"
    })
    if r.status_code == 200 and r.json()["assigned_to"] == "tech2":
        print("✅ Breakdown transfer with note successful")
    else:
        print(f"❌ Breakdown transfer failed: {r.status_code}")
        return False
    
    print("\n✅ All handoff tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_handoff()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
