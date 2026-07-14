"""Verify assignment enforcement + closure attribution fix."""
import requests
from datetime import datetime, timedelta, timezone

BASE = "https://content-extractor-75.preview.emergentagent.com/api"

def login(u, p):
    r = requests.post(f"{BASE}/auth/login", json={"username": u, "password": p})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}

admin = login("admin", "admin123")
tech = login("tech", "tech123")
ok = fail = 0

def check(name, cond, detail=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(f"{'OK  ' if cond else 'FAIL'} {name} {detail}")

# ensure a second technician exists whose task 'tech' will illegally try to work
users = requests.get(f"{BASE}/users", headers=admin).json()
if not any(u["username"] == "tech2" for u in users):
    r = requests.post(f"{BASE}/users", headers=admin, json={"username": "tech2", "password": "tech123", "name": "Technician Two", "role": "technician"})
    print("created tech2:", r.status_code)

m = requests.get(f"{BASE}/machines", headers=admin).json()[0]

# ---- Breakdown enforcement ----
bd = requests.post(f"{BASE}/breakdowns", headers=admin, json={"machine_id": m["id"], "description": "ENF verify bd", "failure_mode": "Mechanical", "assigned_to": "tech2"}).json()
r = requests.put(f"{BASE}/breakdowns/{bd['id']}", headers=tech, json={"action": "start"})
check("BD start by non-assignee -> 403", r.status_code == 403, r.json().get("detail", "")[:70])
r = requests.put(f"{BASE}/breakdowns/{bd['id']}", headers=tech, json={"action": "complete", "action_taken": "hack"})
check("BD complete by non-assignee -> 403", r.status_code == 403)
r = requests.put(f"{BASE}/breakdowns/{bd['id']}", headers=tech, json={"action": "close", "action_taken": "hack"})
check("BD close by non-assignee -> 403", r.status_code == 403)

# holder transfers to 'tech', then tech completes -> attribution = tech
tech2 = login("tech2", "tech123")
r = requests.put(f"{BASE}/breakdowns/{bd['id']}", headers=tech2, json={"action": "assign", "assigned_to": "tech"})
check("holder transfer bd -> tech", r.status_code == 200)
end = datetime.now(timezone.utc); start = end - timedelta(minutes=10)
r = requests.put(f"{BASE}/breakdowns/{bd['id']}", headers=tech, json={"action": "complete", "action_taken": "fixed", "start_time": start.isoformat(), "end_time": end.isoformat()})
check("assignee completes -> 200", r.status_code == 200)
bd_after = requests.get(f"{BASE}/breakdowns/{bd['id']}", headers=admin).json()
check("attribution: assigned_to=tech", bd_after.get("assigned_to") == "tech", bd_after.get("assigned_to"))
check("attribution: closed_by=tech", bd_after.get("closed_by") == "tech", bd_after.get("closed_by"))

# ---- Admin closes a breakdown assigned to tech2 (45 min -> RCA) ----
bd2 = requests.post(f"{BASE}/breakdowns", headers=admin, json={"machine_id": m["id"], "description": "ENF verify admin close", "failure_mode": "Mechanical", "assigned_to": "tech2"}).json()
end2 = datetime.now(timezone.utc); start2 = end2 - timedelta(minutes=45)
r = requests.put(f"{BASE}/breakdowns/{bd2['id']}", headers=admin, json={"action": "close", "action_taken": "admin closed", "start_time": start2.isoformat(), "end_time": end2.isoformat()})
res = r.json()
check("admin close assigned bd -> 200", r.status_code == 200)
check("RCA assigned to actual repairer (tech2)", res.get("rca_assigned_to") == "tech2", res.get("rca_assigned_to"))
bd2_after = requests.get(f"{BASE}/breakdowns/{bd2['id']}", headers=admin).json()
check("closed_by=admin (actor)", bd2_after.get("closed_by") == "admin", bd2_after.get("closed_by"))
check("assigned_to stays tech2 (repairer)", bd2_after.get("assigned_to") == "tech2")
rca = requests.get(f"{BASE}/work-orders/{res['rca_task_id']}", headers=admin).json()
check("RCA WO locked to tech2", rca.get("assigned_to") == "tech2", rca.get("assigned_to"))

# timeline audit: closure event mentions both parties
tl = requests.get(f"{BASE}/timeline?limit=30", headers=admin).json()
items = tl if isinstance(tl, list) else tl.get("items", [])
evt = next((e for e in items if e.get("reference_id") == bd2["id"] and e.get("event_type") == "breakdown_closed"), None)
check("timeline audit shows repaired-by vs closed-by", bool(evt) and "Repaired by tech2" in (evt.get("description") or "") and "closed by admin" in (evt.get("description") or ""), (evt or {}).get("description", "no event")[:100])

# ---- Admin override at closure: bd assigned tech2, admin closes selecting 'tech' ----
bd3 = requests.post(f"{BASE}/breakdowns", headers=admin, json={"machine_id": m["id"], "description": "ENF verify override", "failure_mode": "Mechanical", "assigned_to": "tech2"}).json()
end3 = datetime.now(timezone.utc); start3 = end3 - timedelta(minutes=40)
r = requests.put(f"{BASE}/breakdowns/{bd3['id']}", headers=admin, json={"action": "close", "action_taken": "override", "assigned_to": "tech", "start_time": start3.isoformat(), "end_time": end3.isoformat()})
res3 = r.json()
check("admin override close -> RCA to actual performer (tech)", res3.get("rca_assigned_to") == "tech", res3.get("rca_assigned_to"))
tl = requests.get(f"{BASE}/timeline?limit=30", headers=admin).json()
items = tl if isinstance(tl, list) else tl.get("items", [])
evt3 = next((e for e in items if e.get("reference_id") == bd3["id"] and e.get("event_type") == "breakdown_closed"), None)
check("timeline records reassignment at closure", bool(evt3) and "Reassigned from tech2" in (evt3.get("description") or ""), (evt3 or {}).get("description", "")[:110])

# ---- Work order enforcement ----
wo = requests.post(f"{BASE}/work-orders", headers=admin, json={"machine_id": m["id"], "title": "ENF verify wo", "wo_type": "Corrective", "assigned_to": "tech2"}).json()
r = requests.put(f"{BASE}/work-orders/{wo['id']}", headers=tech, json={"action": "start"})
check("WO start by non-assignee -> 403", r.status_code == 403)
r = requests.put(f"{BASE}/work-orders/{wo['id']}", headers=tech, json={"action": "complete", "action_taken": "hack"})
check("WO complete by non-assignee -> 403", r.status_code == 403)
r = requests.put(f"{BASE}/work-orders/{wo['id']}", headers=tech2, json={"action": "complete", "action_taken": "done"})
check("WO complete by assignee -> 200", r.status_code == 200)
wo_after = requests.get(f"{BASE}/work-orders/{wo['id']}", headers=admin).json()
check("WO completed_by recorded", wo_after.get("completed_by") == "tech2", wo_after.get("completed_by"))
# admin can act on assigned tasks
wo2 = requests.post(f"{BASE}/work-orders", headers=admin, json={"machine_id": m["id"], "title": "ENF verify wo admin", "wo_type": "Corrective", "assigned_to": "tech2"}).json()
r = requests.put(f"{BASE}/work-orders/{wo2['id']}", headers=admin, json={"action": "complete", "action_taken": "admin done"})
check("admin can complete assigned WO", r.status_code == 200)
wo2_after = requests.get(f"{BASE}/work-orders/{wo2['id']}", headers=admin).json()
check("admin completion audit: completed_by=admin, assigned stays tech2", wo2_after.get("completed_by") == "admin" and wo2_after.get("assigned_to") == "tech2")

print(f"\nRESULT: {ok} passed, {fail} failed")
