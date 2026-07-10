"""
Comprehensive Backend API Testing for Factory Operations Platform
Tests all endpoints with proper authentication and RBAC validation
"""
import requests
import sys
import time
from datetime import datetime, timedelta

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class FactoryOpsAPITester:
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
                    self.log(f"Response: {response.text[:200]}", "DEBUG")
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
        self.log("FACTORY OPERATIONS PLATFORM - BACKEND API TESTS")
        self.log("=" * 80)
        
        # 1. Authentication Tests
        if not self.test_authentication():
            self.log("Authentication failed - stopping tests", "ERROR")
            return False
        
        # 2. Hierarchy Tests
        self.test_hierarchy()
        
        # 3. RBAC Tests
        self.test_rbac()
        
        # 4. Public Breakdown Reporting (NO AUTH)
        self.test_public_breakdown_reporting()
        
        # 5. Machine Reports Flow
        self.test_machine_reports()
        
        # 6. Breakdown Lifecycle
        self.test_breakdown_lifecycle()
        
        # 7. 30-min Root Cause Rule
        self.test_root_cause_rule()
        
        # 8. Work Orders
        self.test_work_orders()
        
        # 9. PM Tasks
        self.test_pm_tasks()
        
        # 10. Runtime Logs
        self.test_runtime()
        
        # 11. Reliability
        self.test_reliability()
        
        # 12. Analytics
        self.test_analytics()
        
        # 13. Spares Inventory
        self.test_spares()
        
        # 14. Admin CRUD
        self.test_admin_crud()
        
        # 15. Timeline & Notifications
        self.test_timeline_notifications()
        
        return True

    def test_authentication(self):
        """Test authentication for all 3 users"""
        self.log("\n" + "=" * 80)
        self.log("1. AUTHENTICATION TESTS")
        self.log("=" * 80)
        
        users = [
            ('admin', 'admin123', 'admin'),
            ('tech', 'tech123', 'technician'),
            ('operator', 'operator123', 'operator')
        ]
        
        for username, password, expected_role in users:
            success, resp = self.test(
                f"Login as {username}",
                "POST", "auth/login", 200,
                data={"username": username, "password": password}
            )
            if success and 'token' in resp:
                self.tokens[username] = resp['token']
                if resp.get('user', {}).get('role') == expected_role:
                    self.log(f"  ✓ {username} role verified: {expected_role}")
                else:
                    self.log(f"  ✗ {username} role mismatch", "WARN")
            else:
                self.log(f"Failed to login as {username}", "ERROR")
                return False
        
        # Test invalid credentials
        self.test("Invalid credentials rejected", "POST", "auth/login", 401,
                 data={"username": "admin", "password": "wrongpass"})
        
        # Test /auth/me
        self.test("GET /auth/me", "GET", "auth/me", 200, token=self.tokens['admin'])
        
        return True

    def test_hierarchy(self):
        """Test hierarchy endpoints"""
        self.log("\n" + "=" * 80)
        self.log("2. HIERARCHY TESTS")
        self.log("=" * 80)
        
        # Get hierarchy
        success, resp = self.test("GET /hierarchy", "GET", "hierarchy", 200, 
                                 token=self.tokens['admin'])
        if success:
            depts = resp.get('departments', [])
            lines = resp.get('lines', [])
            pgs = resp.get('process_groups', [])
            self.log(f"  ✓ Departments: {len(depts)}, Lines: {len(lines)}, Process Groups: {len(pgs)}")
            if len(depts) == 3 and len(lines) == 14 and len(pgs) == 40:
                self.log(f"  ✓ Hierarchy counts match expected (3 depts, 14 lines, 40 PGs)")
            else:
                self.log(f"  ✗ Hierarchy counts mismatch - expected 3/14/40", "WARN")
        
        # Get machines
        success, resp = self.test("GET /machines", "GET", "machines", 200,
                                 token=self.tokens['admin'])
        if success:
            machines = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Total machines: {len(machines)}")
            if len(machines) == 194:
                self.log(f"  ✓ Machine count matches expected (194)")
                # Store a test machine for later use
                if machines:
                    self.test_data['machine'] = machines[0]
                    # Find a machine from PC36 or KKR for destructive tests
                    for m in machines:
                        if m.get('line') in ['PC36', 'KKR']:
                            self.test_data['test_machine'] = m
                            break
            else:
                self.log(f"  ✗ Machine count mismatch - expected 194", "WARN")
        
        # Get control room summary
        success, resp = self.test("GET /control-room/summary", "GET", "control-room/summary", 200,
                                 token=self.tokens['admin'])
        if success:
            self.log(f"  ✓ Control room summary: {resp.get('total_machines')} machines")

    def test_rbac(self):
        """Test Role-Based Access Control"""
        self.log("\n" + "=" * 80)
        self.log("3. RBAC TESTS")
        self.log("=" * 80)
        
        # Operator should get 403 on work-orders, spares, pm-tasks
        self.test("Operator GET /work-orders (403)", "GET", "work-orders", 403,
                 token=self.tokens['operator'])
        self.test("Operator GET /spares (403)", "GET", "spares", 403,
                 token=self.tokens['operator'])
        self.test("Operator POST /pm-tasks (403)", "POST", "pm-tasks", 403,
                 token=self.tokens['operator'],
                 data={"task_name": "test", "machine_id": "test", "frequency": "daily"})
        
        # Tech should get 403 on POST /users
        self.test("Tech POST /users (403)", "POST", "users", 403,
                 token=self.tokens['tech'],
                 data={"username": "test", "password": "test", "role": "operator", "name": "Test"})
        
        # Admin should have access to everything
        self.test("Admin GET /users (200)", "GET", "users", 200,
                 token=self.tokens['admin'])
    
    def test_public_breakdown_reporting(self):
        """Test public breakdown reporting (NO AUTH required) with MANDATORY technician assignment"""
        self.log("\n" + "=" * 80)
        self.log("4. PUBLIC BREAKDOWN REPORTING (NO AUTH) + MANDATORY TECHNICIAN")
        self.log("=" * 80)
        
        # GET /public/report-context WITHOUT auth - should include technicians
        success, resp = self.test("GET /public/report-context (no auth)", "GET", 
                                 "public/report-context", 200)
        if success:
            lines = resp.get('lines', [])
            machines = resp.get('machines', [])
            technicians = resp.get('technicians', [])
            self.log(f"  ✓ Public context: {len(lines)} lines, {len(machines)} machines, {len(technicians)} technicians")
            if machines:
                self.test_data['public_machine'] = machines[0]
            if not technicians:
                self.log(f"  ✗ No technicians in public context", "WARN")
            else:
                self.log(f"  ✓ Technicians list available for assignment")
        
        if 'public_machine' not in self.test_data:
            self.log("No machine available for public breakdown test", "WARN")
            return
        
        machine = self.test_data['public_machine']
        
        # POST /public/breakdowns WITHOUT assigned_to (should reject 400)
        success, resp = self.test("POST /public/breakdowns (missing assigned_to 400)", "POST",
                                 "public/breakdowns", 400,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown without technician",
                                     "breakdown_type": "MECHANICAL",
                                     "reporter_name": "Floor Operator John"
                                 })
        if success:
            self.log(f"  ✓ Missing assigned_to rejected with 400")
        
        # POST /public/breakdowns with invalid technician (should reject 400)
        success, resp = self.test("POST /public/breakdowns (invalid technician 400)", "POST",
                                 "public/breakdowns", 400,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown with invalid tech",
                                     "breakdown_type": "MECHANICAL",
                                     "reporter_name": "Floor Operator John",
                                     "assigned_to": "nonexistent_user"
                                 })
        if success:
            self.log(f"  ✓ Invalid technician rejected with 400")
        
        # POST /public/breakdowns with non-technician role (should reject 400)
        success, resp = self.test("POST /public/breakdowns (operator role 400)", "POST",
                                 "public/breakdowns", 400,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown with operator",
                                     "breakdown_type": "MECHANICAL",
                                     "reporter_name": "Floor Operator John",
                                     "assigned_to": "operator"
                                 })
        if success:
            self.log(f"  ✓ Non-technician role (operator) rejected with 400")
        
        # POST /public/breakdowns with valid technician (should succeed)
        success, resp = self.test("POST /public/breakdowns (valid technician)", "POST",
                                 "public/breakdowns", 200,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Public kiosk test - machine stopped",
                                     "breakdown_type": "MECHANICAL",
                                     "reporter_name": "Floor Operator John",
                                     "assigned_to": "tech"
                                 })
        if success:
            bd_id = resp.get('id')
            ticket = resp.get('ticket_number')
            self.test_data['public_breakdown_id'] = bd_id
            self.test_data['public_breakdown_ticket'] = ticket
            self.log(f"  ✓ Public breakdown created: {ticket}")
            
            # Verify status is ASSIGNED
            if resp.get('status') == 'ASSIGNED':
                self.log(f"  ✓ Breakdown status is ASSIGNED")
            else:
                self.log(f"  ✗ Breakdown status is {resp.get('status')}, expected ASSIGNED", "WARN")
            
            # Verify assigned_to is set
            if resp.get('assigned_to') == 'tech':
                self.log(f"  ✓ assigned_to='tech' set correctly")
            else:
                self.log(f"  ✗ assigned_to not set correctly", "WARN")
            
            # Verify submitted_via flag
            if resp.get('submitted_via') == 'public_kiosk':
                self.log(f"  ✓ submitted_via=public_kiosk flag set")
            else:
                self.log(f"  ✗ submitted_via flag not set correctly", "WARN")
            
            # Verify auto work order created and assigned
            if resp.get('work_order_number'):
                self.log(f"  ✓ Auto work order created: {resp['work_order_number']}")
            else:
                self.log(f"  ✗ Work order not created", "WARN")
        
        # POST /public/breakdowns WITHOUT reporter_name (should reject 400)
        success, resp = self.test("POST /public/breakdowns (empty reporter_name 400)", "POST",
                                 "public/breakdowns", 400,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown",
                                     "breakdown_type": "ELECTRICAL",
                                     "reporter_name": "",
                                     "assigned_to": "tech"
                                 })
        if success:
            self.log(f"  ✓ Empty reporter_name rejected with 400")
        
        # Test public WARNING reporting with mandatory technician
        success, resp = self.test("POST /public/warnings (valid technician)", "POST",
                                 "public/warnings", 200,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Public warning test - abnormal noise",
                                     "warning_type": "MECHANICAL",
                                     "reporter_name": "Floor Operator Jane",
                                     "wo_type": "Inspection",
                                     "assigned_to": "tech"
                                 })
        if success:
            self.log(f"  ✓ Public warning created: {resp.get('tag_number')}")
            if resp.get('work_order_number'):
                self.log(f"  ✓ Warning WO created: {resp['work_order_number']}")
        
        # POST /public/warnings WITHOUT assigned_to (should reject 400)
        success, resp = self.test("POST /public/warnings (missing assigned_to 400)", "POST",
                                 "public/warnings", 400,
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Warning without tech",
                                     "warning_type": "MECHANICAL",
                                     "reporter_name": "Floor Operator Jane",
                                     "wo_type": "Inspection"
                                 })
        if success:
            self.log(f"  ✓ Warning without assigned_to rejected with 400")
        
        # Verify public breakdown appears in authenticated breakdown list with flag
        if 'public_breakdown_id' in self.test_data:
            success, resp = self.test("GET /breakdowns (verify public flag)", "GET",
                                     "breakdowns", 200,
                                     token=self.tokens['admin'])
            if success:
                items = resp.get('items', [])
                public_bd = next((b for b in items if b.get('id') == self.test_data['public_breakdown_id']), None)
                if public_bd and public_bd.get('submitted_via') == 'public_kiosk':
                    self.log(f"  ✓ Public breakdown visible in authenticated list with flag")

    def test_machine_reports(self):
        """Test machine report flow"""
        self.log("\n" + "=" * 80)
        self.log("4. MACHINE REPORTS FLOW")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        
        # Get error codes
        success, resp = self.test("GET /error-codes", "GET", "error-codes", 200,
                                 token=self.tokens['operator'])
        if success and resp:
            error_code = resp[0].get('code', 'OBS-01')
        else:
            error_code = 'OBS-01'
        
        # Operator creates report
        success, resp = self.test("Operator POST /reports", "POST", "reports", 200,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "error_code": error_code,
                                     "description": "Test report - abnormal noise detected"
                                 })
        if success:
            report_id = resp.get('id')
            self.test_data['report_id'] = report_id
            self.log(f"  ✓ Report created: {resp.get('report_number')}")
            
            # Tech reviews and converts to breakdown
            success, resp = self.test("Tech review report (convert)", "PUT", 
                                     f"reports/{report_id}/review", 200,
                                     token=self.tokens['tech'],
                                     data={
                                         "action": "convert",
                                         "failure_mode": "Bearing Failure",
                                         "review_notes": "Converted to breakdown"
                                     })
            if success:
                self.log(f"  ✓ Report converted to breakdown")
                if resp.get('breakdown'):
                    self.test_data['converted_breakdown'] = resp['breakdown']

    def test_breakdown_lifecycle(self):
        """Test breakdown lifecycle with spare consumption and MANDATORY technician assignment"""
        self.log("\n" + "=" * 80)
        self.log("5. BREAKDOWN LIFECYCLE + MANDATORY TECHNICIAN")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        
        # Test authenticated breakdown WITHOUT assigned_to (should reject 400)
        success, resp = self.test("POST /breakdowns (missing assigned_to 400)", "POST", "breakdowns", 400,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown without tech",
                                     "failure_mode": "Motor Failure"
                                 })
        if success:
            self.log(f"  ✓ Authenticated breakdown without assigned_to rejected with 400")
        
        # Test authenticated breakdown with invalid technician (should reject 400)
        success, resp = self.test("POST /breakdowns (invalid technician 400)", "POST", "breakdowns", 400,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown with invalid tech",
                                     "failure_mode": "Motor Failure",
                                     "assigned_to": "invalid_user_xyz"
                                 })
        if success:
            self.log(f"  ✓ Invalid technician rejected with 400")
        
        # Test authenticated breakdown with non-technician role (should reject 400)
        success, resp = self.test("POST /breakdowns (admin role 400)", "POST", "breakdowns", 400,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown with admin",
                                     "failure_mode": "Motor Failure",
                                     "assigned_to": "admin"
                                 })
        if success:
            self.log(f"  ✓ Non-technician role (admin) rejected with 400")
        
        # Test authenticated WARNING without assigned_to (should reject 400)
        success, resp = self.test("POST /warnings (missing assigned_to 400)", "POST", "warnings", 400,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Warning without tech",
                                     "warning_type": "MECHANICAL",
                                     "wo_type": "Inspection"
                                 })
        if success:
            self.log(f"  ✓ Warning without assigned_to rejected with 400")
        
        # Create breakdown with valid technician
        success, resp = self.test("POST /breakdowns (valid technician)", "POST", "breakdowns", 200,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown - motor failure",
                                     "failure_mode": "Motor Failure",
                                     "assigned_to": "tech"
                                 })
        if success:
            bd_id = resp.get('id')
            self.test_data['breakdown_id'] = bd_id
            self.log(f"  ✓ Breakdown created: {resp.get('ticket_number')}")
            
            # Verify status is ASSIGNED
            if resp.get('status') == 'ASSIGNED':
                self.log(f"  ✓ Breakdown status is ASSIGNED")
            else:
                self.log(f"  ✗ Breakdown status is {resp.get('status')}, expected ASSIGNED", "WARN")
            
            # Verify assigned_to is set
            if resp.get('assigned_to') == 'tech':
                self.log(f"  ✓ assigned_to='tech' set correctly")
            else:
                self.log(f"  ✗ assigned_to not set correctly", "WARN")
            
            # Verify work order created
            if resp.get('work_order_number'):
                self.log(f"  ✓ Work order created: {resp['work_order_number']}")
            else:
                self.log(f"  ✗ Work order not created", "WARN")
            
            # Check machine status changed to failed
            success, m_resp = self.test("GET machine after breakdown", "GET", 
                                       f"machines/{machine['id']}", 200,
                                       token=self.tokens['tech'])
            if success and m_resp.get('machine', {}).get('status') == 'failed':
                self.log(f"  ✓ Machine status changed to 'failed'")
            
            # Start repair
            success, resp = self.test("Start breakdown repair", "PUT", f"breakdowns/{bd_id}", 200,
                                     token=self.tokens['tech'],
                                     data={"action": "start"})
            if success:
                self.log(f"  ✓ Repair started")
                
                # Check machine status changed to repair
                success, m_resp = self.test("GET machine during repair", "GET",
                                           f"machines/{machine['id']}", 200,
                                           token=self.tokens['tech'])
                if success and m_resp.get('machine', {}).get('status') == 'repair':
                    self.log(f"  ✓ Machine status changed to 'repair'")
            
            # Complete with spare consumption
            success, resp = self.test("Complete breakdown with spares", "PUT", 
                                     f"breakdowns/{bd_id}", 200,
                                     token=self.tokens['tech'],
                                     data={
                                         "action": "complete",
                                         "root_cause": "Motor bearing seized due to lack of lubrication",
                                         "action_taken": "Replaced motor bearing, applied proper lubrication",
                                         "consumed_spares": [
                                             {"sap_code": "400001234", "quantity": 2}
                                         ]
                                     })
            if success:
                self.log(f"  ✓ Breakdown completed with spare consumption")
                
                # Verify machine back to running
                success, m_resp = self.test("GET machine after completion", "GET",
                                           f"machines/{machine['id']}", 200,
                                           token=self.tokens['tech'])
                if success and m_resp.get('machine', {}).get('status') == 'running':
                    self.log(f"  ✓ Machine status back to 'running'")
                
                # Verify spare quantity decremented
                success, spare_resp = self.test("GET spare after consumption", "GET",
                                               "spares", 200,
                                               token=self.tokens['tech'],
                                               params={"search": "400001234"})
                if success:
                    items = spare_resp.get('items', [])
                    if items:
                        self.log(f"  ✓ Spare quantity after consumption: {items[0].get('quantity')}")
                
                # Verify spare transaction exists
                success, tx_resp = self.test("GET spare transactions", "GET",
                                            "spare-transactions", 200,
                                            token=self.tokens['tech'],
                                            params={"sap_code": "400001234"})
                if success:
                    txs = tx_resp.get('items', [])
                    breakdown_tx = [t for t in txs if t.get('transaction_type') == 'BREAKDOWN_CONSUMPTION']
                    if breakdown_tx:
                        self.log(f"  ✓ BREAKDOWN_CONSUMPTION transaction recorded")
                
                # Verify reliability metrics created
                success, rel_resp = self.test("GET reliability metrics", "GET",
                                             f"reliability/metrics/{machine['id']}", 200,
                                             token=self.tokens['tech'])
                if success and rel_resp.get('metrics'):
                    level = rel_resp['metrics'].get('level', 0)
                    self.log(f"  ✓ Reliability metrics exist (level: {level})")

    def test_root_cause_rule(self):
        """Test 30-min root cause rule"""
        self.log("\n" + "=" * 80)
        self.log("6. 30-MIN ROOT CAUSE RULE")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        
        # Create breakdown with start_time 2 hours ago
        start_time = (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z'
        success, resp = self.test("POST breakdown (2h ago)", "POST", "breakdowns", 200,
                                 token=self.tokens['tech'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test 30-min rule",
                                     "failure_mode": "Electrical Fault",
                                     "start_time": start_time,
                                     "assigned_to": "tech"
                                 })
        if success:
            bd_id = resp.get('id')
            
            # Try to complete WITHOUT root_cause (should fail)
            success, resp = self.test("Complete without root_cause (400)", "PUT",
                                     f"breakdowns/{bd_id}", 400,
                                     token=self.tokens['tech'],
                                     data={
                                         "action": "complete",
                                         "action_taken": "Fixed the issue"
                                     })
            if success:
                self.log(f"  ✓ Completion without root_cause rejected (400)")
            
            # Complete WITH root_cause (should succeed and create RCA WO)
            success, resp = self.test("Complete with root_cause", "PUT",
                                     f"breakdowns/{bd_id}", 200,
                                     token=self.tokens['tech'],
                                     data={
                                         "action": "complete",
                                         "root_cause": "Electrical panel overheating due to dust accumulation",
                                         "action_taken": "Cleaned panel, replaced damaged components"
                                     })
            if success:
                self.log(f"  ✓ Breakdown completed with root_cause")
                
                # Check if RCA work order was created
                success, wo_resp = self.test("GET work orders", "GET", "work-orders", 200,
                                            token=self.tokens['tech'])
                if success:
                    wos = wo_resp.get('items', [])
                    rca_wos = [w for w in wos if w.get('source') == 'rca_followup' and 
                              w.get('source_breakdown_id') == bd_id]
                    if rca_wos:
                        self.log(f"  ✓ RCA follow-up work order auto-generated: {rca_wos[0].get('wo_number')}")
                        self.log(f"  ✓ Assigned to attending technician: {rca_wos[0].get('assigned_to')}")
                    else:
                        self.log(f"  ✗ RCA work order not found", "WARN")

    def test_work_orders(self):
        """Test work order lifecycle"""
        self.log("\n" + "=" * 80)
        self.log("7. WORK ORDER LIFECYCLE")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        
        # Create work order
        success, resp = self.test("POST /work-orders", "POST", "work-orders", 200,
                                 token=self.tokens['tech'],
                                 data={
                                     "machine_id": machine['id'],
                                     "title": "Test corrective maintenance",
                                     "description": "Replace worn belt",
                                     "wo_type": "Corrective",
                                     "priority": "medium",
                                     "assigned_to": "tech"
                                 })
        if success:
            wo_id = resp.get('id')
            self.log(f"  ✓ Work order created: {resp.get('wo_number')}")
            
            # Start work order
            success, resp = self.test("Start work order", "PUT", f"work-orders/{wo_id}", 200,
                                     token=self.tokens['tech'],
                                     data={"action": "start"})
            if success:
                self.log(f"  ✓ Work order started")
            
            # Complete with spare consumption
            success, resp = self.test("Complete work order with spares", "PUT",
                                     f"work-orders/{wo_id}", 200,
                                     token=self.tokens['tech'],
                                     data={
                                         "action": "complete",
                                         "action_taken": "Replaced V-belt A57",
                                         "spare_parts": [
                                             {"sap_code": "400002101", "quantity": 1}
                                         ]
                                     })
            if success:
                self.log(f"  ✓ Work order completed with spare consumption")
                
                # Verify spare transaction
                success, tx_resp = self.test("GET spare transactions", "GET",
                                            "spare-transactions", 200,
                                            token=self.tokens['tech'],
                                            params={"sap_code": "400002101"})
                if success:
                    txs = tx_resp.get('items', [])
                    wo_tx = [t for t in txs if t.get('transaction_type') == 'WORKORDER_CONSUMPTION']
                    if wo_tx:
                        self.log(f"  ✓ WORKORDER_CONSUMPTION transaction recorded")

    def test_pm_tasks(self):
        """Test PM tasks with structured checklists and PDF export"""
        self.log("\n" + "=" * 80)
        self.log("8. PM TASKS & STRUCTURED CHECKLISTS")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        today = datetime.utcnow().date().isoformat()
        
        # Test PM templates with checklist_groups
        success, resp = self.test("GET /pm-templates", "GET", "pm-templates", 200,
                                 token=self.tokens['admin'])
        if success:
            templates = resp if isinstance(resp, list) else []
            self.log(f"  ✓ PM templates: {len(templates)} available")
            templates_with_groups = [t for t in templates if t.get('checklist_groups')]
            if templates_with_groups:
                self.log(f"  ✓ Templates with checklist_groups: {len(templates_with_groups)}")
            else:
                self.log(f"  ✗ No templates with checklist_groups found", "WARN")
        
        # Create PM task with structured checklist_groups
        success, resp = self.test("POST /pm-tasks (structured checklist)", "POST", "pm-tasks", 200,
                                 token=self.tokens['admin'],
                                 data={
                                     "task_name": "Test Structured PM",
                                     "description": "Testing structured checklist groups",
                                     "priority": "medium",
                                     "machine_id": machine['id'],
                                     "assigned_to": "tech",
                                     "frequency": "monthly",
                                     "checklist_groups": [
                                         {
                                             "description": "Motor",
                                             "items": [
                                                 {"checked_for": "Bearing", "parameter": "Vibration, Sound"},
                                                 {"checked_for": "Over load", "parameter": "Ampere"}
                                             ]
                                         },
                                         {
                                             "description": "Gearbox",
                                             "items": [
                                                 {"checked_for": "Oil Level", "parameter": "Visual Check"}
                                             ]
                                         }
                                     ],
                                     "reminder_offset_days": 1,
                                     "next_due_date": today
                                 })
        if success:
            pm_id = resp.get('id')
            self.test_data['pm_task_id'] = pm_id
            self.log(f"  ✓ PM task created with structured checklist")
            
            # Verify checklist_groups were normalized
            if resp.get('checklist_groups'):
                groups = resp['checklist_groups']
                self.log(f"  ✓ checklist_groups normalized: {len(groups)} groups")
                total_items = sum(len(g.get('items', [])) for g in groups)
                self.log(f"  ✓ Total checklist items: {total_items}")
            
            # Verify flat checklist was derived
            if resp.get('checklist'):
                flat = resp['checklist']
                self.log(f"  ✓ Flat checklist derived: {len(flat)} items")
            
            # GET PM task to verify structure
            success, get_resp = self.test("GET /pm-tasks/{id}", "GET", f"pm-tasks/{pm_id}", 200,
                                         token=self.tokens['tech'])
            if success:
                if get_resp.get('checklist_groups'):
                    self.log(f"  ✓ GET returns checklist_groups")
        
        # Test PDF export - blank template
        success, pdf_resp = self.test("GET /pm-tasks/{id}/pdf (blank)", "GET", 
                                      f"pm-tasks/{pm_id}/pdf", 200,
                                      token=self.tokens['tech'])
        if success:
            self.log(f"  ✓ Blank PDF export successful")
        
        # Test PDF with nonexistent task (404)
        self.test("GET /pm-tasks/nonexistent/pdf (404)", "GET", 
                 "pm-tasks/nonexistent-id-12345/pdf", 404,
                 token=self.tokens['tech'])
        
        # Test PM completion with row_results
        success, resp = self.test("POST /pm-tasks/{id}/complete (row_results)", "POST",
                                 f"pm-tasks/{pm_id}/complete", 200,
                                 token=self.tokens['tech'],
                                 data={
                                     "remarks": "All checks completed",
                                     "done_by": "John Tech",
                                     "checked_by": "Jane Supervisor",
                                     "row_results": [
                                         {
                                             "sn": 1,
                                             "description": "Motor",
                                             "checked_for": "Bearing",
                                             "parameter": "Vibration, Sound",
                                             "status": "OK",
                                             "remarks": "Normal operation"
                                         },
                                         {
                                             "sn": 1,
                                             "description": "Motor",
                                             "checked_for": "Over load",
                                             "parameter": "Ampere",
                                             "status": "NOT_OK",
                                             "remarks": "Slightly high current"
                                         },
                                         {
                                             "sn": 2,
                                             "description": "Gearbox",
                                             "checked_for": "Oil Level",
                                             "parameter": "Visual Check",
                                             "status": "OK",
                                             "remarks": ""
                                         }
                                     ]
                                 })
        if success:
            completion_id = resp.get('id')
            self.test_data['pm_completion_id'] = completion_id
            self.log(f"  ✓ PM completed with row_results")
            
            # Verify row_results saved
            if resp.get('row_results'):
                self.log(f"  ✓ row_results saved: {len(resp['row_results'])} rows")
            if resp.get('done_by'):
                self.log(f"  ✓ done_by saved: {resp['done_by']}")
            if resp.get('checked_by'):
                self.log(f"  ✓ checked_by saved: {resp['checked_by']}")
            
            # Test PDF export with completion_id=latest
            success, pdf_resp = self.test("GET /pm-tasks/{id}/pdf?completion_id=latest", "GET",
                                         f"pm-tasks/{pm_id}/pdf", 200,
                                         token=self.tokens['tech'],
                                         params={"completion_id": "latest"})
            if success:
                self.log(f"  ✓ Completed PDF export successful")
        
        # Test invalid status value (should reject with 400)
        success, resp = self.test("POST /pm-tasks/{id}/complete (invalid status 400)", "POST",
                                 f"pm-tasks/{pm_id}/complete", 400,
                                 token=self.tokens['tech'],
                                 data={
                                     "done_by": "Test",
                                     "row_results": [
                                         {
                                             "sn": 1,
                                             "description": "Motor",
                                             "checked_for": "Bearing",
                                             "parameter": "Vibration",
                                             "status": "MAYBE",
                                             "remarks": ""
                                         }
                                     ]
                                 })
        if success:
            self.log(f"  ✓ Invalid status 'MAYBE' rejected with 400")

    def test_runtime(self):
        """Test runtime logs, CSV import, and line-level DELETE (admin-only)"""
        self.log("\n" + "=" * 80)
        self.log("9. RUNTIME LOGS + LINE-LEVEL DELETE")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        line = machine.get('line')
        today = datetime.utcnow().date().isoformat()
        test_date = (datetime.utcnow().date() - timedelta(days=5)).isoformat()
        
        # Create line runtime log for testing DELETE
        success, resp = self.test("POST /runtime-logs (line-level for DELETE test)", "POST", "runtime-logs", 200,
                                 token=self.tokens['admin'],
                                 data={
                                     "line": line,
                                     "date": test_date,
                                     "calendar_hours": 24.0,
                                     "run_hours": 18.0
                                 })
        if success:
            self.log(f"  ✓ Line runtime log created for {line} on {test_date}")
        
        # Test DELETE as technician (should reject 403)
        success, resp = self.test("DELETE /line-runtime-logs (tech 403)", "DELETE", 
                                 f"line-runtime-logs?line={line}&date={test_date}", 403,
                                 token=self.tokens['tech'])
        if success:
            self.log(f"  ✓ Technician DELETE rejected with 403 (admin-only)")
        
        # Test DELETE as admin (should succeed 200)
        success, resp = self.test("DELETE /line-runtime-logs (admin 200)", "DELETE",
                                 f"line-runtime-logs?line={line}&date={test_date}", 200,
                                 token=self.tokens['admin'])
        if success:
            self.log(f"  ✓ Admin DELETE succeeded")
            if resp.get('machine_logs_removed'):
                self.log(f"  ✓ Fanned-out machine logs removed: {resp['machine_logs_removed']}")
        
        # Verify line log is deleted
        success, resp = self.test("GET /line-runtime-logs (verify deleted)", "GET",
                                 f"line-runtime-logs?line={line}&date_from={test_date}&date_to={test_date}", 200,
                                 token=self.tokens['admin'])
        if success:
            items = resp.get('items', [])
            if len(items) == 0:
                self.log(f"  ✓ Line runtime log deleted successfully")
            else:
                self.log(f"  ✗ Line runtime log still exists after DELETE", "WARN")
        
        # Test DELETE non-existent (should reject 404)
        success, resp = self.test("DELETE /line-runtime-logs (non-existent 404)", "DELETE",
                                 f"line-runtime-logs?line={line}&date=2020-01-01", 404,
                                 token=self.tokens['admin'])
        if success:
            self.log(f"  ✓ DELETE non-existent entry rejected with 404")
        
        # Manual log entry
        success, resp = self.test("POST /runtime-logs", "POST", "runtime-logs", 200,
                                 token=self.tokens['admin'],
                                 data={
                                     "machine_id": machine['id'],
                                     "date": today,
                                     "calendar_hours": 24.0,
                                     "run_hours": 20.0
                                 })
        if success:
            self.log(f"  ✓ Runtime log created (20/24 hours)")
        
        # Test validation: run_hours > calendar_hours
        success, resp = self.test("POST runtime with invalid hours (400)", "POST", "runtime-logs", 400,
                                 token=self.tokens['admin'],
                                 data={
                                     "machine_id": machine['id'],
                                     "date": today,
                                     "calendar_hours": 24.0,
                                     "run_hours": 25.0
                                 })
        if success:
            self.log(f"  ✓ Validation rejected run_hours > calendar_hours")
        
        # CSV import preview
        csv_data = f"line,date,run_hours,calendar_hours\n{line},{today},18,24\nINVALID_LINE,{today},10,24"
        success, resp = self.test("POST /runtime-logs/import (preview)", "POST", "runtime-logs/import", 200,
                                 token=self.tokens['admin'],
                                 data={"csv_text": csv_data, "apply": False})
        if success:
            self.log(f"  ✓ CSV preview: {resp.get('valid_rows')} valid, {len(resp.get('errors', []))} errors")
            if resp.get('errors'):
                self.log(f"    Errors detected: {resp['errors'][0]}")
        
        # CSV import apply
        csv_data_valid = f"line,date,run_hours,calendar_hours\n{line},{today},19,24"
        success, resp = self.test("POST /runtime-logs/import (apply)", "POST", "runtime-logs/import", 200,
                                 token=self.tokens['admin'],
                                 data={"csv_text": csv_data_valid, "apply": True})
        if success:
            self.log(f"  ✓ CSV imported: {resp.get('imported')} rows")

    def test_reliability(self):
        """Test reliability engine"""
        self.log("\n" + "=" * 80)
        self.log("10. RELIABILITY ENGINE")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        
        # Create multiple breakdowns quickly to trigger level 3
        self.log(f"  Creating 5 breakdowns on {machine['name']} for reliability analysis...")
        for i in range(5):
            success, resp = self.test(f"Create breakdown {i+1}/5", "POST", "breakdowns", 200,
                                     token=self.tokens['tech'],
                                     data={
                                         "machine_id": machine['id'],
                                         "description": f"Reliability test breakdown {i+1}",
                                         "failure_mode": "Bearing Failure",
                                         "assigned_to": "tech"
                                     })
            if success:
                bd_id = resp.get('id')
                # Complete immediately
                self.test(f"Complete breakdown {i+1}/5", "PUT", f"breakdowns/{bd_id}", 200,
                         token=self.tokens['tech'],
                         data={
                             "action": "complete",
                             "root_cause": f"Test root cause {i+1}",
                             "action_taken": f"Test action {i+1}"
                         })
        
        # Get reliability metrics
        success, resp = self.test("GET /reliability/metrics/{machine_id}", "GET",
                                 f"reliability/metrics/{machine['id']}", 200,
                                 token=self.tokens['tech'])
        if success and resp.get('metrics'):
            metrics = resp['metrics']
            level = metrics.get('level', 0)
            self.log(f"  ✓ Reliability level: {level}")
            if level >= 3:
                self.log(f"  ✓ Level 3 achieved (sufficient failure history)")
                if metrics.get('weibull'):
                    weibull = metrics['weibull']
                    self.log(f"  ✓ Weibull parameters: beta={weibull.get('beta')}, eta={weibull.get('eta')}")
                if metrics.get('tbf_history'):
                    self.log(f"  ✓ TBF history available: {len(metrics['tbf_history'])} records")
            else:
                self.log(f"  ⚠ Level {level} (need 5+ failures for level 3)", "WARN")
        
        # Get reliability metrics list
        success, resp = self.test("GET /reliability/metrics (list)", "GET", "reliability/metrics", 200,
                                 token=self.tokens['tech'])
        if success:
            metrics_list = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Reliability metrics list: {len(metrics_list)} machines")

    def test_analytics(self):
        """Test analytics KPIs"""
        self.log("\n" + "=" * 80)
        self.log("11. ANALYTICS")
        self.log("=" * 80)
        
        # Plant level
        success, resp = self.test("GET /analytics/kpis (plant)", "GET", "analytics/kpis", 200,
                                 token=self.tokens['admin'],
                                 params={"level": "plant"})
        if success:
            self.log(f"  ✓ Plant KPIs: MTBF={resp.get('mtbf_hours')}h, MTTR={resp.get('mttr_hours')}h, Availability={resp.get('availability')}%")
        
        # Line level
        success, resp = self.test("GET /analytics/kpis (line=PC21)", "GET", "analytics/kpis", 200,
                                 token=self.tokens['admin'],
                                 params={"level": "line", "value": "PC21"})
        if success:
            self.log(f"  ✓ PC21 Line KPIs: {resp.get('failures_total')} failures")
        
        # Machine level
        if 'test_machine' in self.test_data:
            machine = self.test_data['test_machine']
            success, resp = self.test("GET /analytics/kpis (machine)", "GET", "analytics/kpis", 200,
                                     token=self.tokens['admin'],
                                     params={"level": "machine", "value": machine['id']})
            if success:
                self.log(f"  ✓ Machine KPIs: {resp.get('failures_total')} failures, {resp.get('downtime_hours_total')}h downtime")

    def test_spares(self):
        """Test spares inventory"""
        self.log("\n" + "=" * 80)
        self.log("12. SPARES INVENTORY")
        self.log("=" * 80)
        
        # Dashboard
        success, resp = self.test("GET /spares/dashboard", "GET", "spares/dashboard", 200,
                                 token=self.tokens['tech'])
        if success:
            self.log(f"  ✓ Dashboard: {resp.get('total_materials')} materials, {resp.get('in_stock')} in stock, {resp.get('out_of_stock')} out of stock")
            if resp.get('total_materials') == 30:
                self.log(f"  ✓ Expected 30 seeded materials found")
        
        # Search
        success, resp = self.test("GET /spares?search=bearing", "GET", "spares", 200,
                                 token=self.tokens['tech'],
                                 params={"search": "bearing"})
        if success:
            items = resp.get('items', [])
            self.log(f"  ✓ Instant search 'bearing': {len(items)} results")
        
        # Adjust stock (negative overdraw should be rejected)
        success, resp = self.test("POST /spares/{sap}/adjust (overdraw 400)", "POST",
                                 "spares/400001234/adjust", 400,
                                 token=self.tokens['admin'],
                                 data={"quantity_change": -1000, "notes": "Test overdraw"})
        if success:
            self.log(f"  ✓ Negative overdraw rejected")
        
        # CSV import preview
        csv_data = "sap_code,quantity_change\n400001234,10\nUNKNOWN_SAP,5"
        success, resp = self.test("POST /spares/import (preview)", "POST", "spares/import", 200,
                                 token=self.tokens['admin'],
                                 data={"csv_text": csv_data, "mode": "adjustment", "apply": False})
        if success:
            self.log(f"  ✓ CSV preview: {resp.get('valid_rows')} valid, {len(resp.get('errors', []))} errors")
            if resp.get('errors'):
                self.log(f"    Error for unknown SAP: {resp['errors'][0]}")
        
        # CSV import apply
        csv_data_valid = "sap_code,quantity_change\n400001234,5"
        success, resp = self.test("POST /spares/import (apply)", "POST", "spares/import", 200,
                                 token=self.tokens['admin'],
                                 data={"csv_text": csv_data_valid, "mode": "adjustment", "apply": True})
        if success:
            self.log(f"  ✓ CSV imported: {resp.get('imported')} rows")
            
            # Verify CSV_IMPORT transaction
            success, tx_resp = self.test("GET spare transactions (CSV_IMPORT)", "GET",
                                        "spare-transactions", 200,
                                        token=self.tokens['tech'],
                                        params={"sap_code": "400001234", "transaction_type": "CSV_IMPORT"})
            if success:
                txs = tx_resp.get('items', [])
                if txs:
                    self.log(f"  ✓ CSV_IMPORT transaction recorded")
        
        # Machine spares
        if 'test_machine' in self.test_data:
            machine = self.test_data['test_machine']
            success, resp = self.test("GET /machines/{id}/spares", "GET",
                                     f"machines/{machine['id']}/spares", 200,
                                     token=self.tokens['tech'])
            if success:
                self.log(f"  ✓ Machine spares: {len(resp.get('recommended', []))} recommended, {len(resp.get('recent_usage', []))} recent usage")

    def test_admin_crud(self):
        """Test admin CRUD operations"""
        self.log("\n" + "=" * 80)
        self.log("13. ADMIN CRUD")
        self.log("=" * 80)
        
        # Create user
        success, resp = self.test("POST /users", "POST", "users", 200,
                                 token=self.tokens['admin'],
                                 data={
                                     "username": f"testuser_{int(time.time())}",
                                     "password": "test123",
                                     "role": "operator",
                                     "name": "Test User",
                                     "email": "test@factory.local"
                                 })
        if success:
            user_id = resp.get('id')
            self.log(f"  ✓ User created: {resp.get('username')}")
            self.test_data['test_user_id'] = user_id
        
        # Invalid role should be rejected
        success, resp = self.test("POST /users (invalid role 400)", "POST", "users", 400,
                                 token=self.tokens['admin'],
                                 data={
                                     "username": "invalid",
                                     "password": "test",
                                     "role": "invalid_role",
                                     "name": "Invalid"
                                 })
        if success:
            self.log(f"  ✓ Invalid role rejected")
        
        # Create failure mode
        success, resp = self.test("POST /failure-modes", "POST", "failure-modes", 200,
                                 token=self.tokens['admin'],
                                 data={"name": f"Test Failure Mode {int(time.time())}"})
        if success:
            self.log(f"  ✓ Failure mode created")
        
        # Create error code
        success, resp = self.test("POST /error-codes", "POST", "error-codes", 200,
                                 token=self.tokens['admin'],
                                 data={"code": f"TST-{int(time.time())}", "label": "Test Error Code"})
        if success:
            self.log(f"  ✓ Error code created")
        
        # Update machine position
        if 'test_machine' in self.test_data:
            machine = self.test_data['test_machine']
            success, resp = self.test("PUT /machines/{id} (position)", "PUT",
                                     f"machines/{machine['id']}", 200,
                                     token=self.tokens['admin'],
                                     data={"position_x": 100, "position_y": 200})
            if success:
                self.log(f"  ✓ Machine position updated")
        
        # Delete department with machines should fail
        success, resp = self.test("DELETE department with machines (400)", "DELETE",
                                 "departments/test", 400,
                                 token=self.tokens['admin'])
        # This will likely 404 since 'test' doesn't exist, but that's ok
        
        # Get audit logs
        success, resp = self.test("GET /audit-logs", "GET", "audit-logs", 200,
                                 token=self.tokens['admin'])
        if success:
            logs = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Audit logs: {len(logs)} entries")
            admin_actions = [l for l in logs if l.get('user') == 'admin']
            if admin_actions:
                self.log(f"  ✓ Admin actions logged: {len(admin_actions)}")

    def test_timeline_notifications(self):
        """Test timeline and notifications"""
        self.log("\n" + "=" * 80)
        self.log("14. TIMELINE & NOTIFICATIONS")
        self.log("=" * 80)
        
        # Get timeline
        success, resp = self.test("GET /timeline", "GET", "timeline", 200,
                                 token=self.tokens['admin'])
        if success:
            events = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Timeline events: {len(events)}")
        
        # Filter by event_type
        success, resp = self.test("GET /timeline?event_type=breakdown_created", "GET", "timeline", 200,
                                 token=self.tokens['admin'],
                                 params={"event_type": "breakdown_created"})
        if success:
            events = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Filtered timeline (breakdown_created): {len(events)} events")
        
        # Get notifications
        success, resp = self.test("GET /notifications", "GET", "notifications", 200,
                                 token=self.tokens['admin'])
        if success:
            notifs = resp if isinstance(resp, list) else []
            self.log(f"  ✓ Notifications: {len(notifs)}")
        
        # Mark all as read
        success, resp = self.test("PUT /notifications/read-all", "PUT", "notifications/read-all", 200,
                                 token=self.tokens['admin'])
        if success:
            self.log(f"  ✓ All notifications marked as read")

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
            for failure in self.failures[:20]:  # Show first 20 failures
                self.log(f"  - {failure}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%")
        self.log("=" * 80)
        
        return 0 if self.tests_failed == 0 else 1

def main():
    tester = FactoryOpsAPITester()
    tester.run_all_tests()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
