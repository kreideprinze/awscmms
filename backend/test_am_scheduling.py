"""
AM Scheduling Backend Tests - Admin-scheduled AM tasks with per-shift recurrence
Tests schedule CRUD, line-wide scheduling, task instances, submission linking, and compliance KPIs
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class AMSchedulingTester:
    def __init__(self):
        self.admin_token = None
        self.tech_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.fryer_template_id = None
        self.fryer_schedule_id = None
        self.fryer_machine_id = None
        self.scratch_template_id = None
        self.scratch_schedule_id = None
        self.test_line = None

    def log(self, msg, status="INFO"):
        prefix = {"PASS": "✅", "FAIL": "❌", "INFO": "🔍"}.get(status, "ℹ️")
        print(f"{prefix} {msg}")

    def test(self, name, fn):
        """Run a single test"""
        self.tests_run += 1
        self.log(f"Testing: {name}", "INFO")
        try:
            fn()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "PASS")
            return True
        except AssertionError as e:
            self.log(f"FAILED: {name} - {str(e)}", "FAIL")
            return False
        except Exception as e:
            self.log(f"ERROR: {name} - {str(e)}", "FAIL")
            return False

    def login(self, username, password):
        """Login and return token"""
        r = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
        if r.status_code == 200:
            return r.json().get("token")
        raise Exception(f"Login failed for {username}: {r.status_code} {r.text}")

    def get(self, endpoint, token, expected_status=200):
        """GET request"""
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        if r.status_code != expected_status:
            raise AssertionError(f"GET {endpoint}: Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code == 200 else None

    def post(self, endpoint, token, data, expected_status=200):
        """POST request"""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data)
        if r.status_code not in (expected_status, 201) if expected_status == 200 else r.status_code != expected_status:
            raise AssertionError(f"POST {endpoint}: Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code in (200, 201) else None

    def put(self, endpoint, token, data, expected_status=200):
        """PUT request"""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.put(f"{BASE_URL}{endpoint}", headers=headers, json=data)
        if r.status_code != expected_status:
            raise AssertionError(f"PUT {endpoint}: Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code == 200 else None

    def delete(self, endpoint, token, expected_status=200):
        """DELETE request"""
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.delete(f"{BASE_URL}{endpoint}", headers=headers)
        if r.status_code != expected_status:
            raise AssertionError(f"DELETE {endpoint}: Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code == 200 else None

    def setup(self):
        """Setup: login users, find Fryer template"""
        self.log("=== SETUP ===")
        self.admin_token = self.login("admin", "admin123")
        self.tech_token = self.login("tech", "tech123")
        self.log("Users logged in successfully")

        # Find the Fryer template
        templates = self.get("/am-templates", self.admin_token)
        fryer = next((t for t in templates if "Fryer" in t.get("template_name", "")), None)
        if not fryer:
            raise Exception("Fryer AM template not found in demo data")
        self.fryer_template_id = fryer["id"]
        self.fryer_machine_id = fryer["machine_id"]
        self.test_line = fryer.get("line")
        self.log(f"Found Fryer template: {fryer['template_name']} (machine: {fryer['machine_name']}, line: {self.test_line})")

        # Find the Fryer schedule
        schedules = self.get("/am-schedules", self.admin_token)
        fryer_sched = next((s for s in schedules if s["template_id"] == self.fryer_template_id), None)
        if fryer_sched:
            self.fryer_schedule_id = fryer_sched["id"]
            self.log(f"Found Fryer schedule: shifts {fryer_sched['shifts']}, active={fryer_sched['active']}")

    # ============ BACKEND 1: Schedule CRUD ============
    def test_schedule_list(self):
        """GET /api/am-schedules lists the Fryer schedule"""
        schedules = self.get("/am-schedules", self.admin_token)
        fryer_sched = next((s for s in schedules if s["template_id"] == self.fryer_template_id), None)
        assert fryer_sched is not None, "Fryer schedule not found"
        assert set(fryer_sched["shifts"]) == {"A", "B", "C"}, f"Expected shifts A,B,C, got {fryer_sched['shifts']}"
        assert fryer_sched["active"] is True, "Fryer schedule should be active"
        self.log(f"Fryer schedule found: {fryer_sched['machine_name']}, shifts {fryer_sched['shifts']}")

    def test_schedule_duplicate_template_400(self):
        """POST /api/am-schedules duplicate template -> 400 'already exists'"""
        self.post("/am-schedules", self.admin_token, {
            "template_id": self.fryer_template_id,
            "shifts": ["A"]
        }, expected_status=400)
        self.log("Duplicate schedule creation correctly rejected with 400")

    def test_schedule_empty_shifts_400(self):
        """POST /api/am-schedules with empty shifts -> 400"""
        # Get a machine without a schedule
        machines = self.get("/machines", self.admin_token)
        templates = self.get("/am-templates", self.admin_token)
        schedules = self.get("/am-schedules", self.admin_token)
        scheduled_template_ids = {s["template_id"] for s in schedules}
        
        # Find a template without a schedule
        unscheduled = next((t for t in templates if t["id"] not in scheduled_template_ids), None)
        if unscheduled:
            self.post("/am-schedules", self.admin_token, {
                "template_id": unscheduled["id"],
                "shifts": []
            }, expected_status=400)
            self.log("Empty shifts correctly rejected with 400")
        else:
            self.log("No unscheduled template found, skipping empty shifts test")

    def test_schedule_tech_403(self):
        """POST /api/am-schedules as tech -> 403"""
        self.post("/am-schedules", self.tech_token, {
            "template_id": self.fryer_template_id,
            "shifts": ["A"]
        }, expected_status=403)
        self.log("Tech user correctly denied schedule creation with 403")

    def test_schedule_update_shifts(self):
        """PUT /api/am-schedules/{id} {shifts:['A','B']} then restore to ['A','B','C']"""
        # Update to A,B only
        updated = self.put(f"/am-schedules/{self.fryer_schedule_id}", self.admin_token, {
            "shifts": ["A", "B"]
        })
        assert set(updated["shifts"]) == {"A", "B"}, f"Expected shifts A,B, got {updated['shifts']}"
        self.log("Fryer schedule updated to shifts A,B")

        # Restore to A,B,C
        restored = self.put(f"/am-schedules/{self.fryer_schedule_id}", self.admin_token, {
            "shifts": ["A", "B", "C"]
        })
        assert set(restored["shifts"]) == {"A", "B", "C"}, f"Expected shifts A,B,C, got {restored['shifts']}"
        self.log("Fryer schedule restored to shifts A,B,C")

    def test_schedule_deactivate_reactivate(self):
        """PUT {active:false} sets deactivated_at and deletes today's PENDING instances, then PUT {active:true} restores"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get today's tasks before deactivation
        tasks_before = self.get(f"/am-tasks?machine_id={self.fryer_machine_id}&date_from={today}&date_to={today}", self.admin_token)
        pending_before = [t for t in tasks_before if t["status"] == "PENDING"]
        self.log(f"Before deactivation: {len(pending_before)} pending tasks today")

        # Deactivate
        deactivated = self.put(f"/am-schedules/{self.fryer_schedule_id}", self.admin_token, {
            "active": False
        })
        assert deactivated["active"] is False, "Schedule should be inactive"
        assert deactivated["deactivated_at"] is not None, "deactivated_at should be set"
        self.log("Fryer schedule deactivated")

        # Check today's PENDING instances are deleted
        tasks_after_deactivate = self.get(f"/am-tasks?machine_id={self.fryer_machine_id}&date_from={today}&date_to={today}&status=PENDING", self.admin_token)
        assert len(tasks_after_deactivate) == 0, f"Expected 0 pending tasks after deactivation, got {len(tasks_after_deactivate)}"
        self.log("Today's PENDING instances deleted after deactivation")

        # Reactivate
        reactivated = self.put(f"/am-schedules/{self.fryer_schedule_id}", self.admin_token, {
            "active": True
        })
        assert reactivated["active"] is True, "Schedule should be active"
        self.log("Fryer schedule reactivated")

        # Verify today's C PENDING instance regenerates
        tasks_after_reactivate = self.get(f"/am-tasks?machine_id={self.fryer_machine_id}&date_from={today}&date_to={today}", self.admin_token)
        pending_after = [t for t in tasks_after_reactivate if t["status"] == "PENDING"]
        # Note: A and B are already SUBMITTED, so only C should regenerate as PENDING
        assert len(pending_after) > 0, "Expected at least one pending task after reactivation"
        self.log(f"After reactivation: {len(pending_after)} pending tasks regenerated")

    # ============ BACKEND 2: Line-wide scheduling ============
    def test_line_wide_scheduling(self):
        """Create scratch AM template for another machine on same line, then POST /api/am-schedules/line-wide"""
        # Find another machine on the same line
        machines = self.get("/machines", self.admin_token)
        line_machines = [m for m in machines if m.get("line") == self.test_line and m["id"] != self.fryer_machine_id]
        
        if not line_machines:
            self.log(f"No other machines on line {self.test_line}, skipping line-wide test")
            return

        target_machine = line_machines[0]
        self.log(f"Creating scratch template for {target_machine['name']} on line {self.test_line}")

        # Create scratch template
        scratch_template = self.post("/am-templates", self.admin_token, {
            "machine_id": target_machine["id"],
            "template_name": f"TEST_SCRATCH_{datetime.now().strftime('%H%M%S')}",
            "checklist_groups": [
                {
                    "description": "Test Sub-Component",
                    "items": [{"checked_for": "Test check item", "parameter": ""}]
                }
            ]
        })
        self.scratch_template_id = scratch_template["id"]
        self.log(f"Scratch template created: {scratch_template['template_name']}")

        # Line-wide scheduling
        result = self.post("/am-schedules/line-wide", self.admin_token, {
            "line": self.test_line,
            "shifts": ["A"],
            "assigned_to": None
        })
        
        assert "created" in result, "Response should have 'created' count"
        assert "updated" in result, "Response should have 'updated' count"
        assert "covered_machines" in result, "Response should have 'covered_machines' list"
        assert "machines_without_template" in result, "Response should have 'machines_without_template' count"
        
        self.log(f"Line-wide result: {result['created']} created, {result['updated']} updated, {len(result['covered_machines'])} covered, {result['machines_without_template']} without template")

        # Find the scratch schedule
        schedules = self.get("/am-schedules", self.admin_token)
        scratch_sched = next((s for s in schedules if s["template_id"] == self.scratch_template_id), None)
        if scratch_sched:
            self.scratch_schedule_id = scratch_sched["id"]
            self.log(f"Scratch schedule created: {scratch_sched['machine_name']}, shifts {scratch_sched['shifts']}")

    # ============ BACKEND 3: Task instances ============
    def test_task_instances(self):
        """GET /api/am-tasks returns last-7-days instances with filters"""
        # Get all tasks
        tasks = self.get("/am-tasks", self.admin_token)
        assert len(tasks) > 0, "Expected at least some AM tasks"
        
        # Check structure
        task = tasks[0]
        assert "date" in task, "Task should have 'date'"
        assert "shift" in task, "Task should have 'shift'"
        assert "status" in task, "Task should have 'status'"
        assert "machine_id" in task, "Task should have 'machine_id'"
        self.log(f"Found {len(tasks)} AM tasks in last 7 days")

        # Filter by status=PENDING
        pending = self.get("/am-tasks?status=PENDING", self.admin_token)
        for t in pending:
            assert t["status"] == "PENDING", f"Expected PENDING, got {t['status']}"
        self.log(f"Status filter works: {len(pending)} PENDING tasks")

        # Filter by machine_id
        fryer_tasks = self.get(f"/am-tasks?machine_id={self.fryer_machine_id}", self.admin_token)
        for t in fryer_tasks:
            assert t["machine_id"] == self.fryer_machine_id, "Machine filter failed"
        self.log(f"Machine filter works: {len(fryer_tasks)} tasks for Fryer")

        # Verify idempotency - calling GET twice doesn't duplicate
        tasks_again = self.get("/am-tasks", self.admin_token)
        assert len(tasks_again) == len(tasks), "Task count should be stable (idempotent)"
        self.log("Task generation is idempotent")

    # ============ BACKEND 4: Submission linking ============
    def test_submission_linking(self):
        """POST /api/public/am-submissions for Fryer shift C, verify task status SUBMITTED and compliance updates"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get Fryer template details
        template = self.get(f"/public/am-templates/{self.fryer_template_id}", self.admin_token)
        
        # Build submission payload
        row_results = []
        for group in template["checklist_groups"]:
            for item in group["items"]:
                row_results.append({
                    "description": group["description"],
                    "checked_for": item["checked_for"],
                    "parameter": item.get("parameter", ""),
                    "status": "OK",
                    "remarks": ""
                })

        # Submit for shift C
        submission = self.post("/public/am-submissions", self.admin_token, {
            "template_id": self.fryer_template_id,
            "name": "Test Operator",
            "gpid": "TEST123",
            "shift": "C",
            "started_at": datetime.now().isoformat(),
            "row_results": row_results
        })
        
        assert submission["ok"] is True, "Submission should succeed"
        submission_id = submission["id"]
        self.log(f"Shift C submission created: {submission_id}")

        # Verify task status is now SUBMITTED
        tasks = self.get(f"/am-tasks?machine_id={self.fryer_machine_id}&date_from={today}&date_to={today}&shift=C", self.admin_token)
        shift_c_task = next((t for t in tasks if t["shift"] == "C"), None)
        assert shift_c_task is not None, "Shift C task should exist"
        assert shift_c_task["status"] == "SUBMITTED", f"Expected SUBMITTED, got {shift_c_task['status']}"
        assert shift_c_task["submission_id"] == submission_id, "submission_id should be linked"
        self.log(f"Shift C task status updated to SUBMITTED with submission_id")

        # Check compliance KPI
        kpis = self.get("/analytics/kpis?level=plant", self.admin_token)
        assert kpis["am_compliance"] is not None, "AM compliance should be calculated"
        assert kpis["am_scheduled_count"] >= 3, f"Expected at least 3 scheduled (A,B,C), got {kpis['am_scheduled_count']}"
        assert kpis["am_submitted_count"] >= 3, f"Expected at least 3 submitted (A,B,C), got {kpis['am_submitted_count']}"
        # Note: compliance might be 100% if all scheduled shifts are submitted
        self.log(f"AM Compliance: {kpis['am_compliance']}% ({kpis['am_submitted_count']}/{kpis['am_scheduled_count']})")

    # ============ BACKEND 5: Compliance scoping ============
    def test_compliance_scoping(self):
        """GET /api/analytics/kpis with various level/value filters"""
        # Plant level
        plant_kpis = self.get("/analytics/kpis?level=plant", self.admin_token)
        assert "am_compliance" in plant_kpis, "Plant KPIs should include am_compliance"
        assert "am_scheduled_count" in plant_kpis, "Plant KPIs should include am_scheduled_count"
        assert "am_submitted_count" in plant_kpis, "Plant KPIs should include am_submitted_count"
        self.log(f"Plant AM compliance: {plant_kpis['am_compliance']}%")

        # Line level with AM schedules
        if self.test_line:
            line_kpis = self.get(f"/analytics/kpis?level=line&value={self.test_line}", self.admin_token)
            assert line_kpis["am_scheduled_count"] > 0, f"Line {self.test_line} should have scheduled AM tasks"
            self.log(f"Line {self.test_line} AM: {line_kpis['am_submitted_count']}/{line_kpis['am_scheduled_count']}")

        # Line level with no AM schedules
        machines = self.get("/machines", self.admin_token)
        all_lines = list(set(m.get("line") for m in machines if m.get("line")))
        schedules = self.get("/am-schedules", self.admin_token)
        scheduled_lines = set(s.get("line") for s in schedules if s.get("line"))
        no_am_lines = [l for l in all_lines if l not in scheduled_lines]
        
        if no_am_lines:
            no_am_line = no_am_lines[0]
            no_am_kpis = self.get(f"/analytics/kpis?level=line&value={no_am_line}", self.admin_token)
            assert no_am_kpis["am_compliance"] is None, f"Line {no_am_line} with no AM should have null compliance"
            assert no_am_kpis["am_scheduled_count"] == 0, f"Line {no_am_line} should have 0 scheduled"
            self.log(f"Line {no_am_line} (no AM): compliance=null, scheduled=0")

        # Date slicer: past no-schedule window
        past_kpis = self.get("/analytics/kpis?level=plant&date_from=2026-06-01&date_to=2026-06-05", self.admin_token)
        assert past_kpis["am_scheduled_count"] == 0, "Past window with no schedules should have 0 scheduled"
        self.log("Past date range correctly shows 0 scheduled")

    # ============ CLEANUP ============
    def cleanup(self):
        """Delete scratch template and schedule"""
        self.log("=== CLEANUP ===")
        try:
            if self.scratch_schedule_id:
                self.delete(f"/am-schedules/{self.scratch_schedule_id}", self.admin_token)
                self.log(f"Deleted scratch schedule {self.scratch_schedule_id}")
        except Exception as e:
            self.log(f"Cleanup schedule error: {e}", "FAIL")

        try:
            if self.scratch_template_id:
                self.delete(f"/am-templates/{self.scratch_template_id}", self.admin_token)
                self.log(f"Deleted scratch template {self.scratch_template_id}")
        except Exception as e:
            self.log(f"Cleanup template error: {e}", "FAIL")

    def run_all(self):
        """Run all tests"""
        try:
            self.setup()
            
            # Backend 1: Schedule CRUD
            self.test("BACKEND 1.1: GET /api/am-schedules lists Fryer schedule", self.test_schedule_list)
            self.test("BACKEND 1.2: POST duplicate template -> 400", self.test_schedule_duplicate_template_400)
            self.test("BACKEND 1.3: POST empty shifts -> 400", self.test_schedule_empty_shifts_400)
            self.test("BACKEND 1.4: POST as tech -> 403", self.test_schedule_tech_403)
            self.test("BACKEND 1.5: PUT update shifts then restore", self.test_schedule_update_shifts)
            self.test("BACKEND 1.6: PUT deactivate/reactivate", self.test_schedule_deactivate_reactivate)
            
            # Backend 2: Line-wide
            self.test("BACKEND 2: Line-wide scheduling", self.test_line_wide_scheduling)
            
            # Backend 3: Task instances
            self.test("BACKEND 3: Task instances with filters", self.test_task_instances)
            
            # Backend 4: Submission linking
            self.test("BACKEND 4: Submission linking and compliance", self.test_submission_linking)
            
            # Backend 5: Compliance scoping
            self.test("BACKEND 5: Compliance scoping", self.test_compliance_scoping)
            
            self.cleanup()
            
        except Exception as e:
            self.log(f"Test suite error: {e}", "FAIL")
            self.cleanup()
        
        # Summary
        print("\n" + "="*60)
        print(f"📊 BACKEND TEST SUMMARY: {self.tests_passed}/{self.tests_run} passed")
        print("="*60)
        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = AMSchedulingTester()
    sys.exit(tester.run_all())
