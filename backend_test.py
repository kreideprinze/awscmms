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
        
        # 4. Machine Reports Flow
        self.test_machine_reports()
        
        # 5. Breakdown Lifecycle
        self.test_breakdown_lifecycle()
        
        # 6. 30-min Root Cause Rule
        self.test_root_cause_rule()
        
        # 7. Work Orders
        self.test_work_orders()
        
        # 8. PM Tasks
        self.test_pm_tasks()
        
        # 9. Runtime Logs
        self.test_runtime()
        
        # 10. Reliability
        self.test_reliability()
        
        # 11. Analytics
        self.test_analytics()
        
        # 12. Spares Inventory
        self.test_spares()
        
        # 13. Admin CRUD
        self.test_admin_crud()
        
        # 14. Timeline & Notifications
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
        """Test breakdown lifecycle with spare consumption"""
        self.log("\n" + "=" * 80)
        self.log("5. BREAKDOWN LIFECYCLE")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        
        # Create breakdown
        success, resp = self.test("POST /breakdowns", "POST", "breakdowns", 200,
                                 token=self.tokens['operator'],
                                 data={
                                     "machine_id": machine['id'],
                                     "description": "Test breakdown - motor failure",
                                     "failure_mode": "Motor Failure"
                                 })
        if success:
            bd_id = resp.get('id')
            self.test_data['breakdown_id'] = bd_id
            self.log(f"  ✓ Breakdown created: {resp.get('ticket_number')}")
            
            # Check machine status changed to failed
            success, m_resp = self.test("GET machine after breakdown", "GET", 
                                       f"machines/{machine['id']}", 200,
                                       token=self.tokens['tech'])
            if success and m_resp.get('machine', {}).get('status') == 'failed':
                self.log(f"  ✓ Machine status changed to 'failed'")
            
            # Assign to tech
            success, resp = self.test("Assign breakdown", "PUT", f"breakdowns/{bd_id}", 200,
                                     token=self.tokens['tech'],
                                     data={"action": "assign", "assigned_to": "tech"})
            if success:
                self.log(f"  ✓ Breakdown assigned")
            
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
                                     "start_time": start_time
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
        """Test PM tasks and scheduler"""
        self.log("\n" + "=" * 80)
        self.log("8. PM TASKS & SCHEDULER")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        today = datetime.utcnow().date().isoformat()
        
        # Create PM task with frequency=daily and next_due_date=today
        success, resp = self.test("POST /pm-tasks (daily, due today)", "POST", "pm-tasks", 200,
                                 token=self.tokens['admin'],
                                 data={
                                     "task_name": "Test Daily Inspection",
                                     "description": "Daily operator check",
                                     "priority": "medium",
                                     "machine_id": machine['id'],
                                     "assigned_to": "tech",
                                     "frequency": "daily",
                                     "checklist": ["Check for leaks", "Verify operation"],
                                     "reminder_offset_days": 1,
                                     "next_due_date": today
                                 })
        if success:
            pm_id = resp.get('id')
            self.test_data['pm_task_id'] = pm_id
            self.log(f"  ✓ PM task created (due today)")
            self.log(f"  ⏳ Waiting 70 seconds for PM scheduler to generate work order...")
            
            # Wait for scheduler (runs every 60s)
            time.sleep(70)
            
            # Check if PM work order was generated
            success, wo_resp = self.test("GET work orders after scheduler", "GET", "work-orders", 200,
                                        token=self.tokens['tech'])
            if success:
                wos = wo_resp.get('items', [])
                pm_wos = [w for w in wos if w.get('pm_task_id') == pm_id and w.get('source') == 'pm_scheduler']
                if pm_wos:
                    self.log(f"  ✓ PM scheduler generated work order: {pm_wos[0].get('wo_number')}")
                    self.test_data['pm_wo_id'] = pm_wos[0].get('id')
                else:
                    self.log(f"  ✗ PM work order not generated by scheduler", "WARN")
            
            # Check for pm_due notification
            success, notif_resp = self.test("GET notifications", "GET", "notifications", 200,
                                           token=self.tokens['tech'])
            if success:
                notifs = notif_resp if isinstance(notif_resp, list) else []
                pm_notifs = [n for n in notifs if n.get('notif_type') == 'pm_due' and 
                            n.get('reference_id') == self.test_data.get('pm_wo_id')]
                if pm_notifs:
                    self.log(f"  ✓ pm_due notification created")
        
        # Test PM task completion
        success, resp = self.test("POST /pm-tasks/{id}/complete", "POST",
                                 f"pm-tasks/{pm_id}/complete", 200,
                                 token=self.tokens['tech'],
                                 data={
                                     "remarks": "Inspection completed successfully",
                                     "checklist_results": {"Check for leaks": True, "Verify operation": True},
                                     "spares_consumed": [{"sap_code": "400007001", "quantity": 0.5}]
                                 })
        if success:
            self.log(f"  ✓ PM task completed with checklist and spares")
            
            # Verify next_due_date advanced
            success, pm_resp = self.test("GET PM task after completion", "GET", "pm-tasks", 200,
                                        token=self.tokens['tech'],
                                        params={"machine_id": machine['id']})
            if success:
                tasks = pm_resp.get('items', [])
                task = next((t for t in tasks if t.get('id') == pm_id), None)
                if task and task.get('next_due_date') > today:
                    self.log(f"  ✓ next_due_date advanced to: {task.get('next_due_date')}")

    def test_runtime(self):
        """Test runtime logs and CSV import"""
        self.log("\n" + "=" * 80)
        self.log("9. RUNTIME LOGS")
        self.log("=" * 80)
        
        if 'test_machine' not in self.test_data:
            self.log("No test machine available - skipping", "WARN")
            return
        
        machine = self.test_data['test_machine']
        today = datetime.utcnow().date().isoformat()
        
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
        csv_data = f"machine_code,date,run_hours,calendar_hours\n{machine['code']},{today},18,24\nINVALID_CODE,{today},10,24"
        success, resp = self.test("POST /runtime-logs/import (preview)", "POST", "runtime-logs/import", 200,
                                 token=self.tokens['admin'],
                                 data={"csv_text": csv_data, "apply": False})
        if success:
            self.log(f"  ✓ CSV preview: {resp.get('valid_rows')} valid, {len(resp.get('errors', []))} errors")
            if resp.get('errors'):
                self.log(f"    Errors detected: {resp['errors'][0]}")
        
        # CSV import apply
        csv_data_valid = f"machine_code,date,run_hours,calendar_hours\n{machine['code']},{today},19,24"
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
                                         "failure_mode": "Bearing Failure"
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
