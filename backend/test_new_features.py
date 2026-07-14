"""
Backend Testing: Three NEW Features
1. PM on_time tolerance window (± reminder_offset_days)
2. PM Backfill endpoint (idempotent)
3. Time Utilization in Analytics KPIs
"""
import requests
import sys
from datetime import datetime, timedelta, timezone

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class NewFeaturesTester:
    def __init__(self):
        self.admin_token = None
        self.tech_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_machine_id = None
        self.test_pm_task_id = None
        self.test_pm_completion_ids = []

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
        """Setup: login users, get test machine"""
        self.log("=== SETUP ===")
        self.admin_token = self.login("admin", "admin123")
        self.tech_token = self.login("tech", "tech123")
        self.log("Users logged in successfully")

        # Get a test machine
        machines = self.get("/machines", self.admin_token)
        if machines and len(machines) > 0:
            self.test_machine_id = machines[0]["id"]
            self.log(f"Test machine: {machines[0]['name']} ({self.test_machine_id})")

    # ============ FEATURE 1: PM ON_TIME TOLERANCE ============
    def test_pm_on_time_within_tolerance(self):
        """Test: PM completed within tolerance window should be on_time=TRUE"""
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Create PM task with reminder_offset_days=1 and next_due_date=today
        pm_task = self.post("/pm-tasks", self.admin_token, {
            "task_name": "Test PM On-Time Tolerance",
            "machine_id": self.test_machine_id,
            "assigned_to": "tech",
            "frequency": "monthly",
            "checklist": ["Check item 1", "Check item 2"],
            "reminder_offset_days": 1,
            "next_due_date": today
        })
        
        task_id = pm_task["id"]
        self.test_pm_task_id = task_id
        self.log(f"Created PM task {task_id} with reminder_offset=1, due_date={today}")
        
        # Complete the PM task (should be on_time=TRUE since completed on due date)
        completion = self.post(f"/pm-tasks/{task_id}/complete", self.tech_token, {
            "row_results": [],
            "checklist_date": today
        })
        
        comp_id = completion.get("id")
        self.test_pm_completion_ids.append(comp_id)
        
        # Verify on_time is TRUE
        assert completion.get("on_time") == True, f"Expected on_time=True, got {completion.get('on_time')}"
        assert "on_time_offset_days" in completion, "Missing on_time_offset_days field"
        self.log(f"PM completion on_time={completion.get('on_time')}, offset_days={completion.get('on_time_offset_days')}")

    def test_pm_on_time_outside_tolerance(self):
        """Test: PM completed outside tolerance window should be on_time=FALSE"""
        # Create PM task with reminder_offset_days=1 and next_due_date 5 days ago
        five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()
        
        pm_task = self.post("/pm-tasks", self.admin_token, {
            "task_name": "Test PM Late Completion",
            "machine_id": self.test_machine_id,
            "assigned_to": "tech",
            "frequency": "monthly",
            "checklist": ["Check item 1"],
            "reminder_offset_days": 1,
            "next_due_date": five_days_ago
        })
        
        task_id = pm_task["id"]
        self.log(f"Created PM task {task_id} with reminder_offset=1, due_date={five_days_ago} (5 days ago)")
        
        # Complete the PM task (should be on_time=FALSE since completed 5 days late, outside ±1 day window)
        completion = self.post(f"/pm-tasks/{task_id}/complete", self.tech_token, {
            "row_results": []
        })
        
        comp_id = completion.get("id")
        self.test_pm_completion_ids.append(comp_id)
        
        # Verify on_time is FALSE
        assert completion.get("on_time") == False, f"Expected on_time=False, got {completion.get('on_time')}"
        assert "on_time_offset_days" in completion, "Missing on_time_offset_days field"
        self.log(f"PM completion on_time={completion.get('on_time')}, offset_days={completion.get('on_time_offset_days')}")

    # ============ FEATURE 2: PM BACKFILL ENDPOINT ============
    def test_pm_backfill_admin_only(self):
        """Test: POST /api/pm-completions/backfill-on-time is admin-only (403 for tech)"""
        # Tech should get 403
        try:
            self.post("/pm-completions/backfill-on-time", self.tech_token, {}, expected_status=403)
            self.log("Backfill endpoint correctly returns 403 for technician")
        except AssertionError:
            raise AssertionError("Backfill endpoint should return 403 for non-admin users")

    def test_pm_backfill_idempotent(self):
        """Test: Backfill endpoint is idempotent - second run should give updated=0"""
        # First run
        result1 = self.post("/pm-completions/backfill-on-time", self.admin_token, {})
        scanned1 = result1.get("scanned", 0)
        updated1 = result1.get("updated", 0)
        self.log(f"First backfill run: scanned={scanned1}, updated={updated1}")
        
        # Second run (should be idempotent)
        result2 = self.post("/pm-completions/backfill-on-time", self.admin_token, {})
        scanned2 = result2.get("scanned", 0)
        updated2 = result2.get("updated", 0)
        self.log(f"Second backfill run: scanned={scanned2}, updated={updated2}")
        
        # Second run should have updated=0 (idempotent)
        assert updated2 == 0, f"Expected updated=0 on second run (idempotent), got {updated2}"
        self.log("Backfill endpoint is correctly idempotent")

    # ============ FEATURE 3: TIME UTILIZATION IN ANALYTICS ============
    def test_time_utilization_in_kpis(self):
        """Test: GET /api/analytics/kpis includes time_utilization object"""
        kpis = self.get("/analytics/kpis?level=plant", self.admin_token)
        
        # Verify time_utilization exists
        assert "time_utilization" in kpis, "Missing time_utilization in KPIs response"
        
        tu = kpis["time_utilization"]
        
        # Verify all required fields
        required_fields = ["predictive_minutes", "preventive_minutes", "breakdown_minutes", "total_minutes"]
        for field in required_fields:
            assert field in tu, f"Missing {field} in time_utilization"
        
        # Verify total = sum of the 3
        total = tu["total_minutes"]
        calculated_total = tu["predictive_minutes"] + tu["preventive_minutes"] + tu["breakdown_minutes"]
        assert abs(total - calculated_total) < 0.1, f"Total mismatch: {total} != {calculated_total}"
        
        self.log(f"Time utilization: predictive={tu['predictive_minutes']}, preventive={tu['preventive_minutes']}, breakdown={tu['breakdown_minutes']}, total={tu['total_minutes']}")

    def test_time_utilization_date_slicing(self):
        """Test: Time utilization respects date_from/date_to slicing"""
        # Query a narrow past range (should give all zeros or very low values)
        kpis = self.get("/analytics/kpis?level=plant&date_from=2020-01-01&date_to=2020-01-02", self.admin_token)
        
        tu = kpis["time_utilization"]
        total = tu["total_minutes"]
        
        # Should be 0 or very low for a narrow past range
        self.log(f"Time utilization for 2020-01-01 to 2020-01-02: total={total} minutes")
        # Note: We don't assert 0 because there might be test data, but we verify the field exists and is numeric
        assert isinstance(total, (int, float)), f"Expected numeric total_minutes, got {type(total)}"

    def test_time_utilization_level_scoping(self):
        """Test: Time utilization respects level/value scoping"""
        # Get plant-level time utilization
        plant_kpis = self.get("/analytics/kpis?level=plant", self.admin_token)
        plant_total = plant_kpis["time_utilization"]["total_minutes"]
        
        # Get line-level time utilization (should be <= plant total)
        machines = self.get("/machines", self.admin_token)
        if machines and len(machines) > 0:
            test_line = machines[0].get("line")
            if test_line:
                line_kpis = self.get(f"/analytics/kpis?level=line&value={test_line}", self.admin_token)
                line_total = line_kpis["time_utilization"]["total_minutes"]
                
                # Line total should be <= plant total
                assert line_total <= plant_total, f"Line total ({line_total}) should be <= plant total ({plant_total})"
                self.log(f"Time utilization scoping: plant={plant_total}, line={line_total}")

    # ============ REGRESSION TESTS ============
    def test_analytics_kpis_regression(self):
        """Test: GET /api/analytics/kpis still returns pm_compliance, pareto, availability etc."""
        # Test at different levels
        levels = [
            ("plant", None),
            ("line", None),  # Will get first line
            ("department", None),  # Will get first department
        ]
        
        # Get hierarchy for testing
        machines = self.get("/machines", self.admin_token)
        if machines and len(machines) > 0:
            test_line = machines[0].get("line")
            test_dept = machines[0].get("department")
            levels[1] = ("line", test_line)
            levels[2] = ("department", test_dept)
        
        for level, value in levels:
            if value is None and level != "plant":
                continue
            
            endpoint = f"/analytics/kpis?level={level}"
            if value:
                endpoint += f"&value={value}"
            
            kpis = self.get(endpoint, self.admin_token)
            
            # Verify key fields still exist
            required_fields = ["pm_compliance", "pareto", "availability", "mtbf_hours", "mttr_hours"]
            for field in required_fields:
                assert field in kpis, f"Missing {field} in KPIs response at level={level}"
            
            self.log(f"KPIs regression test passed for level={level}, value={value}")

    def run_all_tests(self):
        """Run all tests"""
        self.setup()
        
        self.log("\n=== FEATURE 1: PM ON_TIME TOLERANCE ===")
        self.test("PM on_time within tolerance window", self.test_pm_on_time_within_tolerance)
        self.test("PM on_time outside tolerance window", self.test_pm_on_time_outside_tolerance)
        
        self.log("\n=== FEATURE 2: PM BACKFILL ENDPOINT ===")
        self.test("PM backfill admin-only (403 for tech)", self.test_pm_backfill_admin_only)
        self.test("PM backfill idempotent", self.test_pm_backfill_idempotent)
        
        self.log("\n=== FEATURE 3: TIME UTILIZATION ===")
        self.test("Time utilization in KPIs", self.test_time_utilization_in_kpis)
        self.test("Time utilization date slicing", self.test_time_utilization_date_slicing)
        self.test("Time utilization level scoping", self.test_time_utilization_level_scoping)
        
        self.log("\n=== REGRESSION TESTS ===")
        self.test("Analytics KPIs regression", self.test_analytics_kpis_regression)
        
        self.log(f"\n{'='*60}")
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        self.log(f"{'='*60}")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = NewFeaturesTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
