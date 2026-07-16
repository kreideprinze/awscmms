"""
Comprehensive backend test for Autonomous Maintenance (AM) Checklist module.
Tests all CRUD operations, public endpoints, authenticated endpoints, side effects, and PDF generation.
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class AMChecklistTester:
    def __init__(self):
        self.admin_token = None
        self.tech_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_template_id = None
        self.test_submission_id = None
        self.test_machine_id = None
        self.demo_template_id = None
        self.failures = []

    def log(self, msg, status="INFO"):
        prefix = "✅" if status == "PASS" else "❌" if status == "FAIL" else "🔍"
        print(f"{prefix} {msg}")

    def test(self, name, method, endpoint, expected_status, data=None, token=None, params=None):
        """Run a single API test"""
        url = f"{BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        self.log(f"Testing {name}...", "INFO")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"PASSED - {name} (Status: {response.status_code})", "PASS")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.log(f"FAILED - {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    error_detail = response.json()
                    self.log(f"  Error: {error_detail}", "FAIL")
                    self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code} - {error_detail}")
                except:
                    self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                return False, {}

        except Exception as e:
            self.log(f"FAILED - {name} - Error: {str(e)}", "FAIL")
            self.failures.append(f"{name}: Exception - {str(e)}")
            return False, {}

    def login(self, username, password):
        """Login and get token"""
        success, response = self.test(
            f"Login as {username}",
            "POST",
            "/auth/login",
            200,
            data={"username": username, "password": password}
        )
        if success and 'token' in response:
            return response['token']
        return None

    def get_machines(self):
        """Get list of machines"""
        success, response = self.test(
            "Get machines list",
            "GET",
            "/machines",
            200,
            token=self.admin_token
        )
        if success and response:
            return response
        return []

    def get_demo_template(self):
        """Find the demo 'AM — Fryer' template"""
        success, response = self.test(
            "Get AM templates to find demo",
            "GET",
            "/am-templates",
            200,
            token=self.admin_token
        )
        if success and response:
            for t in response:
                if 'Fryer' in t.get('template_name', ''):
                    self.demo_template_id = t['id']
                    self.log(f"Found demo template: {t['template_name']} (ID: {t['id']})", "INFO")
                    return t
        return None

    # ============ BACKEND 1: Template CRUD (admin) ============
    
    def test_backend_1_template_crud(self):
        self.log("\n=== BACKEND 1: Template CRUD (admin) ===", "INFO")
        
        # Get a machine for testing
        machines = self.get_machines()
        if not machines:
            self.log("No machines found - cannot test template creation", "FAIL")
            return False
        
        self.test_machine_id = machines[0]['id']
        self.log(f"Using machine: {machines[0]['name']} (ID: {self.test_machine_id})", "INFO")
        
        # Test 1: Create template with valid data
        template_data = {
            "machine_id": self.test_machine_id,
            "template_name": f"TEST_AM_Template_{datetime.now().strftime('%H%M%S')}",
            "checklist_groups": [
                {
                    "description": "Test Sub-Component 1",
                    "items": [
                        {"checked_for": "Test Check 1", "parameter": "Visual"},
                        {"checked_for": "Test Check 2", "parameter": "Measurement"}
                    ]
                },
                {
                    "description": "Test Sub-Component 2",
                    "items": [
                        {"checked_for": "Test Check 3", "parameter": ""}
                    ]
                }
            ]
        }
        
        success, response = self.test(
            "Create AM template (admin)",
            "POST",
            "/am-templates",
            200,
            data=template_data,
            token=self.admin_token
        )
        
        if success:
            self.test_template_id = response.get('id')
            # Verify frequency is 'per_shift'
            if response.get('frequency') == 'per_shift':
                self.log("Frequency correctly set to 'per_shift'", "PASS")
                self.tests_passed += 1
            else:
                self.log(f"Frequency incorrect: {response.get('frequency')}", "FAIL")
                self.failures.append("Template frequency not 'per_shift'")
            self.tests_run += 1
        
        # Test 2: Create template with empty groups (should fail with 400)
        self.test(
            "Create template with empty groups (should fail)",
            "POST",
            "/am-templates",
            400,
            data={
                "machine_id": self.test_machine_id,
                "template_name": "Empty Template",
                "checklist_groups": []
            },
            token=self.admin_token
        )
        
        # Test 3: Create template as tech (should fail with 403)
        self.test(
            "Create template as tech (should fail)",
            "POST",
            "/am-templates",
            403,
            data=template_data,
            token=self.tech_token
        )
        
        # Test 4: Update template name
        if self.test_template_id:
            self.test(
                "Update template name",
                "PUT",
                f"/am-templates/{self.test_template_id}",
                200,
                data={"template_name": f"UPDATED_TEST_AM_{datetime.now().strftime('%H%M%S')}"},
                token=self.admin_token
            )
        
        # Test 5: Duplicate template to another machine
        if self.test_template_id and len(machines) > 1:
            target_machine_id = machines[1]['id']
            success, dup_response = self.test(
                "Duplicate template to another machine",
                "POST",
                f"/am-templates/{self.test_template_id}/duplicate",
                200,
                data={"target_machine_id": target_machine_id},
                token=self.admin_token
            )
        
        # Test 6: Delete a test template (create a new one for deletion)
        delete_template_data = {
            "machine_id": self.test_machine_id,
            "template_name": f"DELETE_ME_{datetime.now().strftime('%H%M%S')}",
            "checklist_groups": [
                {
                    "description": "Temp Group",
                    "items": [{"checked_for": "Temp Check", "parameter": ""}]
                }
            ]
        }
        success, del_template = self.test(
            "Create template for deletion test",
            "POST",
            "/am-templates",
            200,
            data=delete_template_data,
            token=self.admin_token
        )
        
        if success and del_template.get('id'):
            self.test(
                "Delete AM template",
                "DELETE",
                f"/am-templates/{del_template['id']}",
                200,
                token=self.admin_token
            )

    # ============ BACKEND 2: Public endpoints (NO auth) ============
    
    def test_backend_2_public_endpoints(self):
        self.log("\n=== BACKEND 2: Public endpoints (NO auth) ===", "INFO")
        
        # Test 1: GET /public/am-context
        success, response = self.test(
            "Get public AM context",
            "GET",
            "/public/am-context",
            200
        )
        
        if success and 'templates' in response:
            self.log(f"Found {len(response['templates'])} public templates", "INFO")
        
        # Test 2: GET /public/am-templates/{id}
        if self.demo_template_id:
            success, template = self.test(
                "Get public AM template",
                "GET",
                f"/public/am-templates/{self.demo_template_id}",
                200
            )
            
            if success and template.get('checklist_groups'):
                self.log(f"Template has {len(template['checklist_groups'])} groups", "INFO")
        
        # Test 3: POST /public/am-submissions - missing name (should fail 400)
        self.test(
            "Public submit without name (should fail)",
            "POST",
            "/public/am-submissions",
            400,
            data={
                "template_id": self.demo_template_id or "dummy",
                "name": "",
                "gpid": "12345",
                "shift": "A",
                "row_results": []
            }
        )
        
        # Test 4: POST /public/am-submissions - missing gpid (should fail 400)
        self.test(
            "Public submit without GPID (should fail)",
            "POST",
            "/public/am-submissions",
            400,
            data={
                "template_id": self.demo_template_id or "dummy",
                "name": "Test Operator",
                "gpid": "",
                "shift": "A",
                "row_results": []
            }
        )
        
        # Test 5: POST /public/am-submissions - invalid shift 'D' (should fail 400)
        self.test(
            "Public submit with invalid shift D (should fail)",
            "POST",
            "/public/am-submissions",
            400,
            data={
                "template_id": self.demo_template_id or "dummy",
                "name": "Test Operator",
                "gpid": "12345",
                "shift": "D",
                "row_results": []
            }
        )
        
        # Test 6: POST /public/am-submissions - NOT_OK without remarks (should fail 400)
        if self.demo_template_id:
            # Get template to build proper row_results
            success, template = self.test(
                "Get template for NOT_OK test",
                "GET",
                f"/public/am-templates/{self.demo_template_id}",
                200
            )
            
            if success and template.get('checklist_groups'):
                # Build row_results with one NOT_OK item without remarks
                row_results = []
                for group in template['checklist_groups']:
                    for item in group['items']:
                        row_results.append({
                            "description": group['description'],
                            "checked_for": item['checked_for'],
                            "parameter": item.get('parameter', ''),
                            "status": "NOT_OK",
                            "remarks": ""  # Missing remarks for NOT_OK
                        })
                        break  # Just one item
                    break
                
                success, error_response = self.test(
                    "Public submit NOT_OK without remarks (should fail)",
                    "POST",
                    "/public/am-submissions",
                    400,
                    data={
                        "template_id": self.demo_template_id,
                        "name": "Test Operator",
                        "gpid": "12345",
                        "shift": "A",
                        "row_results": row_results
                    }
                )
                
                # Verify error mentions remarks
                if not success and error_response:
                    detail = str(error_response.get('detail', ''))
                    if 'remarks' in detail.lower() or 'required' in detail.lower():
                        self.log("Error correctly mentions remarks requirement", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log(f"Error doesn't mention remarks: {detail}", "FAIL")
                        self.failures.append("NOT_OK validation error doesn't mention remarks")
                    self.tests_run += 1
        
        # Test 7: POST /public/am-submissions - unanswered item (should fail 400)
        if self.demo_template_id:
            success, template = self.test(
                "Get template for unanswered test",
                "GET",
                f"/public/am-templates/{self.demo_template_id}",
                200
            )
            
            if success and template.get('checklist_groups'):
                # Build incomplete row_results (missing some items)
                row_results = []
                for group in template['checklist_groups']:
                    if group['items']:
                        # Only answer first item, leave rest unanswered
                        item = group['items'][0]
                        row_results.append({
                            "description": group['description'],
                            "checked_for": item['checked_for'],
                            "parameter": item.get('parameter', ''),
                            "status": "OK",
                            "remarks": ""
                        })
                        break
                
                self.test(
                    "Public submit with unanswered items (should fail)",
                    "POST",
                    "/public/am-submissions",
                    400,
                    data={
                        "template_id": self.demo_template_id,
                        "name": "Test Operator",
                        "gpid": "12345",
                        "shift": "A",
                        "row_results": row_results
                    }
                )
        
        # Test 8: POST /public/am-submissions - valid full submission
        if self.demo_template_id:
            success, template = self.test(
                "Get template for valid submission",
                "GET",
                f"/public/am-templates/{self.demo_template_id}",
                200
            )
            
            if success and template.get('checklist_groups'):
                # Build complete row_results
                row_results = []
                not_ok_count = 0
                for group in template['checklist_groups']:
                    for idx, item in enumerate(group['items']):
                        # Make first item NOT_OK with remarks, rest OK
                        status = "NOT_OK" if idx == 0 else "OK"
                        remarks = "Test issue found" if status == "NOT_OK" else ""
                        if status == "NOT_OK":
                            not_ok_count += 1
                        
                        row_results.append({
                            "description": group['description'],
                            "checked_for": item['checked_for'],
                            "parameter": item.get('parameter', ''),
                            "status": status,
                            "remarks": remarks
                        })
                
                started_at = datetime.utcnow().isoformat() + 'Z'
                
                success, sub_response = self.test(
                    "Public submit valid full submission",
                    "POST",
                    "/public/am-submissions",
                    200,
                    data={
                        "template_id": self.demo_template_id,
                        "name": f"Test_Operator_{datetime.now().strftime('%H%M%S')}",
                        "gpid": "TEST12345",
                        "shift": "A",
                        "started_at": started_at,
                        "row_results": row_results
                    }
                )
                
                if success:
                    # Verify response fields
                    checks = [
                        ('ok', True, sub_response.get('ok')),
                        ('id', True, bool(sub_response.get('id'))),
                        ('not_ok_count', not_ok_count, sub_response.get('not_ok_count')),
                        ('duration_minutes', True, sub_response.get('duration_minutes') is not None)
                    ]
                    
                    for field, expected, actual in checks:
                        self.tests_run += 1
                        if expected == actual or (expected is True and actual):
                            self.log(f"Field '{field}' correct: {actual}", "PASS")
                            self.tests_passed += 1
                        else:
                            self.log(f"Field '{field}' incorrect: expected {expected}, got {actual}", "FAIL")
                            self.failures.append(f"Public submission field '{field}' incorrect")
                    
                    # Store for later tests
                    self.test_submission_id = sub_response.get('id')

    # ============ BACKEND 3: Authenticated submit & filters ============
    
    def test_backend_3_authenticated_submit(self):
        self.log("\n=== BACKEND 3: Authenticated submit & filters ===", "INFO")
        
        # Test 1: POST /am-submissions (authenticated)
        if self.demo_template_id:
            success, template = self.test(
                "Get template for auth submission",
                "GET",
                f"/public/am-templates/{self.demo_template_id}",
                200
            )
            
            if success and template.get('checklist_groups'):
                # Build complete row_results (all OK)
                row_results = []
                for group in template['checklist_groups']:
                    for item in group['items']:
                        row_results.append({
                            "description": group['description'],
                            "checked_for": item['checked_for'],
                            "parameter": item.get('parameter', ''),
                            "status": "OK",
                            "remarks": ""
                        })
                
                started_at = datetime.utcnow().isoformat() + 'Z'
                
                success, sub_response = self.test(
                    "Authenticated submit (as tech)",
                    "POST",
                    "/am-submissions",
                    200,
                    data={
                        "template_id": self.demo_template_id,
                        "name": f"Tech_User_{datetime.now().strftime('%H%M%S')}",
                        "gpid": "TECH999",
                        "shift": "B",
                        "started_at": started_at,
                        "row_results": row_results
                    },
                    token=self.tech_token
                )
        
        # Test 2: GET /am-submissions with filters
        # Filter by machine_id
        if self.test_machine_id:
            self.test(
                "Get submissions filtered by machine_id",
                "GET",
                "/am-submissions",
                200,
                token=self.tech_token,
                params={"machine_id": self.test_machine_id}
            )
        
        # Filter by shift=A
        self.test(
            "Get submissions filtered by shift A",
            "GET",
            "/am-submissions",
            200,
            token=self.tech_token,
            params={"shift": "A"}
        )
        
        # Filter by date range
        today = datetime.now().strftime('%Y-%m-%d')
        self.test(
            "Get submissions filtered by date range",
            "GET",
            "/am-submissions",
            200,
            token=self.tech_token,
            params={"date_from": today, "date_to": today}
        )
        
        # Test 3: GET /am-coverage
        success, coverage = self.test(
            "Get AM coverage board",
            "GET",
            "/am-coverage",
            200,
            token=self.tech_token
        )
        
        if success and coverage:
            # Verify structure
            if 'date' in coverage and 'rows' in coverage:
                self.log(f"Coverage board has {len(coverage['rows'])} templates", "INFO")
                # Check shift structure
                if coverage['rows']:
                    first_row = coverage['rows'][0]
                    if 'shifts' in first_row:
                        shifts = first_row['shifts']
                        for shift in ['A', 'B', 'C']:
                            if shift in shifts:
                                shift_data = shifts[shift]
                                if 'done' in shift_data and 'count' in shift_data and 'last_by' in shift_data:
                                    self.log(f"Shift {shift} structure correct", "PASS")
                                    self.tests_passed += 1
                                else:
                                    self.log(f"Shift {shift} structure incorrect", "FAIL")
                                    self.failures.append(f"Coverage shift {shift} missing fields")
                                self.tests_run += 1

    # ============ BACKEND 4: Side effects (timeline & notifications) ============
    
    def test_backend_4_side_effects(self):
        self.log("\n=== BACKEND 4: Side effects (timeline & notifications) ===", "INFO")
        
        # Get timeline events
        success, timeline = self.test(
            "Get timeline events",
            "GET",
            "/timeline",
            200,
            token=self.admin_token,
            params={"limit": 100}
        )
        
        if success and timeline:
            # Look for am_submitted events
            am_events = [e for e in timeline if e.get('event_type') == 'am_submitted']
            if am_events:
                self.log(f"Found {len(am_events)} AM submission timeline events", "PASS")
                self.tests_passed += 1
            else:
                self.log("No AM submission timeline events found", "FAIL")
                self.failures.append("No am_submitted timeline events")
            self.tests_run += 1
        
        # Get notifications
        success, notifications = self.test(
            "Get notifications",
            "GET",
            "/notifications",
            200,
            token=self.admin_token
        )
        
        if success and notifications:
            # Look for AM checklist notifications
            am_notifs = [n for n in notifications if 'AM Checklist' in n.get('title', '') or 'AM checklist' in n.get('message', '')]
            if am_notifs:
                self.log(f"Found {len(am_notifs)} AM checklist notifications", "INFO")
                # Check if any mention "flagged issues"
                flagged = [n for n in am_notifs if 'flagged' in n.get('message', '').lower()]
                if flagged:
                    self.log(f"Found {len(flagged)} flagged-issues notifications", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("No flagged-issues notifications found (may be OK if all submissions were OK)", "INFO")
                self.tests_run += 1

    # ============ BACKEND 5: PDF generation ============
    
    def test_backend_5_pdf(self):
        self.log("\n=== BACKEND 5: PDF generation ===", "INFO")
        
        # Test 1: GET blank PDF (authenticated)
        if self.demo_template_id:
            url = f"{BASE_URL}/am-templates/{self.demo_template_id}/pdf"
            headers = {'Authorization': f'Bearer {self.admin_token}'}
            
            self.tests_run += 1
            self.log("Testing blank PDF download...", "INFO")
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    if response.headers.get('content-type') == 'application/pdf':
                        pdf_size = len(response.content)
                        if pdf_size > 20000:  # >20KB
                            self.log(f"Blank PDF downloaded successfully ({pdf_size} bytes)", "PASS")
                            self.tests_passed += 1
                        else:
                            self.log(f"Blank PDF too small ({pdf_size} bytes)", "FAIL")
                            self.failures.append(f"Blank PDF size {pdf_size} < 20KB")
                    else:
                        self.log(f"Wrong content-type: {response.headers.get('content-type')}", "FAIL")
                        self.failures.append("Blank PDF wrong content-type")
                else:
                    self.log(f"Blank PDF failed: {response.status_code}", "FAIL")
                    self.failures.append(f"Blank PDF returned {response.status_code}")
            except Exception as e:
                self.log(f"Blank PDF error: {str(e)}", "FAIL")
                self.failures.append(f"Blank PDF exception: {str(e)}")
        
        # Test 2: GET completed PDF with submission_id=latest
        if self.demo_template_id:
            url = f"{BASE_URL}/am-templates/{self.demo_template_id}/pdf?submission_id=latest"
            headers = {'Authorization': f'Bearer {self.admin_token}'}
            
            self.tests_run += 1
            self.log("Testing completed PDF download (latest)...", "INFO")
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    if response.headers.get('content-type') == 'application/pdf':
                        pdf_size = len(response.content)
                        self.log(f"Completed PDF downloaded successfully ({pdf_size} bytes)", "PASS")
                        self.tests_passed += 1
                    else:
                        self.log(f"Wrong content-type: {response.headers.get('content-type')}", "FAIL")
                        self.failures.append("Completed PDF wrong content-type")
                else:
                    self.log(f"Completed PDF failed: {response.status_code}", "FAIL")
                    self.failures.append(f"Completed PDF returned {response.status_code}")
            except Exception as e:
                self.log(f"Completed PDF error: {str(e)}", "FAIL")
                self.failures.append(f"Completed PDF exception: {str(e)}")
        
        # Test 3: Unauthenticated PDF request (should fail 401/403)
        if self.demo_template_id:
            url = f"{BASE_URL}/am-templates/{self.demo_template_id}/pdf"
            
            self.tests_run += 1
            self.log("Testing unauthenticated PDF request (should fail)...", "INFO")
            try:
                response = requests.get(url, timeout=15)
                if response.status_code in [401, 403]:
                    self.log(f"Unauthenticated PDF correctly rejected ({response.status_code})", "PASS")
                    self.tests_passed += 1
                else:
                    self.log(f"Unauthenticated PDF should fail but got {response.status_code}", "FAIL")
                    self.failures.append(f"Unauthenticated PDF returned {response.status_code} instead of 401/403")
            except Exception as e:
                self.log(f"Unauthenticated PDF error: {str(e)}", "FAIL")
                self.failures.append(f"Unauthenticated PDF exception: {str(e)}")

    # ============ Cleanup ============
    
    def cleanup(self):
        self.log("\n=== Cleanup: Deleting test data ===", "INFO")
        
        # Get all templates and delete test ones (keep demo)
        success, templates = self.test(
            "Get all templates for cleanup",
            "GET",
            "/am-templates",
            200,
            token=self.admin_token
        )
        
        if success and templates:
            for t in templates:
                # Delete if it's a test template (starts with TEST or UPDATED_TEST)
                if t['template_name'].startswith('TEST') or t['template_name'].startswith('UPDATED_TEST'):
                    self.log(f"Deleting test template: {t['template_name']}", "INFO")
                    requests.delete(f"{BASE_URL}/am-templates/{t['id']}", 
                                  headers={'Authorization': f'Bearer {self.admin_token}'})

    def run_all_tests(self):
        """Run all backend tests"""
        print("\n" + "="*80)
        print("AUTONOMOUS MAINTENANCE (AM) CHECKLIST - BACKEND TEST SUITE")
        print("="*80 + "\n")
        
        # Login
        self.log("Logging in...", "INFO")
        self.admin_token = self.login("admin", "admin123")
        if not self.admin_token:
            self.log("Admin login failed - cannot continue", "FAIL")
            return False
        
        self.tech_token = self.login("tech", "tech123")
        if not self.tech_token:
            self.log("Tech login failed - cannot continue", "FAIL")
            return False
        
        # Find demo template
        self.get_demo_template()
        
        # Run test suites
        self.test_backend_1_template_crud()
        self.test_backend_2_public_endpoints()
        self.test_backend_3_authenticated_submit()
        self.test_backend_4_side_effects()
        self.test_backend_5_pdf()
        
        # Cleanup
        self.cleanup()
        
        # Print summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failures:
            print("\n" + "="*80)
            print("FAILURES:")
            print("="*80)
            for i, failure in enumerate(self.failures, 1):
                print(f"{i}. {failure}")
        
        print("\n" + "="*80 + "\n")
        
        return self.tests_passed == self.tests_run

def main():
    tester = AMChecklistTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
