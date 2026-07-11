"""
Quick Backend Sanity Check for New Features
Tests the new backend endpoints added for the frontend update
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class NewFeaturesTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.tokens = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, data=None, token=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

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
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                self.log(f"❌ FAIL - {name}: Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    self.log(f"Response: {response.text[:300]}", "DEBUG")
                except:
                    pass
                return False, {}

        except Exception as e:
            self.failures.append(f"{name}: {str(e)}")
            self.log(f"❌ FAIL - {name}: {str(e)}", "FAIL")
            return False, {}

    def run_tests(self):
        """Run all new feature tests"""
        self.log("=" * 80)
        self.log("NEW FEATURES BACKEND SANITY CHECK")
        self.log("=" * 80)
        
        # Login
        self.log("\n1. AUTHENTICATION")
        success, resp = self.test("Login as admin", "POST", "auth/login", 200,
                                 data={"username": "admin", "password": "admin123"})
        if not success:
            self.log("Login failed - stopping tests", "ERROR")
            return False
        self.tokens['admin'] = resp['token']
        
        success, resp = self.test("Login as tech", "POST", "auth/login", 200,
                                 data={"username": "tech", "password": "tech123"})
        if success:
            self.tokens['tech'] = resp['token']
        
        # Test new line-kpis endpoint with hours parameter
        self.log("\n2. CONTROL ROOM LINE KPIs - NEW ENDPOINTS")
        success, resp = self.test("GET /control-room/line-kpis?hours=8", "GET", 
                                 "control-room/line-kpis", 200,
                                 token=self.tokens['admin'],
                                 params={"hours": 8})
        if success:
            lines = resp.get('lines', [])
            self.log(f"  ✓ Line KPIs (8h window): {len(lines)} lines")
            if lines:
                line = lines[0]
                self.log(f"  ✓ Sample line: {line.get('line')} - Availability: {line.get('availability')}%, Downtime: {line.get('downtime_minutes')}min")
                if 'active_breakdown_since' in line:
                    self.log(f"  ✓ active_breakdown_since field present: {line.get('active_breakdown_since')}")
                if 'sections' in line:
                    self.log(f"  ✓ sections field present: {len(line.get('sections', []))} sections")
        
        # Test with custom date range
        today = datetime.utcnow().date()
        date_from = (today - timedelta(days=7)).isoformat()
        date_to = today.isoformat()
        success, resp = self.test("GET /control-room/line-kpis?date_from&date_to", "GET",
                                 "control-room/line-kpis", 200,
                                 token=self.tokens['admin'],
                                 params={"date_from": date_from, "date_to": date_to})
        if success:
            self.log(f"  ✓ Custom date range works: {date_from} to {date_to}")
        
        # Test work order claim action
        self.log("\n3. WORK ORDER CLAIM ACTION")
        
        # First, create an UNASSIGNED work order
        success, machines_resp = self.test("GET machines", "GET", "machines", 200,
                                          token=self.tokens['admin'])
        if success and machines_resp:
            machine = machines_resp[0]
            
            # Create WO without assigned_to (should be UNASSIGNED)
            success, wo_resp = self.test("POST /work-orders (unassigned)", "POST", "work-orders", 200,
                                        token=self.tokens['admin'],
                                        data={
                                            "machine_id": machine['id'],
                                            "title": "Test unassigned WO",
                                            "description": "Testing claim action",
                                            "wo_type": "Corrective",
                                            "priority": "medium"
                                        })
            if success:
                wo_id = wo_resp.get('id')
                wo_number = wo_resp.get('wo_number')
                self.log(f"  ✓ Unassigned WO created: {wo_number}")
                
                # Verify it's UNASSIGNED (status OPEN, no assigned_to)
                if wo_resp.get('status') == 'OPEN' and not wo_resp.get('assigned_to'):
                    self.log(f"  ✓ WO is UNASSIGNED (status=OPEN, assigned_to=null)")
                
                # Tech claims it
                success, claim_resp = self.test("PUT /work-orders/{id} action=claim", "PUT",
                                               f"work-orders/{wo_id}", 200,
                                               token=self.tokens['tech'],
                                               data={"action": "claim"})
                if success:
                    self.log(f"  ✓ Tech claimed WO successfully")
                    if claim_resp.get('assigned_to') == 'tech':
                        self.log(f"  ✓ assigned_to updated to 'tech'")
                    if claim_resp.get('status') == 'ASSIGNED':
                        self.log(f"  ✓ status updated to ASSIGNED")
        
        # Test Analytics closure rate KPI
        self.log("\n4. ANALYTICS - CLOSURE RATE KPI")
        success, resp = self.test("GET /analytics/kpis (plant)", "GET", "analytics/kpis", 200,
                                 token=self.tokens['admin'],
                                 params={"level": "plant"})
        if success:
            if 'closure_rate' in resp:
                self.log(f"  ✓ closure_rate field present: {resp.get('closure_rate')}%")
            if 'breakdowns_closed' in resp:
                self.log(f"  ✓ breakdowns_closed field present: {resp.get('breakdowns_closed')}")
            if 'breakdowns_reported' in resp:
                self.log(f"  ✓ breakdowns_reported field present: {resp.get('breakdowns_reported')}")
            if 'pareto' in resp:
                self.log(f"  ✓ pareto field present: {len(resp.get('pareto', []))} failure modes")
        
        # Test AWS settings with predictive_trigger_pct
        self.log("\n5. AWS - PREDICTIVE TRIGGER SETTING")
        success, resp = self.test("GET /reliability/settings", "GET", "reliability/settings", 200,
                                 token=self.tokens['admin'])
        if success:
            if 'predictive_trigger_pct' in resp:
                self.log(f"  ✓ predictive_trigger_pct field present: {resp.get('predictive_trigger_pct')}%")
            
            # Test updating it
            success, update_resp = self.test("PUT /reliability/settings", "PUT", "reliability/settings", 200,
                                            token=self.tokens['admin'],
                                            data={"predictive_trigger_pct": 85})
            if success:
                self.log(f"  ✓ predictive_trigger_pct updated successfully")
        
        return True

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 80)
        self.log("TEST SUMMARY")
        self.log("=" * 80)
        self.log(f"Total Tests: {self.tests_run}")
        self.log(f"Passed: {self.tests_passed} ✅")
        self.log(f"Failed: {len(self.failures)} ❌")
        
        if self.failures:
            self.log("\nFailed Tests:")
            for failure in self.failures:
                self.log(f"  - {failure}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%")
        self.log("=" * 80)
        
        return 0 if len(self.failures) == 0 else 1

def main():
    tester = NewFeaturesTester()
    tester.run_tests()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
