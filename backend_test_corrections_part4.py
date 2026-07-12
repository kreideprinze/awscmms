"""
Backend API Testing for Corrections Part 4
Tests the new assignment/closure governance changes
"""
import requests
import sys
import time
from datetime import datetime, timedelta

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class CorrectionsPart4Tester:
    def __init__(self):
        self.base_url = BASE_URL
        self.tokens = {}
        self.test_data = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
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
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
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
                    self.log(f"Response: {response.text[:300]}", "DEBUG")
                except:
                    pass
                return False, {}

        except Exception as e:
            self.tests_failed += 1
            self.failures.append(f"{name}: {str(e)}")
            self.log(f"❌ FAIL - {name}: {str(e)}", "FAIL")
            return False, {}

    def run_all_tests(self):
        """Run all test suites"""
        self.log("=" * 80)
        self.log("CORRECTIONS PART 4 - BACKEND API TESTS")
        self.log("=" * 80)
        
        # 1. Authentication
        if not self.test_authentication():
            self.log("Authentication failed - stopping tests", "ERROR")
            return False
        
        # 2. Get test machine
        if not self.get_test_machine():
            self.log("No test machine available - stopping tests", "ERROR")
            return False
        
        # 3. Test breakdown assignment/closure governance
        self.test_breakdown_governance()
        
        # 4. Test work order assignment/closure governance
        self.test_work_order_governance()
        
        # 5. Test breakdown-WO sync
        self.test_breakdown_wo_sync()
        
        # 6. Test admin start doesn't self-assign
        self.test_admin_start_no_assign()
        
        # 7. Test reliability metrics (life % ticking)
        self.test_reliability_life_pct()
        
        return True

    def test_authentication(self):
        """Test authentication"""
        self.log("\n" + "=" * 80)
        self.log("1. AUTHENTICATION")
        self.log("=" * 80)
        
        users = [
            ('admin', 'admin123', 'admin'),
            ('tech', 'tech123', 'technician'),
        ]
        
        for username, password, expected_role in users:
            success, resp = self.test(
                f"Login as {username}",
                "POST", "auth/login", 200,
                data={"username": username, "password": password}
            )
            if success and 'token' in resp:
                self.tokens[username] = resp['token']
                self.log(f"  ✓ {username} logged in")
            else:
                self.log(f"Failed to login as {username}", "ERROR")
                return False
        
        return True

    def get_test_machine(self):
        """Get a test machine"""
        self.log("\n" + "=" * 80)
        self.log("2. GET TEST MACHINE")
        self.log("=" * 80)
        
        success, resp = self.test("GET /machines", "GET", "machines", 200,
                                 token=self.tokens['admin'])
        if success:
            machines = resp if isinstance(resp, list) else []
            if machines:
                # Find a machine from PC36 or KKR for testing
                for m in machines:
                    if m.get('line') in ['PC36', 'KKR']:
                        self.test_data['machine'] = m
                        self.log(f"  ✓ Test machine: {m['name']} ({m['code']})")
                        return True
                # Fallback to first machine
                self.test_data['machine'] = machines[0]
                self.log(f"  ✓ Test machine: {machines[0]['name']}")
                return True
        
        return False

    def test_breakdown_governance(self):
        """Test breakdown assignment and closure governance"""
        self.log("\n" + "=" * 80)
        self.log("3. BREAKDOWN ASSIGNMENT & CLOSURE GOVERNANCE")
        self.log("=" * 80)
        
        machine = self.test_data['machine']
        
        # TEST 1: Admin creates unassigned breakdown
        self.log("\n--- TEST 1: Admin creates unassigned breakdown ---")
        success, resp = self.test(
            "POST /breakdowns (admin, no assigned_to)",
            "POST", "breakdowns", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "description": "Test unassigned breakdown",
                "failure_mode": "Test Failure",
                "breakdown_type": "MECHANICAL"
            }
        )
        if success:
            bd_id = resp.get('id')
            self.test_data['unassigned_bd_id'] = bd_id
            self.log(f"  ✓ Breakdown created: {resp.get('ticket_number')}")
            
            # Verify status is OPEN (not ASSIGNED)
            if resp.get('status') == 'OPEN':
                self.log(f"  ✓ Status is OPEN (unassigned)")
            else:
                self.log(f"  ✗ Status is {resp.get('status')}, expected OPEN", "WARN")
            
            # Verify assigned_to is None
            if not resp.get('assigned_to'):
                self.log(f"  ✓ assigned_to is None")
            else:
                self.log(f"  ✗ assigned_to is {resp.get('assigned_to')}, expected None", "WARN")
            
            # TEST 2: Admin tries to complete without assigned_to -> 400
            self.log("\n--- TEST 2: Admin complete without assigned_to -> 400 ---")
            success, resp = self.test(
                "PUT /breakdowns/{id} (admin complete, no assigned_to) -> 400",
                "PUT", f"breakdowns/{bd_id}", 400,
                token=self.tokens['admin'],
                data={
                    "action": "complete",
                    "action_taken": "Fixed the issue"
                }
            )
            if success:
                self.log(f"  ✓ Admin complete without assigned_to rejected with 400")
            
            # TEST 3: Admin completes WITH assigned_to -> CLOSED
            self.log("\n--- TEST 3: Admin complete WITH assigned_to -> CLOSED ---")
            success, resp = self.test(
                "PUT /breakdowns/{id} (admin complete, with assigned_to) -> 200",
                "PUT", f"breakdowns/{bd_id}", 200,
                token=self.tokens['admin'],
                data={
                    "action": "complete",
                    "action_taken": "Fixed the issue",
                    "assigned_to": "tech"
                }
            )
            if success:
                self.log(f"  ✓ Admin complete with assigned_to succeeded")
                
                # Verify via GET
                success, get_resp = self.test(
                    "GET /breakdowns/{id} (verify assigned_to)",
                    "GET", f"breakdowns/{bd_id}", 200,
                    token=self.tokens['admin']
                )
                if success:
                    if get_resp.get('status') == 'CLOSED':
                        self.log(f"  ✓ Status is CLOSED")
                    else:
                        self.log(f"  ✗ Status is {get_resp.get('status')}, expected CLOSED", "WARN")
                    
                    if get_resp.get('assigned_to') == 'tech':
                        self.log(f"  ✓ assigned_to is 'tech'")
                    else:
                        self.log(f"  ✗ assigned_to is {get_resp.get('assigned_to')}, expected 'tech'", "WARN")
        
        # TEST 4: Tech completes unassigned breakdown -> auto-assign
        self.log("\n--- TEST 4: Tech completes unassigned breakdown -> auto-assign ---")
        success, resp = self.test(
            "POST /breakdowns (unassigned)",
            "POST", "breakdowns", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "description": "Test tech auto-assign",
                "failure_mode": "Test Failure",
                "breakdown_type": "ELECTRICAL"
            }
        )
        if success:
            bd_id = resp.get('id')
            
            # Tech completes without assigned_to -> auto-assign
            success, resp = self.test(
                "PUT /breakdowns/{id} (tech complete, no assigned_to) -> auto-assign",
                "PUT", f"breakdowns/{bd_id}", 200,
                token=self.tokens['tech'],
                data={
                    "action": "complete",
                    "action_taken": "Fixed by tech"
                }
            )
            if success:
                self.log(f"  ✓ Tech complete succeeded")
                
                # Verify via GET
                success, get_resp = self.test(
                    "GET /breakdowns/{id} (verify auto-assign)",
                    "GET", f"breakdowns/{bd_id}", 200,
                    token=self.tokens['tech']
                )
                if success:
                    if get_resp.get('assigned_to') == 'tech':
                        self.log(f"  ✓ assigned_to auto-assigned to 'tech'")
                    else:
                        self.log(f"  ✗ assigned_to is {get_resp.get('assigned_to')}, expected 'tech'", "WARN")

    def test_work_order_governance(self):
        """Test work order assignment and closure governance"""
        self.log("\n" + "=" * 80)
        self.log("4. WORK ORDER ASSIGNMENT & CLOSURE GOVERNANCE")
        self.log("=" * 80)
        
        machine = self.test_data['machine']
        
        # TEST 1: Create unassigned WO
        self.log("\n--- TEST 1: Create unassigned WO ---")
        success, resp = self.test(
            "POST /work-orders (unassigned)",
            "POST", "work-orders", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "title": "Test unassigned WO",
                "description": "Test WO",
                "wo_type": "Corrective",
                "priority": "medium"
            }
        )
        if success:
            wo_id = resp.get('id')
            self.test_data['unassigned_wo_id'] = wo_id
            self.log(f"  ✓ WO created: {resp.get('wo_number')}")
            
            # Verify status is OPEN
            if resp.get('status') == 'OPEN':
                self.log(f"  ✓ Status is OPEN")
            else:
                self.log(f"  ✗ Status is {resp.get('status')}, expected OPEN", "WARN")
            
            # TEST 2: Admin assigns via dropdown
            self.log("\n--- TEST 2: Admin assigns WO via dropdown ---")
            success, resp = self.test(
                "PUT /work-orders/{id} (admin assign)",
                "PUT", f"work-orders/{wo_id}", 200,
                token=self.tokens['admin'],
                data={
                    "action": "assign",
                    "assigned_to": "tech"
                }
            )
            if success:
                self.log(f"  ✓ Admin assign succeeded")
                
                # Verify status is ASSIGNED
                if resp.get('status') == 'ASSIGNED':
                    self.log(f"  ✓ Status is ASSIGNED")
                else:
                    self.log(f"  ✗ Status is {resp.get('status')}, expected ASSIGNED", "WARN")
        
        # TEST 3: Tech claims unassigned WO
        self.log("\n--- TEST 3: Tech claims unassigned WO ---")
        success, resp = self.test(
            "POST /work-orders (unassigned for claim)",
            "POST", "work-orders", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "title": "Test claim WO",
                "description": "Test WO",
                "wo_type": "Corrective",
                "priority": "medium"
            }
        )
        if success:
            wo_id = resp.get('id')
            
            # Tech claims
            success, resp = self.test(
                "PUT /work-orders/{id} (tech claim)",
                "PUT", f"work-orders/{wo_id}", 200,
                token=self.tokens['tech'],
                data={"action": "claim"}
            )
            if success:
                self.log(f"  ✓ Tech claim succeeded")
                
                # Verify assigned_to is 'tech'
                if resp.get('assigned_to') == 'tech':
                    self.log(f"  ✓ assigned_to is 'tech'")
                else:
                    self.log(f"  ✗ assigned_to is {resp.get('assigned_to')}, expected 'tech'", "WARN")

    def test_breakdown_wo_sync(self):
        """Test breakdown-WO assignment sync"""
        self.log("\n" + "=" * 80)
        self.log("5. BREAKDOWN-WO ASSIGNMENT SYNC")
        self.log("=" * 80)
        
        machine = self.test_data['machine']
        
        # Create unassigned breakdown (auto-creates linked WO)
        self.log("\n--- TEST: Assign breakdown -> linked WO also assigned ---")
        success, resp = self.test(
            "POST /breakdowns (unassigned)",
            "POST", "breakdowns", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "description": "Test sync",
                "failure_mode": "Test Failure",
                "breakdown_type": "MECHANICAL"
            }
        )
        if success:
            bd_id = resp.get('id')
            wo_id = resp.get('work_order_id')
            self.log(f"  ✓ Breakdown created: {resp.get('ticket_number')}")
            self.log(f"  ✓ Linked WO: {resp.get('work_order_number')}")
            
            # Assign breakdown
            success, resp = self.test(
                "PUT /breakdowns/{id} (assign)",
                "PUT", f"breakdowns/{bd_id}", 200,
                token=self.tokens['admin'],
                data={
                    "action": "assign",
                    "assigned_to": "tech"
                }
            )
            if success:
                self.log(f"  ✓ Breakdown assigned to 'tech'")
                
                # Verify linked WO is also assigned
                if wo_id:
                    success, wo_resp = self.test(
                        "GET /work-orders/{id} (verify sync)",
                        "GET", f"work-orders/{wo_id}", 200,
                        token=self.tokens['admin']
                    )
                    if success:
                        if wo_resp.get('assigned_to') == 'tech':
                            self.log(f"  ✓ Linked WO also assigned to 'tech'")
                        else:
                            self.log(f"  ✗ Linked WO assigned_to is {wo_resp.get('assigned_to')}, expected 'tech'", "WARN")
                        
                        if wo_resp.get('status') == 'ASSIGNED':
                            self.log(f"  ✓ Linked WO status is ASSIGNED")
                        else:
                            self.log(f"  ✗ Linked WO status is {wo_resp.get('status')}, expected ASSIGNED", "WARN")

    def test_admin_start_no_assign(self):
        """Test admin start doesn't self-assign"""
        self.log("\n" + "=" * 80)
        self.log("6. ADMIN START DOESN'T SELF-ASSIGN")
        self.log("=" * 80)
        
        machine = self.test_data['machine']
        
        # TEST 1: Admin starts unassigned breakdown
        self.log("\n--- TEST 1: Admin starts unassigned breakdown ---")
        success, resp = self.test(
            "POST /breakdowns (unassigned)",
            "POST", "breakdowns", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "description": "Test admin start",
                "failure_mode": "Test Failure",
                "breakdown_type": "MECHANICAL"
            }
        )
        if success:
            bd_id = resp.get('id')
            
            # Admin starts
            success, resp = self.test(
                "PUT /breakdowns/{id} (admin start)",
                "PUT", f"breakdowns/{bd_id}", 200,
                token=self.tokens['admin'],
                data={"action": "start"}
            )
            if success:
                self.log(f"  ✓ Admin start succeeded")
                
                # Verify via GET - assigned_to should still be None
                success, get_resp = self.test(
                    "GET /breakdowns/{id} (verify no auto-assign)",
                    "GET", f"breakdowns/{bd_id}", 200,
                    token=self.tokens['admin']
                )
                if success:
                    if not get_resp.get('assigned_to'):
                        self.log(f"  ✓ assigned_to is still None (admin didn't self-assign)")
                    else:
                        self.log(f"  ✗ assigned_to is {get_resp.get('assigned_to')}, expected None", "WARN")
                    
                    if get_resp.get('status') == 'IN_PROGRESS':
                        self.log(f"  ✓ Status is IN_PROGRESS")
                    else:
                        self.log(f"  ✗ Status is {get_resp.get('status')}, expected IN_PROGRESS", "WARN")
        
        # TEST 2: Tech starts unassigned breakdown -> auto-assign
        self.log("\n--- TEST 2: Tech starts unassigned breakdown -> auto-assign ---")
        success, resp = self.test(
            "POST /breakdowns (unassigned)",
            "POST", "breakdowns", 200,
            token=self.tokens['admin'],
            data={
                "machine_id": machine['id'],
                "description": "Test tech start",
                "failure_mode": "Test Failure",
                "breakdown_type": "ELECTRICAL"
            }
        )
        if success:
            bd_id = resp.get('id')
            
            # Tech starts
            success, resp = self.test(
                "PUT /breakdowns/{id} (tech start)",
                "PUT", f"breakdowns/{bd_id}", 200,
                token=self.tokens['tech'],
                data={"action": "start"}
            )
            if success:
                self.log(f"  ✓ Tech start succeeded")
                
                # Verify via GET - assigned_to should be 'tech'
                success, get_resp = self.test(
                    "GET /breakdowns/{id} (verify auto-assign)",
                    "GET", f"breakdowns/{bd_id}", 200,
                    token=self.tokens['tech']
                )
                if success:
                    if get_resp.get('assigned_to') == 'tech':
                        self.log(f"  ✓ assigned_to auto-assigned to 'tech'")
                    else:
                        self.log(f"  ✗ assigned_to is {get_resp.get('assigned_to')}, expected 'tech'", "WARN")

    def test_reliability_life_pct(self):
        """Test reliability metrics have non-null categories with life_pct"""
        self.log("\n" + "=" * 80)
        self.log("7. RELIABILITY METRICS (LIFE % TICKING)")
        self.log("=" * 80)
        
        # Get reliability metrics list
        success, resp = self.test(
            "GET /reliability/metrics",
            "GET", "reliability/metrics", 200,
            token=self.tokens['admin']
        )
        if success:
            metrics_list = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Reliability metrics: {len(metrics_list)} machines")
            
            # Find machines with categories
            machines_with_categories = [m for m in metrics_list if m.get('categories')]
            self.log(f"  ✓ Machines with categories: {len(machines_with_categories)}")
            
            if machines_with_categories:
                # Check first machine with categories
                m = machines_with_categories[0]
                self.log(f"  ✓ Sample machine: {m.get('machine_name')}")
                
                categories = m.get('categories', {})
                for cat_name, cat_data in categories.items():
                    life_pct = cat_data.get('life_pct')
                    hours_since = cat_data.get('hours_since_last_failure')
                    
                    if life_pct is not None and life_pct > 0:
                        self.log(f"  ✓ {cat_name}: life_pct={life_pct}%, hours_since={hours_since}h")
                    else:
                        self.log(f"  ⚠ {cat_name}: life_pct={life_pct} (expected > 0)", "WARN")
            else:
                self.log(f"  ⚠ No machines with categories found (need failures first)", "WARN")

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
            for failure in self.failures[:20]:
                self.log(f"  - {failure}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%")
        self.log("=" * 80)
        
        return 0 if self.tests_failed == 0 else 1

def main():
    tester = CorrectionsPart4Tester()
    tester.run_all_tests()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
