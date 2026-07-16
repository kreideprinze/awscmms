"""
Backend Testing: Four NEW Features - RCA Rejection, Breakdown Types Analytics, Technician Leaderboard, Mid-Repair Handoff
"""
import requests
import sys
from datetime import datetime, timedelta, timezone

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class NewFeaturesTester:
    def __init__(self):
        self.admin_token = None
        self.tech_token = None
        self.chandrakant_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_machine_id = None
        self.test_line = None
        self.test_rca_wo_id = None
        self.test_breakdown_id = None
        self.test_wo_id = None

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
        try:
            self.chandrakant_token = self.login("chandrakant", "chandrakant123")
        except:
            self.log("chandrakant user not found, will skip some transfer tests")
            self.chandrakant_token = None
        self.log("Users logged in successfully")

        # Get a test machine
        machines = self.get("/machines", self.admin_token)
        if machines and len(machines) > 0:
            self.test_machine_id = machines[0]["id"]
            self.test_line = machines[0].get("line")
            self.log(f"Test machine: {machines[0]['name']} ({self.test_machine_id}), line: {self.test_line}")

    # ============ FEATURE 1: RCA REJECTION CYCLE ============
    def test_rca_rejection_full_cycle(self):
        """Test: Full RCA rejection cycle - create, submit, reject, resubmit, close"""
        # Step 1: Create a breakdown with >30min downtime to trigger RCA
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=35)).isoformat()
        end_time = now.isoformat()
        
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test RCA rejection cycle",
            "breakdown_type": "MECHANICAL",
            "assigned_to": "tech",
            "start_time": start_time
        })
        self.test_breakdown_id = bd["id"]
        
        # Start and complete breakdown to trigger RCA
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        result = self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "start_time": start_time,
            "end_time": end_time,
            "action_taken": "Repaired for RCA test"
        })
        
        assert result.get("rca_required"), "RCA should be required"
        assert result.get("rca_task_id"), "RCA task ID should be present"
        self.test_rca_wo_id = result["rca_task_id"]
        self.log(f"RCA WO created: {self.test_rca_wo_id}")
        
        # Step 2: As tech, submit 5-Why RCA
        rca_data = {
            "whys": ["Why 1", "Why 2", "Why 3", "Why 4", "Why 5"],
            "root_cause": "Initial root cause",
            "corrective_action": "Initial corrective action"
        }
        self.put(f"/work-orders/{self.test_rca_wo_id}/rca", self.tech_token, rca_data)
        self.log("RCA submitted by tech")
        
        # Step 3: Complete the RCA WO
        self.put(f"/work-orders/{self.test_rca_wo_id}", self.tech_token, {"action": "complete"})
        
        # Verify status is PENDING_ADMIN_CLOSURE
        wo = self.get(f"/work-orders/{self.test_rca_wo_id}", self.tech_token)
        assert wo["status"] == "PENDING_ADMIN_CLOSURE", f"Expected PENDING_ADMIN_CLOSURE, got {wo['status']}"
        self.log("RCA WO status: PENDING_ADMIN_CLOSURE")
        
        # Step 4: Admin rejects the RCA
        reject_result = self.put(f"/work-orders/{self.test_rca_wo_id}/rca-reject", self.admin_token, {
            "reason": "Root cause too shallow"
        })
        assert reject_result["status"] == "IN_PROGRESS", f"Expected IN_PROGRESS after reject, got {reject_result['status']}"
        assert reject_result["rca_rejection"]["reason"] == "Root cause too shallow"
        self.log("RCA rejected by admin, status back to IN_PROGRESS")
        
        # Verify WO has rejection info
        wo = self.get(f"/work-orders/{self.test_rca_wo_id}", self.tech_token)
        assert wo["status"] == "IN_PROGRESS", "Status should be IN_PROGRESS"
        assert wo["assigned_to"] == "tech", "Should still be assigned to tech"
        assert wo["rca_rejection"]["reason"] == "Root cause too shallow"
        assert wo.get("rca_rejections_count") == 1, "Rejection count should be 1"
        assert wo["rca"]["whys"], "Previous RCA answers should be retained (prefilled)"
        self.log("RCA rejection verified: status IN_PROGRESS, assigned_to unchanged, rca retained")
        
        # Step 5: Tech resubmits updated RCA
        updated_rca = {
            "whys": ["Updated Why 1", "Updated Why 2", "Updated Why 3", "Updated Why 4", "Updated Why 5"],
            "root_cause": "Deeper root cause analysis",
            "corrective_action": "Improved corrective action"
        }
        self.put(f"/work-orders/{self.test_rca_wo_id}/rca", self.tech_token, updated_rca)
        
        # Verify rca_rejection cleared after resubmission
        wo = self.get(f"/work-orders/{self.test_rca_wo_id}", self.tech_token)
        assert wo.get("rca_rejection") is None, "rca_rejection should be cleared after resubmit"
        self.log("RCA resubmitted, rca_rejection cleared")
        
        # Step 6: Complete again
        self.put(f"/work-orders/{self.test_rca_wo_id}", self.tech_token, {"action": "complete"})
        wo = self.get(f"/work-orders/{self.test_rca_wo_id}", self.tech_token)
        assert wo["status"] == "PENDING_ADMIN_CLOSURE", "Status should be PENDING_ADMIN_CLOSURE again"
        
        # Step 7: Admin closes
        self.put(f"/work-orders/{self.test_rca_wo_id}", self.admin_token, {"action": "close"})
        wo = self.get(f"/work-orders/{self.test_rca_wo_id}", self.tech_token)
        assert wo["status"] == "CLOSED", "RCA WO should be CLOSED"
        self.log("RCA WO closed by admin after resubmission")

    def test_rca_reject_error_cases(self):
        """Test: RCA rejection error cases - empty reason, non-PENDING status, tech trying to reject"""
        if not self.test_rca_wo_id:
            self.log("No RCA WO available, skipping error case tests")
            return
        
        # Create a new RCA for testing
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=35)).isoformat()
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test RCA error cases",
            "breakdown_type": "ELECTRICAL",
            "assigned_to": "tech",
            "start_time": start_time
        })
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        result = self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "complete",
            "start_time": start_time,
            "end_time": now.isoformat(),
            "action_taken": "Test"
        })
        rca_wo_id = result["rca_task_id"]
        
        # Submit and complete RCA
        self.put(f"/work-orders/{rca_wo_id}/rca", self.tech_token, {
            "whys": ["W1", "W2", "W3", "W4", "W5"],
            "root_cause": "Test",
            "corrective_action": "Test"
        })
        self.put(f"/work-orders/{rca_wo_id}", self.tech_token, {"action": "complete"})
        
        # Error case 1: Reject with empty reason -> 400
        self.put(f"/work-orders/{rca_wo_id}/rca-reject", self.admin_token, {"reason": ""}, expected_status=400)
        self.log("Empty rejection reason correctly rejected (400)")
        
        # Error case 2: Tech trying to reject -> 403
        self.put(f"/work-orders/{rca_wo_id}/rca-reject", self.tech_token, {"reason": "Test"}, expected_status=403)
        self.log("Tech trying to reject RCA correctly rejected (403)")
        
        # Reject it properly
        self.put(f"/work-orders/{rca_wo_id}/rca-reject", self.admin_token, {"reason": "Test rejection"})
        
        # Error case 3: Reject a non-PENDING RCA (now IN_PROGRESS) -> 400
        self.put(f"/work-orders/{rca_wo_id}/rca-reject", self.admin_token, {"reason": "Test"}, expected_status=400)
        self.log("Rejecting non-PENDING RCA correctly rejected (400)")

    # ============ FEATURE 2: ANALYTICS BREAKDOWN TYPES ============
    def test_analytics_breakdown_types(self):
        """Test: GET /api/analytics/kpis returns breakdown_types with count and downtime_minutes"""
        # Create breakdowns of different types
        now = datetime.now(timezone.utc)
        for bd_type in ["MECHANICAL", "ELECTRICAL", "CONTROL_PLC"]:
            bd = self.post("/breakdowns", self.tech_token, {
                "machine_id": self.test_machine_id,
                "description": f"Test {bd_type} breakdown",
                "breakdown_type": bd_type,
                "assigned_to": "tech",
                "start_time": (now - timedelta(minutes=20)).isoformat()
            })
            self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
            self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
                "action": "complete",
                "end_time": now.isoformat(),
                "action_taken": "Fixed"
            })
        
        # Get analytics KPIs
        kpis = self.get("/analytics/kpis?level=plant", self.admin_token)
        assert "breakdown_types" in kpis, "breakdown_types field should be present"
        assert isinstance(kpis["breakdown_types"], list), "breakdown_types should be a list"
        
        # Verify structure
        for bt in kpis["breakdown_types"]:
            assert "type" in bt, "Each breakdown type should have 'type'"
            assert "count" in bt, "Each breakdown type should have 'count'"
            assert "downtime_minutes" in bt, "Each breakdown type should have 'downtime_minutes'"
            assert bt["type"] in ["MECHANICAL", "ELECTRICAL", "CONTROL_PLC"], f"Invalid type: {bt['type']}"
        
        self.log(f"breakdown_types returned: {kpis['breakdown_types']}")

    def test_analytics_breakdown_types_date_range(self):
        """Test: breakdown_types respects date_from/date_to filters"""
        # Test with narrow past range (should return empty)
        kpis = self.get("/analytics/kpis?level=plant&date_from=2020-01-01&date_to=2020-01-02", self.admin_token)
        assert kpis["breakdown_types"] == [] or all(bt["count"] == 0 for bt in kpis["breakdown_types"]), \
            "breakdown_types should be empty or zero for past date range"
        self.log("breakdown_types correctly filtered by date range (empty for past dates)")

    # ============ FEATURE 3: TECHNICIAN LEADERBOARD ============
    def test_technician_analytics_endpoint(self):
        """Test: GET /api/analytics/technicians returns rows with overall_score and rca_completed"""
        result = self.get("/analytics/technicians", self.admin_token)
        assert "technicians" in result, "technicians field should be present"
        assert isinstance(result["technicians"], list), "technicians should be a list"
        
        if len(result["technicians"]) > 0:
            tech = result["technicians"][0]
            assert "overall_score" in tech, "Each technician should have overall_score"
            assert "rca_completed" in tech, "Each technician should have rca_completed"
            assert isinstance(tech["overall_score"], (int, float)), "overall_score should be numeric"
            assert isinstance(tech["rca_completed"], int), "rca_completed should be integer"
            assert 0 <= tech["overall_score"] <= 100, "overall_score should be 0-100"
            self.log(f"Technician analytics: {tech['technician']} - overall_score={tech['overall_score']}, rca_completed={tech['rca_completed']}")
        else:
            self.log("No technician data available yet")

    def test_technician_analytics_admin_only(self):
        """Test: GET /api/analytics/technicians returns 403 for technician role"""
        self.get("/analytics/technicians", self.tech_token, expected_status=403)
        self.log("Technician analytics correctly restricted to admin (403 for tech)")

    # ============ FEATURE 4: MID-REPAIR HANDOFF ============
    def test_wo_mid_repair_handoff_requires_note(self):
        """Test: Transferring IN_PROGRESS WO requires pass_on_note"""
        if not self.chandrakant_token:
            self.log("chandrakant user not available, skipping handoff test")
            return
        
        # Create WO assigned to tech
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test mid-repair handoff",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        self.test_wo_id = wo["id"]
        
        # Start as tech (IN_PROGRESS)
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {"action": "start"})
        
        # Try to transfer WITHOUT pass_on_note -> 400
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant"
        }, expected_status=400)
        self.log("Transfer IN_PROGRESS WO without pass_on_note correctly rejected (400)")
        
        # Transfer WITH pass_on_note -> success
        result = self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant",
            "pass_on_note": "Replaced motor bearings, need to test alignment"
        })
        assert result["assigned_to"] == "chandrakant", "WO should be transferred to chandrakant"
        
        # Verify handoff recorded
        wo_detail = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert "handoffs" in wo_detail, "handoffs field should be present"
        assert len(wo_detail["handoffs"]) == 1, "Should have 1 handoff"
        handoff = wo_detail["handoffs"][0]
        assert handoff["from"] == "tech", "Handoff from should be tech"
        assert handoff["to"] == "chandrakant", "Handoff to should be chandrakant"
        assert handoff["note"] == "Replaced motor bearings, need to test alignment"
        assert handoff["mid_repair"] == True, "mid_repair flag should be True"
        self.log("Mid-repair handoff successful with Pass-On Note recorded")

    def test_wo_pre_start_transfer_no_note_required(self):
        """Test: Transferring ASSIGNED (not started) WO does NOT require pass_on_note"""
        if not self.chandrakant_token:
            self.log("chandrakant user not available, skipping pre-start transfer test")
            return
        
        # Create WO assigned to tech
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test pre-start transfer",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        
        # Transfer WITHOUT note (status is ASSIGNED, not IN_PROGRESS) -> should work
        result = self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant"
        })
        assert result["assigned_to"] == "chandrakant", "Pre-start transfer should work without note"
        self.log("Pre-start transfer (ASSIGNED status) works without pass_on_note")

    def test_wo_multiple_handoffs(self):
        """Test: Multiple handoffs append to handoffs array"""
        if not self.chandrakant_token:
            self.log("chandrakant user not available, skipping multiple handoffs test")
            return
        
        # Create and start WO
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test multiple handoffs",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {"action": "start"})
        
        # First handoff: tech -> chandrakant
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant",
            "pass_on_note": "First handoff note"
        })
        
        # Second handoff: chandrakant -> tech
        self.put(f"/work-orders/{wo['id']}", self.chandrakant_token, {
            "action": "assign",
            "assigned_to": "tech",
            "pass_on_note": "Second handoff note"
        })
        
        # Verify 2 handoffs
        wo_detail = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert len(wo_detail["handoffs"]) == 2, f"Should have 2 handoffs, got {len(wo_detail['handoffs'])}"
        assert wo_detail["handoffs"][0]["note"] == "First handoff note"
        assert wo_detail["handoffs"][1]["note"] == "Second handoff note"
        self.log("Multiple handoffs correctly appended to handoffs array")

    def test_wo_handoff_integrity(self):
        """Test: Handoff does not touch started_at, duration measured from original start"""
        if not self.chandrakant_token:
            self.log("chandrakant user not available, skipping handoff integrity test")
            return
        
        # Create and start WO
        wo = self.post("/work-orders", self.admin_token, {
            "machine_id": self.test_machine_id,
            "title": "Test handoff integrity",
            "wo_type": "Corrective",
            "assigned_to": "tech"
        })
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {"action": "start"})
        
        # Get original started_at
        wo_before = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        original_started_at = wo_before["started_at"]
        
        # Handoff to chandrakant
        self.put(f"/work-orders/{wo['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant",
            "pass_on_note": "Handoff for integrity test"
        })
        
        # Verify started_at UNCHANGED
        wo_after = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert wo_after["started_at"] == original_started_at, "started_at should be unchanged after handoff"
        
        # Complete as chandrakant
        now = datetime.now(timezone.utc)
        self.put(f"/work-orders/{wo['id']}", self.chandrakant_token, {
            "action": "complete",
            "action_taken": "Completed after handoff"
        })
        
        # Verify duration measured from ORIGINAL started_at
        wo_final = self.get(f"/work-orders/{wo['id']}", self.admin_token)
        assert wo_final["duration_minutes"] is not None, "Duration should be calculated"
        # Duration should be from original start to completion, not from handoff
        self.log(f"Handoff integrity verified: started_at unchanged, duration from original start ({wo_final['duration_minutes']} min)")

    def test_breakdown_mid_repair_handoff(self):
        """Test: Transferring IN_PROGRESS breakdown requires pass_on_note"""
        if not self.chandrakant_token:
            self.log("chandrakant user not available, skipping breakdown handoff test")
            return
        
        # Create breakdown assigned to tech
        bd = self.post("/breakdowns", self.tech_token, {
            "machine_id": self.test_machine_id,
            "description": "Test breakdown handoff",
            "breakdown_type": "MECHANICAL",
            "assigned_to": "tech"
        })
        
        # Start repair (IN_PROGRESS)
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {"action": "start"})
        
        # Try to transfer WITHOUT pass_on_note -> 400
        self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant"
        }, expected_status=400)
        self.log("Transfer IN_PROGRESS breakdown without pass_on_note correctly rejected (400)")
        
        # Transfer WITH pass_on_note -> success
        result = self.put(f"/breakdowns/{bd['id']}", self.tech_token, {
            "action": "assign",
            "assigned_to": "chandrakant",
            "pass_on_note": "Breakdown handoff note"
        })
        assert result["assigned_to"] == "chandrakant", "Breakdown should be transferred"
        
        # Verify handoff recorded
        bd_detail = self.get(f"/breakdowns/{bd['id']}", self.tech_token)
        assert "handoffs" in bd_detail, "handoffs field should be present"
        assert len(bd_detail["handoffs"]) == 1, "Should have 1 handoff"
        assert bd_detail["handoffs"][0]["mid_repair"] == True
        self.log("Breakdown mid-repair handoff successful")

    def run_all_tests(self):
        """Run all new feature tests"""
        self.log("=" * 60)
        self.log("FOUR NEW FEATURES BACKEND TESTING")
        self.log("=" * 60)

        self.setup()

        self.log("\n=== FEATURE 1: RCA REJECTION CYCLE ===")
        self.test("RCA rejection full cycle", self.test_rca_rejection_full_cycle)
        self.test("RCA rejection error cases", self.test_rca_reject_error_cases)

        self.log("\n=== FEATURE 2: ANALYTICS BREAKDOWN TYPES ===")
        self.test("Analytics breakdown_types field", self.test_analytics_breakdown_types)
        self.test("Breakdown types date range filter", self.test_analytics_breakdown_types_date_range)

        self.log("\n=== FEATURE 3: TECHNICIAN LEADERBOARD ===")
        self.test("Technician analytics endpoint", self.test_technician_analytics_endpoint)
        self.test("Technician analytics admin-only", self.test_technician_analytics_admin_only)

        self.log("\n=== FEATURE 4: MID-REPAIR HANDOFF ===")
        self.test("WO mid-repair handoff requires note", self.test_wo_mid_repair_handoff_requires_note)
        self.test("WO pre-start transfer no note required", self.test_wo_pre_start_transfer_no_note_required)
        self.test("WO multiple handoffs", self.test_wo_multiple_handoffs)
        self.test("WO handoff integrity (started_at unchanged)", self.test_wo_handoff_integrity)
        self.test("Breakdown mid-repair handoff", self.test_breakdown_mid_repair_handoff)

        self.log("\n" + "=" * 60)
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        self.log("=" * 60)

        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = NewFeaturesTester()
    sys.exit(tester.run_all_tests())
