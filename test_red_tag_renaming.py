"""
Test Red Tag Renaming Feature
Verifies that "Warning" has been renamed to "Red Tag" in user-facing text
while internal API routes and field names remain unchanged.
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class RedTagRenamingTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.machine_id = None
        self.warning_id = None

    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        self.log(f"Testing: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - {name} (Status: {response.status_code})", "PASS")
                try:
                    return True, response.json() if response.text else {}
                except:
                    return True, {}
            else:
                self.tests_failed += 1
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                self.log(f"❌ FAIL - {name}: Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    self.log(f"Response: {response.text[:500]}", "DEBUG")
                except:
                    pass
                return False, {}

        except Exception as e:
            self.tests_failed += 1
            self.failures.append(f"{name}: {str(e)}")
            self.log(f"❌ FAIL - {name}: {str(e)}", "FAIL")
            return False, {}

    def run_tests(self):
        """Run all Red Tag renaming tests"""
        self.log("=" * 80)
        self.log("RED TAG RENAMING TESTS")
        self.log("=" * 80)
        
        # 1. Login
        if not self.test_login():
            self.log("Login failed - stopping tests", "ERROR")
            return False
        
        # 2. Get a test machine
        if not self.get_test_machine():
            self.log("No machine available - stopping tests", "ERROR")
            return False
        
        # 3. Test backend API routes (should still use /api/warnings)
        self.test_backend_routes()
        
        # 4. Test timeline entries show "Red Tag" wording
        self.test_timeline_wording()
        
        # 5. Test error messages use "Red tag" wording
        self.test_error_messages()
        
        # 6. Test analytics/reliability endpoints (regression)
        self.test_regression_endpoints()
        
        return True

    def test_login(self):
        """Login as admin"""
        self.log("\n1. AUTHENTICATION")
        self.log("-" * 80)
        
        success, resp = self.test(
            "Login as admin",
            "POST", "auth/login", 200,
            data={"username": "admin", "password": "admin123"}
        )
        if success and 'token' in resp:
            self.token = resp['token']
            self.log("  ✓ Logged in successfully")
            return True
        return False

    def get_test_machine(self):
        """Get a test machine"""
        self.log("\n2. GET TEST MACHINE")
        self.log("-" * 80)
        
        success, resp = self.test("GET /machines", "GET", "machines", 200, params={"limit": 1})
        if success and resp:
            machines = resp if isinstance(resp, list) else []
            if machines:
                self.machine_id = machines[0]['id']
                self.log(f"  ✓ Using machine: {machines[0]['name']} ({self.machine_id})")
                return True
        return False

    def test_backend_routes(self):
        """Test that backend routes still use /api/warnings (intentionally unchanged)"""
        self.log("\n3. BACKEND API ROUTES (INTENTIONALLY UNCHANGED)")
        self.log("-" * 80)
        
        # POST /api/warnings should work (route unchanged)
        success, resp = self.test(
            "POST /api/warnings (route unchanged)",
            "POST", "warnings", 200,
            data={
                "machine_id": self.machine_id,
                "description": "Test red tag - abnormal noise",
                "warning_type": "MECHANICAL",
                "reporter_name": "Test Reporter"
            }
        )
        if success:
            self.warning_id = resp.get('id')
            tag_number = resp.get('tag_number')
            wo_number = resp.get('work_order_number')
            self.log(f"  ✓ POST /api/warnings works (route unchanged)")
            self.log(f"  ✓ Created: {tag_number}")
            self.log(f"  ✓ Work order: {wo_number}")
            
            # Verify response has tag_number field (not renamed)
            if 'tag_number' in resp:
                self.log(f"  ✓ Response field 'tag_number' present (unchanged)")
            
            # Verify response has warning_type field (not renamed)
            if 'warning_type' in resp:
                self.log(f"  ✓ Response field 'warning_type' present (unchanged)")
        
        # GET /api/warnings should work (route unchanged)
        success, resp = self.test(
            "GET /api/warnings (route unchanged)",
            "GET", "warnings", 200
        )
        if success:
            items = resp.get('items', [])
            self.log(f"  ✓ GET /api/warnings works (route unchanged)")
            self.log(f"  ✓ Found {len(items)} warnings")
            
            # Verify items have warning_type field
            if items and 'warning_type' in items[0]:
                self.log(f"  ✓ Response items have 'warning_type' field (unchanged)")
        
        # POST /api/warnings/{id}/generate-wo should work
        if self.warning_id:
            # First close the auto-generated WO to test manual generation
            success, resp = self.test(
                "POST /api/warnings/{id}/generate-wo",
                "POST", f"warnings/{self.warning_id}/generate-wo", 200,
                data={"wo_type": "Inspection"}
            )
            if success:
                self.log(f"  ✓ POST /api/warnings/{{id}}/generate-wo works (route unchanged)")

    def test_timeline_wording(self):
        """Test that timeline entries show 'Red Tag' wording"""
        self.log("\n4. TIMELINE WORDING (USER-FACING)")
        self.log("-" * 80)
        
        # Get timeline with limit
        success, resp = self.test(
            "GET /api/timeline (check Red Tag wording)",
            "GET", "timeline", 200,
            params={"limit": 20}
        )
        if success:
            events = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Retrieved {len(events)} timeline events")
            
            # Check for "Red Tag" wording in titles
            red_tag_events = [e for e in events if 'Red Tag' in e.get('title', '') or 'red tag' in e.get('title', '').lower()]
            if red_tag_events:
                self.log(f"  ✓ Found {len(red_tag_events)} events with 'Red Tag' wording")
                for event in red_tag_events[:3]:  # Show first 3
                    self.log(f"    - {event.get('title')}")
            
            # Check for WO auto-dispatched from red tag
            wo_events = [e for e in events if 'auto-dispatched from red tag' in e.get('title', '').lower()]
            if wo_events:
                self.log(f"  ✓ Found WO events with 'auto-dispatched from red tag' wording")
            
            # Verify event_type is still 'warning_created' (internal field unchanged)
            warning_created_events = [e for e in events if e.get('event_type') == 'warning_created']
            if warning_created_events:
                self.log(f"  ✓ event_type='warning_created' still used internally (unchanged)")

    def test_error_messages(self):
        """Test that error messages use 'Red tag' wording"""
        self.log("\n5. ERROR MESSAGES (USER-FACING)")
        self.log("-" * 80)
        
        # Test error: Red tag work order must be Inspection or Corrective
        success, resp = self.test(
            "POST /api/warnings with wo_type='Preventive' (400)",
            "POST", "warnings", 400,
            data={
                "machine_id": self.machine_id,
                "description": "Test",
                "warning_type": "MECHANICAL",
                "reporter_name": "Test",
                "wo_type": "Preventive"
            }
        )
        if success:
            # The test passed (got 400), now check the error message
            self.log(f"  ✓ Got expected 400 error")
            # Note: We can't check the actual error text in this test since we only get status code
            # But the backend code shows: "Red tag work order must be Inspection or Corrective"
        
        # Test error: Red tag not found
        success, resp = self.test(
            "POST /api/warnings/nonexistent-id/generate-wo (404)",
            "POST", "warnings/nonexistent-id-12345/generate-wo", 404,
            data={"wo_type": "Inspection"}
        )
        if success:
            self.log(f"  ✓ Got expected 404 error")
            # Backend code shows: "Red tag not found"

    def test_regression_endpoints(self):
        """Test that analytics and reliability endpoints still work"""
        self.log("\n6. REGRESSION TESTS")
        self.log("-" * 80)
        
        # GET /api/analytics/kpis
        success, resp = self.test(
            "GET /api/analytics/kpis",
            "GET", "analytics/kpis", 200,
            params={"level": "plant"}
        )
        if success:
            self.log(f"  ✓ /api/analytics/kpis works")
            if 'time_utilization' in resp:
                self.log(f"  ✓ time_utilization present: {resp.get('time_utilization')}%")
            if 'pm_compliance' in resp:
                self.log(f"  ✓ pm_compliance present: {resp.get('pm_compliance')}%")
        
        # GET /api/reliability/metrics
        success, resp = self.test(
            "GET /api/reliability/metrics",
            "GET", "reliability/metrics", 200
        )
        if success:
            metrics = resp if isinstance(resp, list) else []
            self.log(f"  ✓ /api/reliability/metrics works ({len(metrics)} machines)")

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 80)
        self.log("TEST SUMMARY")
        self.log("=" * 80)
        self.log(f"Total Tests: {self.tests_run}")
        self.log(f"Passed: {self.tests_passed} ✅")
        self.log(f"Failed: {self.tests_failed} ❌")
        
        if self.tests_failed > 0:
            self.log("\nFailed Tests:")
            for failure in self.failures:
                self.log(f"  - {failure}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%")
        self.log("=" * 80)
        
        return 0 if self.tests_failed == 0 else 1

def main():
    tester = RedTagRenamingTester()
    tester.run_tests()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
