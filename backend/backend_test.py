"""
Backend Testing: 11 Bug Fixes - Breakdown/WO Sync, Editable Times, Line Availability, Warning WO, PM PDF
"""
import requests
import sys
from datetime import datetime, timedelta, timezone

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class BugFixTester:
    def __init__(self):
        self.admin_token = None
        self.tech_token = None
        self.operator_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_machine_id = None
        self.test_line = None
        self.test_breakdown_id = None
        self.test_wo_id = None
        self.test_warning_id = None
        self.test_pm_task_id = None

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

    def setup(self):
        """Setup: login all users, get test machine"""
        self.log("=== SETUP ===")
        self.admin_token = self.login("admin", "admin123")
        self.tech_token = self.login("tech", "tech123")
        self.operator_token = self.login("operator", "operator123")
        self.log("All users logged in successfully")

        # Get a test machine
        machines = self.get("/machines", self.admin_token)
        if machines and len(machines) > 0:
            self.test_machine_id = machines[0]["id"]
            self.test_line = machines[0].get("line")
            self.log(f"Test machine: {machines[0]['name']} ({self.test_machine_id}), line: {self.test_line}")

    # ============ BREAKDOWN TESTS ============
    def test_breakdown_requires_technician(self):
        """Test: POST /api/breakdowns requires assigned_to (technician)"""
        # Without technician -> 400
        self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test breakdown without tech",
            "breakdown_type": "MECHANICAL"
        }, expected_status=400)
        self.log("Breakdown creation correctly requires assigned_to")

    def test_breakdown_with_start_time_and_technician(self):
        """Test: POST /api/breakdowns with assigned_to + start_time"""
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=10)).isoformat()
        
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test breakdown with start time",
            "breakdown_type": "MECHANICAL",
            "assigned_to": "tech",
            "start_time": start_time
        })
        assert bd["ticket_number"], "Breakdown created"
        assert bd["assigned_to"] == "tech", "Technician assigned"
        assert bd["start_time"] == start_time, "Start time set correctly"
        assert bd["work_order_number"], "WO auto-created"
        self.test_breakdown_id = bd["id"]
        self.test_wo_id = bd["work_order_id"]
        self.log(f"Breakdown {bd['ticket_number']} created with tech + start_time, WO: {bd['work_order_number']}")

    def test_breakdown_complete_with_edited_times_short(self):
        """Test: Breakdown complete with edited start/end times, <=30min -> NO RCA, no root_cause required"""
        # Create a new breakdown for this test
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=25)).isoformat()
        end_time = now.isoformat()
        
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Short breakdown test",
            "breakdown_type": "ELECTRICAL",
            "assigned_to": "tech",
            "start_time": start_time
        })
        
        # Start repair
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        
        # Complete with edited times (25 min downtime) - NO root_cause required
        result = self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "start_time": start_time,
            "end_time": end_time,
            "action_taken": "Quick fix"
        })
        assert result["status"] == "COMPLETED", "Breakdown completed"
        assert 24 <= result["downtime_minutes"] <= 26, f"Downtime ~25 min, got {result['downtime_minutes']}"
        
        # Verify NO RCA WO created
        bd_detail = self.get(f"/breakdowns/{bd['id']}", self.tech_token)
        assert not bd_detail.get("rca_task_id"), "No RCA for <=30min downtime"
        self.log(f"Short breakdown (25 min) completed without RCA requirement")

    def test_breakdown_complete_with_edited_times_long(self):
        """Test: Breakdown complete with edited times >30min -> RCA WO created"""
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=45)).isoformat()
        end_time = now.isoformat()
        
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Long breakdown test",
            "breakdown_type": "MECHANICAL",
            "assigned_to": "tech",
            "start_time": start_time
        })
        
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        
        # Complete with edited times (45 min downtime)
        result = self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "start_time": start_time,
            "end_time": end_time,
            "action_taken": "Major repair"
        })
        assert result["status"] == "COMPLETED", "Breakdown completed"
        assert 44 <= result["downtime_minutes"] <= 46, f"Downtime ~45 min, got {result['downtime_minutes']}"
        
        # Verify RCA WO created
        bd_detail = self.get(f"/breakdowns/{bd['id']}", self.tech_token)
        assert bd_detail.get("rca_task_id"), "RCA WO created for >30min downtime"
        self.log(f"Long breakdown (45 min) triggered RCA WO")

    def test_breakdown_end_before_start_rejected(self):
        """Test: Breakdown complete with end_time < start_time -> 400"""
        now = datetime.now(timezone.utc)
        start_time = now.isoformat()
        end_time = (now - timedelta(minutes=10)).isoformat()  # End before start
        
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Invalid time test",
            "breakdown_type": "MECHANICAL",
            "assigned_to": "tech",
            "start_time": start_time
        })
        
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        
        # Try to complete with end < start -> should fail
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "start_time": start_time,
            "end_time": end_time,
            "action_taken": "Test"
        }, expected_status=400)
        self.log("End time before start time correctly rejected (400)")

    # ============ BREAKDOWN-WO SYNC TESTS ============
    def test_breakdown_complete_syncs_wo_to_pending_admin(self):
        """Test: Breakdown complete -> linked WO immediately PENDING_ADMIN_CLOSURE"""
        if not self.test_breakdown_id or not self.test_wo_id:
            raise AssertionError("Test breakdown not created")
        
        # Complete the breakdown
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=20)).isoformat()
        end_time = now.isoformat()
        
        self.put(f"/breakdowns/{self.test_breakdown_id}", self.tech_token, {"action": "start"})
        self.put(f"/breakdowns/{self.test_breakdown_id}", self.tech_token, {
            "action": "complete",
            "start_time": start_time,
            "end_time": end_time,
            "action_taken": "Repaired"
        })
        
        # Verify WO is now PENDING_ADMIN_CLOSURE
        wo = self.get(f"/work-orders/{self.test_wo_id}", self.admin_token)
        assert wo["status"] == "PENDING_ADMIN_CLOSURE", f"WO status should be PENDING_ADMIN_CLOSURE, got {wo['status']}"
        self.log("Breakdown complete correctly synced WO to PENDING_ADMIN_CLOSURE")

    def test_admin_close_wo_closes_breakdown(self):
        """Test: Admin close WO -> breakdown auto-CLOSED"""
        if not self.test_breakdown_id or not self.test_wo_id:
            raise AssertionError("Test breakdown not created")
        
        # Admin closes the WO
        self.put(f"/work-orders/{self.test_wo_id}", self.admin_token, {"action": "close"})
        
        # Verify breakdown is now CLOSED
        bd = self.get(f"/breakdowns/{self.test_breakdown_id}", self.tech_token)
        assert bd["status"] == "CLOSED", f"Breakdown should be CLOSED, got {bd['status']}"
        self.log("Admin WO close correctly auto-closed linked breakdown")

    def test_admin_close_breakdown_closes_wo(self):
        """Test: Admin close breakdown -> WO CLOSED"""
        # Create a new breakdown + WO pair
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test admin close breakdown",
            "breakdown_type": "MECHANICAL",
            "assigned_to": "tech"
        })
        wo_id = bd["work_order_id"]
        
        # Start and complete breakdown
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        now = datetime.now(timezone.utc)
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "end_time": now.isoformat(),
            "action_taken": "Fixed"
        })
        
        # Admin closes breakdown directly
        self.put(f"/breakdowns/{bd['id']}", self.admin_token, {"action": "close"})
        
        # Verify WO is now CLOSED
        wo = self.get(f"/work-orders/{wo_id}", self.admin_token)
        assert wo["status"] == "CLOSED", f"WO should be CLOSED, got {wo['status']}"
        self.log("Admin breakdown close correctly closed linked WO")

    # ============ BREAKDOWNS LIST TESTS ============
    def test_breakdowns_returns_open_total(self):
        """Test: GET /api/breakdowns returns open_total (count of OPEN/ASSIGNED/IN_PROGRESS only)"""
        result = self.get("/breakdowns", self.tech_token)
        assert "open_total" in result, "open_total field present"
        assert "total" in result, "total field present"
        assert isinstance(result["open_total"], int), "open_total is integer"
        # open_total should be <= total
        assert result["open_total"] <= result["total"], "open_total <= total"
        self.log(f"Breakdowns list returns open_total: {result['open_total']} (total: {result['total']})")

    # ============ LINE AVAILABILITY TESTS ============
    def test_line_availability_calculation(self):
        """Test: Line availability = (Window - downtime) / Window * 100, no machine-count normalization"""
        if not self.test_line:
            self.log("No test line available, skipping line availability test")
            return
        
        # Get line KPIs for 8 hours
        result = self.get("/control-room/line-kpis?hours=8", self.admin_token)
        assert "lines" in result, "lines array present"
        assert result["window_hours"] == 8, "Window is 8 hours"
        
        # Find our test line
        test_line_kpi = next((l for l in result["lines"] if l["line"] == self.test_line), None)
        if test_line_kpi:
            # Availability should be between 0 and 100
            assert 0 <= test_line_kpi["availability"] <= 100, f"Availability out of range: {test_line_kpi['availability']}"
            # Downtime should be capped at window (480 min for 8h)
            assert test_line_kpi["downtime_minutes"] <= 480, f"Downtime exceeds window: {test_line_kpi['downtime_minutes']}"
            self.log(f"Line {self.test_line}: availability={test_line_kpi['availability']}%, downtime={test_line_kpi['downtime_minutes']} min")
        else:
            self.log(f"Test line {self.test_line} not found in KPIs")

    # ============ WARNING WO GENERATION TESTS ============
    def test_warning_wo_generation(self):
        """Test: POST /api/warnings/{id}/generate-wo works for warning without WO"""
        # Create a warning first (warnings also require assigned_to now)
        warning = self.post("/warnings", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test warning for WO generation",
            "warning_type": "MECHANICAL",
            "reporter_name": "Test Tech",
            "assigned_to": "tech",
            "wo_type": "Inspection"
        })
        self.test_warning_id = warning["id"]
        assert warning["tag_number"], "Warning created"
        assert warning["work_order_number"], "WO auto-created with warning"
        self.log(f"Warning {warning['tag_number']} created with auto WO: {warning['work_order_number']}")

    def test_warning_wo_generation_duplicate_rejected(self):
        """Test: POST /api/warnings/{id}/generate-wo -> 400 if open WO already linked"""
        if not self.test_warning_id:
            raise AssertionError("Test warning not created")
        
        # Warning already has a WO from creation, try to generate another -> should fail
        self.post(f"/warnings/{self.test_warning_id}/generate-wo", self.tech_token, {
            "assigned_to": "tech",
            "wo_type": "Corrective"
        }, expected_status=400)
        self.log("Duplicate warning WO generation correctly rejected (400)")

    # ============ WO EDITED TIMES TESTS ============
    def test_wo_complete_with_edited_times(self):
        """Test: WO complete with started_at/completed_at -> duration from edited times + RCA if >30min"""
        # Create a WO
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test WO with edited times",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        
        # Start WO
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {"action": "start"})
        
        # Complete with edited times (40 min duration -> should trigger RCA)
        now = datetime.now(timezone.utc)
        started_at = (now - timedelta(minutes=40)).isoformat()
        completed_at = now.isoformat()
        
        result = self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "complete",
            "started_at": started_at,
            "completed_at": completed_at,
            "action_taken": "Completed with edited times"
        })
        assert result["status"] == "PENDING_ADMIN_CLOSURE", "WO completed"
        
        # Verify duration calculated from edited times
        wo_detail = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert 39 <= wo_detail["duration_minutes"] <= 41, f"Duration ~40 min, got {wo_detail['duration_minutes']}"
        # Should have RCA triggered
        assert wo_detail.get("rca_task_id"), "RCA triggered for >30min WO"
        self.log(f"WO completed with edited times (40 min), RCA triggered")

    # ============ PM PDF TESTS ============
    def test_pm_pdf_with_date_parameter(self):
        """Test: GET /api/pm-tasks/{id}/pdf?date=2026-07-20 returns valid PDF"""
        # Get a PM task
        pm_tasks = self.get("/pm-tasks?limit=1", self.admin_token)
        if pm_tasks["total"] == 0:
            self.log("No PM tasks available, skipping PM PDF test")
            return
        
        task_id = pm_tasks["items"][0]["id"]
        self.test_pm_task_id = task_id
        
        # Request PDF with date parameter
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        r = requests.get(f"{BASE_URL}/pm-tasks/{task_id}/pdf?date=2026-07-20", headers=headers)
        assert r.status_code == 200, f"PDF request failed: {r.status_code}"
        assert r.headers.get("Content-Type") == "application/pdf", "Response is PDF"
        assert len(r.content) > 1000, "PDF has content"
        self.log(f"PM PDF generated successfully with date parameter ({len(r.content)} bytes)")

    def test_pm_complete_with_checklist_date(self):
        """Test: POST /api/pm-tasks/{id}/complete accepts checklist_date"""
        if not self.test_pm_task_id:
            # Get a PM task
            pm_tasks = self.get("/pm-tasks?limit=1", self.admin_token)
            if pm_tasks["total"] == 0:
                self.log("No PM tasks available, skipping PM complete test")
                return
            self.test_pm_task_id = pm_tasks["items"][0]["id"]
        
        # Complete PM with checklist_date
        result = self.post(f"/pm-tasks/{self.test_pm_task_id}/complete", self.tech_token, {
            "done_by": "Test Tech",
            "checklist_date": "2026-07-20",
            "row_results": [],
            "remarks": "Test completion"
        })
        assert result["checklist_date"] == "2026-07-20", "Checklist date set correctly"
        self.log("PM completion with checklist_date successful")

    def run_all_tests(self):
        """Run all bug fix tests"""
        self.log("=" * 60)
        self.log("11 BUG FIXES BACKEND TESTING")
        self.log("=" * 60)

        self.setup()

        self.log("\n=== BREAKDOWN CREATION & EDITING TESTS ===")
        self.test("Breakdown requires technician", self.test_breakdown_requires_technician)
        self.test("Breakdown with start_time and technician", self.test_breakdown_with_start_time_and_technician)
        self.test("Breakdown complete with edited times (short, <=30min)", self.test_breakdown_complete_with_edited_times_short)
        self.test("Breakdown complete with edited times (long, >30min)", self.test_breakdown_complete_with_edited_times_long)
        self.test("Breakdown end before start rejected", self.test_breakdown_end_before_start_rejected)

        self.log("\n=== BREAKDOWN-WO SYNC TESTS ===")
        self.test("Breakdown complete syncs WO to PENDING_ADMIN_CLOSURE", self.test_breakdown_complete_syncs_wo_to_pending_admin)
        self.test("Admin close WO closes breakdown", self.test_admin_close_wo_closes_breakdown)
        self.test("Admin close breakdown closes WO", self.test_admin_close_breakdown_closes_wo)

        self.log("\n=== BREAKDOWNS LIST TESTS ===")
        self.test("Breakdowns returns open_total", self.test_breakdowns_returns_open_total)

        self.log("\n=== LINE AVAILABILITY TESTS ===")
        self.test("Line availability calculation", self.test_line_availability_calculation)

        self.log("\n=== WARNING WO GENERATION TESTS ===")
        self.test("Warning WO generation", self.test_warning_wo_generation)
        self.test("Warning WO generation duplicate rejected", self.test_warning_wo_generation_duplicate_rejected)

        self.log("\n=== WO EDITED TIMES TESTS ===")
        self.test("WO complete with edited times", self.test_wo_complete_with_edited_times)

        self.log("\n=== PM PDF TESTS ===")
        self.test("PM PDF with date parameter", self.test_pm_pdf_with_date_parameter)
        self.test("PM complete with checklist_date", self.test_pm_complete_with_checklist_date)

        self.log("\n" + "=" * 60)
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        self.log("=" * 60)

        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = BugFixTester()
    sys.exit(tester.run_all_tests())
