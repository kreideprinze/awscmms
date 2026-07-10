"""
Phase L Backend Testing: RCA 5-Why, Technician Analytics, Line Runtime, AWS Category Sorting
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class PhaseL_Tester:
    def __init__(self):
        self.admin_token = None
        self.tech_token = None
        self.operator_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_machine_id = None
        self.test_line = None
        self.rca_wo_id = None
        self.origin_wo_id = None
        self.breakdown_id = None

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
            raise AssertionError(f"Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code == 200 else None

    def post(self, endpoint, token, data, expected_status=200):
        """POST request"""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data)
        if r.status_code != expected_status:
            raise AssertionError(f"Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code in (200, 201) else None

    def put(self, endpoint, token, data, expected_status=200):
        """PUT request"""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.put(f"{BASE_URL}{endpoint}", headers=headers, json=data)
        if r.status_code != expected_status:
            raise AssertionError(f"Expected {expected_status}, got {r.status_code}: {r.text}")
        return r.json() if r.status_code == 200 else None

    def setup(self):
        """Setup: login all users, get test machine and line"""
        self.log("=== SETUP ===")
        self.admin_token = self.login("admin", "admin123")
        self.tech_token = self.login("tech", "tech123")
        self.operator_token = self.login("operator", "operator123")
        self.log("All users logged in successfully")

        # Get a test machine
        machines = self.get("/machines", self.admin_token)
        if machines and len(machines) > 0:
            self.test_machine_id = machines[0]["id"]
            self.log(f"Test machine: {machines[0]['name']} ({self.test_machine_id})")

        # Get hierarchy for line testing
        hierarchy = self.get("/hierarchy", self.admin_token)
        if hierarchy and hierarchy.get("lines"):
            self.test_line = hierarchy["lines"][0]["name"]
            self.log(f"Test line: {self.test_line}")

    # ============ RCA 5-WHY MODULE TESTS ============
    def test_rca_trigger_from_long_wo(self):
        """Test: RCA WO auto-created when work order duration exceeds threshold"""
        # Create a Corrective WO
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test Long Duration WO",
            "description": "Testing RCA trigger",
            "wo_type": "Corrective",
            "priority": "high",
            "assigned_to": "tech"
        })
        self.origin_wo_id = wo["id"]
        assert wo["wo_number"], "WO created"

        # Start the WO
        self.put(f"/work-orders/{wo['id']}", self.admin_token, {"action": "start"})

        # Complete with duration_minutes=45 (exceeds 30 min threshold)
        result = self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "complete",
            "duration_minutes": 45,
            "action_taken": "Completed repair"
        })
        assert result["status"] == "PENDING_ADMIN_CLOSURE", "WO completed"

        # Verify RCA WO was created
        wo_detail = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert wo_detail.get("rca_task_id"), "RCA task ID set on origin WO"
        self.rca_wo_id = wo_detail["rca_task_id"]

        # Get RCA WO details
        rca_wo = self.get(f"/work-orders/{self.rca_wo_id}", self.admin_token)
        assert rca_wo["wo_type"] == "RCA", "RCA WO type is RCA"
        assert rca_wo["assigned_to"] == "tech", "RCA assigned to attending technician"
        assert rca_wo["priority"] == "high", "RCA priority is high"
        assert rca_wo.get("source_work_order_id") == wo["id"], "RCA links back to origin WO"
        self.log(f"RCA WO created: {rca_wo['wo_number']}")

    def test_rca_wo_cannot_complete_without_submission(self):
        """Test: RCA WO complete action returns 400 before RCA submission"""
        if not self.rca_wo_id:
            raise AssertionError("RCA WO not created in previous test")

        # Try to complete without RCA submission
        self.put(f"/work-orders/{self.rca_wo_id}", self.tech_token, {
            "action": "complete"
        }, expected_status=400)
        self.log("RCA WO correctly rejects completion without 5-Why submission")

    def test_rca_submission_validation(self):
        """Test: RCA submission validates all 5 whys + root_cause + corrective_action"""
        if not self.rca_wo_id:
            raise AssertionError("RCA WO not created")

        # Test: < 5 whys rejected
        self.put(f"/work-orders/{self.rca_wo_id}/rca", self.tech_token, {
            "whys": ["Why 1", "Why 2", "Why 3"],
            "root_cause": "Root cause",
            "corrective_action": "Action"
        }, expected_status=400)

        # Test: empty whys rejected
        self.put(f"/work-orders/{self.rca_wo_id}/rca", self.tech_token, {
            "whys": ["Why 1", "", "Why 3", "Why 4", "Why 5"],
            "root_cause": "Root cause",
            "corrective_action": "Action"
        }, expected_status=400)

        # Test: empty root_cause rejected
        self.put(f"/work-orders/{self.rca_wo_id}/rca", self.tech_token, {
            "whys": ["Why 1", "Why 2", "Why 3", "Why 4", "Why 5"],
            "root_cause": "",
            "corrective_action": "Action"
        }, expected_status=400)

        # Test: empty corrective_action rejected
        self.put(f"/work-orders/{self.rca_wo_id}/rca", self.tech_token, {
            "whys": ["Why 1", "Why 2", "Why 3", "Why 4", "Why 5"],
            "root_cause": "Root cause",
            "corrective_action": ""
        }, expected_status=400)

        # Test: full submission succeeds
        result = self.put(f"/work-orders/{self.rca_wo_id}/rca", self.tech_token, {
            "whys": ["Bearing failed", "Lack of lubrication", "Maintenance schedule missed", "Understaffing", "Budget constraints"],
            "root_cause": "Inadequate preventive maintenance program",
            "corrective_action": "Implement automated PM scheduling and hire additional maintenance staff"
        })
        assert result["ok"], "RCA submission successful"
        assert result["work_order"]["rca"], "RCA data saved"
        self.log("RCA submission validation working correctly")

    def test_rca_submission_permission(self):
        """Test: RCA submission by non-assigned technician returns 403; admin can submit"""
        if not self.rca_wo_id:
            raise AssertionError("RCA WO not created")

        # Create another WO and trigger RCA for permission testing
        wo2 = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test Permission WO",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        self.put(f"/work-orders/{wo2['id']}", self.admin_token, {"action": "start"})
        self.put(f"/work-orders/{wo2['id']}", self.tech_token, {
            "action": "complete",
            "duration_minutes": 35
        })
        wo2_detail = self.get(f"/work-orders/{wo2['id']}", self.admin_token)
        rca2_id = wo2_detail.get("rca_task_id")

        if rca2_id:
            # Try to submit as operator (not assigned) - should fail
            self.put(f"/work-orders/{rca2_id}/rca", self.operator_token, {
                "whys": ["W1", "W2", "W3", "W4", "W5"],
                "root_cause": "Root",
                "corrective_action": "Action"
            }, expected_status=403)

            # Admin can submit
            self.put(f"/work-orders/{rca2_id}/rca", self.admin_token, {
                "whys": ["W1", "W2", "W3", "W4", "W5"],
                "root_cause": "Root",
                "corrective_action": "Action"
            })
            self.log("RCA permission checks working correctly")

    def test_rca_edit_after_completion_rejected(self):
        """Test: After completion, RCA edits rejected (400)"""
        if not self.rca_wo_id:
            raise AssertionError("RCA WO not created")

        # Complete the RCA WO
        self.put(f"/work-orders/{self.rca_wo_id}", self.tech_token, {"action": "complete"})

        # Try to edit RCA - should fail
        self.put(f"/work-orders/{self.rca_wo_id}/rca", self.tech_token, {
            "whys": ["New W1", "New W2", "New W3", "New W4", "New W5"],
            "root_cause": "New root",
            "corrective_action": "New action"
        }, expected_status=400)
        self.log("RCA edit after completion correctly rejected")

    def test_rca_lifecycle(self):
        """Test: RCA lifecycle - tech complete -> PENDING_ADMIN_CLOSURE, tech close -> 403, admin close -> CLOSED"""
        if not self.rca_wo_id:
            raise AssertionError("RCA WO not created")

        # Verify status is PENDING_ADMIN_CLOSURE after tech completion
        rca_wo = self.get(f"/work-orders/{self.rca_wo_id}", self.admin_token)
        assert rca_wo["status"] == "PENDING_ADMIN_CLOSURE", "RCA WO in PENDING_ADMIN_CLOSURE"

        # Tech tries to close - should fail
        self.put(f"/work-orders/{self.rca_wo_id}", self.tech_token, {"action": "close"}, expected_status=403)

        # Admin closes
        result = self.put(f"/work-orders/{self.rca_wo_id}", self.admin_token, {"action": "close"})
        assert result["status"] == "CLOSED", "Admin closed RCA WO"
        self.log("RCA lifecycle working correctly")

    def test_short_wo_no_rca_trigger(self):
        """Test: Short WO (10 min) does NOT trigger RCA"""
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Short WO",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        self.put(f"/work-orders/{wo['id']}", self.admin_token, {"action": "start"})
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "complete",
            "duration_minutes": 10
        })
        wo_detail = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert not wo_detail.get("rca_task_id"), "No RCA triggered for short WO"
        self.log("Short WO correctly does not trigger RCA")

    def test_breakdown_rca_trigger(self):
        """Test: Breakdown with downtime > 30 min triggers RCA WO"""
        # Create breakdown
        bd = self.post("/breakdowns", self.admin_token, {
            "machine_id": self.test_machine_id,
            "description": "Test breakdown for RCA trigger",
            "breakdown_type": "MECHANICAL",
            "auto_create_work_order": True
        })
        self.breakdown_id = bd["id"]

        # Assign and start
        self.put(f"/breakdowns/{bd['id']}", self.admin_token, {
            "action": "assign",
            "assigned_to": "tech"
        })
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})

        # Complete with downtime > 30 min (requires root_cause per existing rule)
        # Calculate end_time to be 35 minutes after start_time
        from datetime import datetime, timedelta, timezone
        start_dt = datetime.fromisoformat(bd["start_time"].replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(minutes=35)
        end_time = end_dt.isoformat()

        result = self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "end_time": end_time,
            "root_cause": "Test root cause for breakdown",
            "action_taken": "Repaired"
        })
        assert result.get("downtime_minutes", 0) > 30, "Downtime exceeds 30 min"

        # Verify RCA WO created
        bd_detail = self.get(f"/breakdowns/{bd['id']}", self.admin_token)
        assert bd_detail.get("rca_task_id"), "RCA task ID set on breakdown"

        # Verify RCA WO details
        rca_wo = self.get(f"/work-orders/{bd_detail['rca_task_id']}", self.admin_token)
        assert rca_wo["wo_type"] == "RCA", "RCA WO created"
        assert rca_wo.get("source_breakdown_id") == bd["id"], "RCA links to breakdown"
        self.log(f"Breakdown RCA trigger working: {rca_wo['wo_number']}")

    # ============ TECHNICIAN ANALYTICS TESTS ============
    def test_technician_analytics_admin_only(self):
        """Test: GET /api/analytics/technicians -> 403 for tech and operator, 200 for admin"""
        # Tech tries - should fail
        self.get("/analytics/technicians", self.tech_token, expected_status=403)

        # Operator tries - should fail
        self.get("/analytics/technicians", self.operator_token, expected_status=403)

        # Admin succeeds
        result = self.get("/analytics/technicians", self.admin_token)
        assert "technicians" in result, "Technicians array present"
        assert "on_time_target_minutes" in result, "On-time target present"
        self.log("Technician analytics admin-only access working")

    def test_technician_analytics_filters(self):
        """Test: Technician analytics accepts filters (date_from, date_to, line, department, wo_type)"""
        # Test with all filters
        today = datetime.now().date().isoformat()
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

        result = self.get(
            f"/analytics/technicians?date_from={yesterday}&date_to={today}&line={self.test_line}&department=Production&wo_type=Corrective",
            self.admin_token
        )
        assert "technicians" in result, "Filters accepted"
        assert result.get("filters"), "Filters echoed back"
        self.log("Technician analytics filters working")

    # ============ LINE-LEVEL RUNTIME TESTS ============
    def test_line_runtime_logging(self):
        """Test: POST /api/runtime-logs with line creates line log and fans out to machines"""
        if not self.test_line:
            raise AssertionError("No test line available")

        today = datetime.now().date().isoformat()

        # Post line runtime
        result = self.post("/runtime-logs", self.admin_token, {
            "line": self.test_line,
            "date": today,
            "calendar_hours": 24,
            "run_hours": 20
        })
        assert result["line"] == self.test_line, "Line log created"
        assert result["machines_count"] > 0, "Machines count present"
        assert result["run_hours"] == 20, "Run hours correct"
        self.log(f"Line runtime logged: {result['machines_count']} machines inherit 20h")

        # Verify line log exists
        line_logs = self.get(f"/line-runtime-logs?line={self.test_line}&date_from={today}&date_to={today}", self.admin_token)
        assert line_logs["total"] > 0, "Line log found"

        # Verify per-machine logs created (fanned out)
        machine_logs = self.get(f"/runtime-logs?line={self.test_line}&date_from={today}&date_to={today}", self.admin_token)
        assert machine_logs["total"] > 0, "Per-machine logs created"
        for log in machine_logs["items"]:
            assert log["run_hours"] == 20, "Machine inherited line runtime"
            assert log["source"] == "line", "Source is 'line'"

    def test_line_runtime_validation(self):
        """Test: run_hours > calendar_hours -> 400; unknown line -> 404"""
        today = datetime.now().date().isoformat()

        # Test: run_hours > calendar_hours
        self.post("/runtime-logs", self.admin_token, {
            "line": self.test_line,
            "date": today,
            "calendar_hours": 20,
            "run_hours": 25
        }, expected_status=400)

        # Test: unknown line
        self.post("/runtime-logs", self.admin_token, {
            "line": "NonExistentLine123",
            "date": today,
            "calendar_hours": 24,
            "run_hours": 20
        }, expected_status=404)
        self.log("Line runtime validation working")

    def test_line_runtime_csv_import(self):
        """Test: CSV import with line,date,run_hours format"""
        csv_text = f"line,date,run_hours,calendar_hours\n{self.test_line},2025-01-10,22,24\n{self.test_line},2025-01-11,23,24"

        # Preview
        preview = self.post("/runtime-logs/import", self.admin_token, {
            "csv_text": csv_text,
            "apply": False
        })
        assert preview["preview"], "Preview mode"
        assert preview["valid_rows"] == 2, "2 valid rows"
        assert len(preview["errors"]) == 0, "No errors"

        # Apply
        result = self.post("/runtime-logs/import", self.admin_token, {
            "csv_text": csv_text,
            "apply": True
        })
        assert result["imported"] == 2, "2 rows imported"
        assert result["machines_affected"] > 0, "Machines affected"
        self.log(f"CSV import working: {result['imported']} rows, {result['machines_affected']} machines")

    # ============ AWS CATEGORY SORTING TESTS ============
    def test_aws_failure_categories(self):
        """Test: GET /api/reliability/metrics includes failure_categories and dominant_category"""
        metrics = self.get("/reliability/metrics", self.admin_token)
        if len(metrics) > 0:
            # Check if any machine has failure_categories
            has_categories = any(m.get("failure_categories") for m in metrics)
            if has_categories:
                for m in metrics:
                    if m.get("failure_categories"):
                        assert isinstance(m["failure_categories"], dict), "failure_categories is dict"
                        assert m.get("dominant_category"), "dominant_category present"
                        self.log(f"Machine {m['machine_name']}: {m['failure_categories']}, dominant: {m['dominant_category']}")
            else:
                self.log("No machines with failure categories yet (no breakdowns recorded)")
        else:
            self.log("No reliability metrics yet")

    def test_aws_category_filter(self):
        """Test: ?category=MECHANICAL returns only machines with dominant MECHANICAL"""
        metrics = self.get("/reliability/metrics?category=MECHANICAL", self.admin_token)
        for m in metrics:
            if m.get("dominant_category"):
                assert m["dominant_category"] == "MECHANICAL", "Only MECHANICAL machines returned"
        self.log("AWS category filter working")

    def run_all_tests(self):
        """Run all Phase L tests"""
        self.log("=" * 60)
        self.log("PHASE L BACKEND TESTING")
        self.log("=" * 60)

        self.setup()

        self.log("\n=== RCA 5-WHY MODULE TESTS ===")
        self.test("RCA trigger from long WO", self.test_rca_trigger_from_long_wo)
        self.test("RCA WO cannot complete without submission", self.test_rca_wo_cannot_complete_without_submission)
        self.test("RCA submission validation", self.test_rca_submission_validation)
        self.test("RCA submission permission", self.test_rca_submission_permission)
        self.test("RCA edit after completion rejected", self.test_rca_edit_after_completion_rejected)
        self.test("RCA lifecycle", self.test_rca_lifecycle)
        self.test("Short WO no RCA trigger", self.test_short_wo_no_rca_trigger)
        self.test("Breakdown RCA trigger", self.test_breakdown_rca_trigger)

        self.log("\n=== TECHNICIAN ANALYTICS TESTS ===")
        self.test("Technician analytics admin-only", self.test_technician_analytics_admin_only)
        self.test("Technician analytics filters", self.test_technician_analytics_filters)

        self.log("\n=== LINE-LEVEL RUNTIME TESTS ===")
        self.test("Line runtime logging", self.test_line_runtime_logging)
        self.test("Line runtime validation", self.test_line_runtime_validation)
        self.test("Line runtime CSV import", self.test_line_runtime_csv_import)

        self.log("\n=== AWS CATEGORY SORTING TESTS ===")
        self.test("AWS failure categories", self.test_aws_failure_categories)
        self.test("AWS category filter", self.test_aws_category_filter)

        self.log("\n" + "=" * 60)
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        self.log("=" * 60)

        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = PhaseL_Tester()
    sys.exit(tester.run_all_tests())
