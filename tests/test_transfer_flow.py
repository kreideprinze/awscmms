import requests, json, sys

BASE = "https://content-extractor-75.preview.emergentagent.com/api"

def login(u, p):
    r = requests.post(f"{BASE}/auth/login", json={"username": u, "password": p})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}

admin = login("admin", "admin123")
tech = login("tech", "tech123")

# find technicians
users = requests.get(f"{BASE}/users", headers=admin).json()
techs = [u["username"] for u in users if u.get("role") == "technician" and u.get("active", True)]
print("technicians:", techs)
if len(techs) < 2:
    # create a second technician for transfer testing
    r = requests.post(f"{BASE}/users", headers=admin, json={
        "username": "tech2", "password": "tech123", "name": "Technician Two", "role": "technician"})
    print("create tech2:", r.status_code, r.text[:200])
    techs.append("tech2")
tech_a, tech_b = "tech", [t for t in techs if t != "tech"][0]
print("tech_a:", tech_a, "tech_b:", tech_b)

machines = requests.get(f"{BASE}/machines", headers=admin).json()
m = machines[0]
print("machine:", m["id"], m["name"])

# 1) Create UNASSIGNED WO
r = requests.post(f"{BASE}/work-orders", headers=admin, json={
    "machine_id": m["id"], "title": "Transfer test WO", "wo_type": "Corrective", "priority": "medium"})
wo = r.json(); wo_id = wo["id"]
print("1. created WO:", wo["wo_number"], "assigned_to:", wo.get("assigned_to"))

# 2) Tech claims it
r = requests.put(f"{BASE}/work-orders/{wo_id}", headers=tech, json={"action": "claim"})
print("2. tech claim:", r.status_code, r.json())

# 3) tech_b tries to transfer (should be 403)
tech_b_hdr = None
try:
    tech_b_hdr = login(tech_b, "tech123")
    r = requests.put(f"{BASE}/work-orders/{wo_id}", headers=tech_b_hdr, json={"action": "assign", "assigned_to": tech_b})
    print("3. tech_b steal attempt (expect 403):", r.status_code, r.json().get("detail"))
except Exception as e:
    print("3. tech_b login failed:", e)

# 4) tech (holder) transfers to tech_b
r = requests.put(f"{BASE}/work-orders/{wo_id}", headers=tech, json={"action": "assign", "assigned_to": tech_b})
print("4. holder transfer -> tech_b:", r.status_code, r.json())

# 5) admin transfers back to tech
r = requests.put(f"{BASE}/work-orders/{wo_id}", headers=admin, json={"action": "assign", "assigned_to": tech_a})
print("5. admin transfer -> tech:", r.status_code, r.json())

# 6) PM task claim/transfer
pms = requests.get(f"{BASE}/pm-tasks", headers=admin).json().get("items", [])
pm_un = next((p for p in pms if not p.get("assigned_to")), None)
pm_any = pm_un or (pms[0] if pms else None)
if pm_any:
    pid = pm_any["id"]
    if pm_un:
        r = requests.post(f"{BASE}/pm-tasks/{pid}/claim", headers=tech, json={})
        print("6a. tech self-claim PM:", r.status_code, r.json())
    # transfer by holder/admin
    r = requests.post(f"{BASE}/pm-tasks/{pid}/claim", headers=admin, json={"assigned_to": tech_b})
    print("6b. admin transfer PM -> tech_b:", r.status_code, r.json())
    # tech_a (not holder) tries transfer -> 403
    r = requests.post(f"{BASE}/pm-tasks/{pid}/claim", headers=tech, json={"assigned_to": tech_a})
    print("6c. non-holder PM transfer (expect 403):", r.status_code, r.json().get("detail"))
else:
    print("6. no PM tasks found")

# 7) Breakdown: create unassigned, claim, transfer, close with >30min downtime -> rca_task_id
r = requests.post(f"{BASE}/breakdowns", headers=admin, json={
    "machine_id": m["id"], "description": "Transfer/RCA flow test", "failure_mode": "Mechanical"})
bd = r.json(); bd_id = bd["id"]
print("7a. breakdown created:", bd.get("ticket_number"), "assigned:", bd.get("assigned_to"))
r = requests.put(f"{BASE}/breakdowns/{bd_id}", headers=tech, json={"action": "claim"})
print("7b. tech claim bd:", r.status_code, r.json())
if tech_b_hdr:
    r = requests.put(f"{BASE}/breakdowns/{bd_id}", headers=tech_b_hdr, json={"action": "assign", "assigned_to": tech_b})
    print("7c. non-holder bd steal (expect 403):", r.status_code, r.json().get("detail"))
r = requests.put(f"{BASE}/breakdowns/{bd_id}", headers=tech, json={"action": "assign", "assigned_to": tech_b})
print("7d. holder transfer bd -> tech_b:", r.status_code, r.json())
r = requests.put(f"{BASE}/breakdowns/{bd_id}", headers=admin, json={"action": "assign", "assigned_to": tech_a})
print("7e. admin transfer bd -> tech:", r.status_code, r.json())

# close with edited times giving 45 min downtime
from datetime import datetime, timedelta, timezone
end = datetime.now(timezone.utc)
start = end - timedelta(minutes=45)
r = requests.put(f"{BASE}/breakdowns/{bd_id}", headers=tech, json={
    "action": "close", "start_time": start.isoformat(), "end_time": end.isoformat(),
    "action_taken": "Replaced bearing"})
res = r.json()
print("7f. close bd (45 min):", r.status_code, json.dumps(res))
rca_id = res.get("rca_task_id")
assert res.get("rca_required") and rca_id, "RCA should be required!"
assert res.get("rca_assigned_to") == tech_a

# 8) RCA lock: cannot transfer/claim RCA
r = requests.put(f"{BASE}/work-orders/{rca_id}", headers=admin, json={"action": "assign", "assigned_to": tech_b})
print("8a. admin transfer RCA (expect 400):", r.status_code, r.json().get("detail"))
r = requests.put(f"{BASE}/work-orders/{rca_id}", headers=tech_b_hdr or tech, json={"action": "claim"})
print("8b. claim RCA (expect 400):", r.status_code, r.json().get("detail"))

print("\nALL CHECKS DONE")
