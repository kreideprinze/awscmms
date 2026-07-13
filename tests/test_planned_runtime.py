"""Verification of the Planned Runtime + derived Downtime + corrected Availability model."""
import requests
from datetime import datetime, timedelta, timezone

BASE = "https://content-extractor-75.preview.emergentagent.com/api"

def login(u, p):
    r = requests.post(f"{BASE}/auth/login", json={"username": u, "password": p})
    return {"Authorization": f"Bearer {r.json()['token']}"}

admin = login("admin", "admin123")
ok = 0
fail = 0

def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"OK   {name} {detail}")
    else:
        fail += 1
        print(f"FAIL {name} {detail}")

machines = requests.get(f"{BASE}/machines", headers=admin).json()
m = next(mm for mm in machines if mm["line"] == "PC21")
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
day3 = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()

# 1) Validation: planned_hours out of range
r = requests.post(f"{BASE}/runtime-logs", headers=admin, json={"line": "PC21", "date": yesterday, "planned_hours": 30})
check("reject planned_hours>24", r.status_code == 400, f"({r.status_code})")
r = requests.post(f"{BASE}/runtime-logs", headers=admin, json={"line": "PC21", "date": yesterday, "planned_hours": 0})
check("reject planned_hours=0", r.status_code == 400, f"({r.status_code})")

# 2) Log planned runtime for yesterday (no breakdowns that day yet) -> availability 100
r = requests.post(f"{BASE}/runtime-logs", headers=admin, json={"line": "PC21", "date": yesterday, "planned_hours": 16})
row = r.json()
check("log planned 16h", r.status_code == 200 and row["planned_hours"] == 16, str({k: row.get(k) for k in ("planned_hours","downtime_hours","run_hours","availability","clamped")}))

# 3) Create a closed breakdown of exactly 2h yesterday on PC21 -> downtime derived
start = f"{yesterday}T08:00:00+00:00"
end = f"{yesterday}T10:00:00+00:00"
r = requests.post(f"{BASE}/breakdowns", headers=admin, json={"machine_id": m["id"], "description": "AB verify derived downtime", "failure_mode": "Mechanical", "assigned_to": "tech"})
bd = r.json()
r = requests.put(f"{BASE}/breakdowns/{bd['id']}", headers=admin, json={"action": "close", "start_time": start, "end_time": end, "action_taken": "verify", "assigned_to": "tech"})
check("close 2h breakdown", r.status_code == 200, f"({r.status_code}) downtime={r.json().get('downtime_minutes')}min")

# 4) Read derived row: downtime 2h, run 14h, availability (16-2)/16=87.5
r = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={yesterday}&date_to={yesterday}", headers=admin)
row = r.json()["items"][0]
check("derived downtime=2h", abs(row["downtime_hours"] - 2.0) < 0.05, f"got {row['downtime_hours']}")
check("derived run=14h", abs(row["run_hours"] - 14.0) < 0.05, f"got {row['run_hours']}")
check("availability=(16-2)/16=87.5", abs(row["availability"] - 87.5) < 0.3, f"got {row['availability']}")
check("not clamped", row["clamped"] is False)

# 5) Warnings must NOT count: create a warning on same machine, re-read downtime unchanged
r = requests.post(f"{BASE}/warnings", headers=admin, json={"machine_id": m["id"], "description": "AB verify warning exclusion", "warning_type": "Abnormal noise"})
warn_ok = r.status_code in (200, 201)
r2 = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={yesterday}&date_to={yesterday}", headers=admin)
row2 = r2.json()["items"][0]
check("warning excluded from downtime", (not warn_ok) or abs(row2["downtime_hours"] - row["downtime_hours"]) < 0.01,
      f"warn_created={warn_ok} downtime {row['downtime_hours']} -> {row2['downtime_hours']}")

# 6) CLAMP: planned 1h on a day with a 2h breakdown -> availability 0, clamped True
start3 = f"{day3}T02:00:00+00:00"
end3 = f"{day3}T04:00:00+00:00"
r = requests.post(f"{BASE}/breakdowns", headers=admin, json={"machine_id": m["id"], "description": "AB verify clamp", "failure_mode": "Mechanical", "assigned_to": "tech"})
bd3 = r.json()
requests.put(f"{BASE}/breakdowns/{bd3['id']}", headers=admin, json={"action": "close", "start_time": start3, "end_time": end3, "action_taken": "verify", "assigned_to": "tech"})
r = requests.post(f"{BASE}/runtime-logs", headers=admin, json={"line": "PC21", "date": day3, "planned_hours": 1})
row3 = r.json()
check("clamp: availability=0", row3["availability"] == 0.0, f"got {row3['availability']}")
check("clamp: flag=True", row3["clamped"] is True)

# 7) Control Room engine: custom window over yesterday -> planned denominator + clamped field
r = requests.get(f"{BASE}/control-room/line-kpis?date_from={yesterday}&date_to={yesterday}", headers=admin)
eng = r.json()
pc21 = next(l for l in eng["lines"] if l["line"] == "PC21")
check("engine PC21 availability=87.5 (planned denominator)", abs((pc21["availability"] or 0) - 87.5) < 0.5, f"got {pc21['availability']}")
check("engine exposes clamped+planned_minutes", "clamped" in pc21 and "planned_minutes" in pc21,
      f"planned_min={pc21.get('planned_minutes')} down={pc21.get('downtime_minutes')}")
check("plant availability present", eng["plant_availability"] is not None, f"got {eng['plant_availability']}")

# 8) Live window (no dates): unlogged today -> 24/7 fallback keeps availability non-null
r = requests.get(f"{BASE}/control-room/line-kpis?hours=24", headers=admin)
live = r.json()
check("live 24h window still ticks (24/7 fallback)", all(l["availability"] is not None for l in live["lines"]))

# 9) Analytics: plant + line + machine scope with planned_hours key
r = requests.get(f"{BASE}/analytics/kpis?level=plant&date_from={day3}&date_to={yesterday}", headers=admin).json()
check("analytics plant planned_hours=17 (16+1)", abs(r.get("planned_hours", 0) - 17) < 0.05, f"got {r.get('planned_hours')}")
check("analytics availability_trend derived", isinstance(r.get("availability_trend"), list))
r = requests.get(f"{BASE}/analytics/kpis?level=machine&value={m['id']}&date_from={day3}&date_to={yesterday}", headers=admin).json()
check("machine scope inherits line planned", abs(r.get("planned_hours", 0) - 17) < 0.05, f"got {r.get('planned_hours')}")

# 10) Machine summary (routers_core) derived runtime block
r = requests.get(f"{BASE}/machines/{m['id']}/summary", headers=admin)
if r.status_code == 404:
    r = requests.get(f"{BASE}/machines/{m['id']}/detail", headers=admin)
d = r.json()
rt = d.get("runtime", {})
check("machine summary runtime derived", r.status_code == 200 and "planned_hours" in rt and "downtime_hours" in rt, str(rt))

# 11) CSV import with planned model
csv_text = f"line,date,planned_hours\nPC21,{(datetime.now(timezone.utc)-timedelta(days=5)).date().isoformat()},20"
r = requests.post(f"{BASE}/runtime-logs/import", headers=admin, json={"csv_text": csv_text, "apply": True})
check("CSV import planned model", r.status_code == 200 and r.json().get("imported") == 1, str(r.json()))
bad_csv = "line,date,run_hours\nPC21,2026-01-01,20"
r = requests.post(f"{BASE}/runtime-logs/import", headers=admin, json={"csv_text": bad_csv, "apply": False})
check("CSV rejects legacy columns", r.status_code == 400, f"({r.status_code})")

# 12) Delete -> day reverts to unlogged
r = requests.delete(f"{BASE}/line-runtime-logs?line=PC21&date={day3}", headers=admin)
check("delete planned entry", r.status_code == 200)
r = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={day3}&date_to={day3}", headers=admin)
check("day reverts to unlogged", len(r.json()["items"]) == 0)

# 13) Reliability engine intact (uses new ctx)
r = requests.get(f"{BASE}/reliability/metrics", headers=admin)
check("reliability metrics healthy", r.status_code == 200)

print(f"\nRESULT: {ok} passed, {fail} failed")
