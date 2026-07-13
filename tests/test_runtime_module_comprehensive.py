"""Comprehensive test suite for Runtime Module Rework (Planned Runtime Model)"""
import requests
import sys
from datetime import datetime, timedelta, timezone

BASE = "https://content-extractor-75.preview.emergentagent.com/api"

class RuntimeModuleTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.admin_token = None
        self.tech_token = None
        self.test_machine_id = None
        self.test_breakdowns = []
        self.test_warnings = []
        self.test_runtime_entries = []
        
    def check(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            print(f"✅ PASS: {name} {detail}")
            return True
        else:
            self.failed += 1
            print(f"❌ FAIL: {name} {detail}")
            return False
    
    def login(self, username, password):
        """Login and return token"""
        try:
            r = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=10)
            if r.status_code == 200:
                return r.json().get('token')
        except Exception as e:
            print(f"Login error for {username}: {e}")
        return None
    
    def test_auth(self):
        """Test authentication"""
        print("\n=== AUTHENTICATION TESTS ===")
        self.admin_token = self.login("admin", "admin123")
        self.check("Admin login", self.admin_token is not None, f"token={'present' if self.admin_token else 'missing'}")
        
        self.tech_token = self.login("tech", "tech123")
        self.check("Tech login", self.tech_token is not None, f"token={'present' if self.tech_token else 'missing'}")
        
        return self.admin_token is not None
    
    def get_test_machine(self):
        """Get a PC21 machine for testing"""
        try:
            r = requests.get(f"{BASE}/machines", headers={"Authorization": f"Bearer {self.admin_token}"}, timeout=10)
            if r.status_code == 200:
                machines = r.json()
                pc21 = next((m for m in machines if m.get('line') == 'PC21'), None)
                if pc21:
                    self.test_machine_id = pc21['id']
                    return True
        except Exception as e:
            print(f"Error getting test machine: {e}")
        return False
    
    def test_runtime_validation(self):
        """Test runtime log validation"""
        print("\n=== RUNTIME VALIDATION TESTS ===")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        
        # Test planned_hours > 24
        r = requests.post(f"{BASE}/runtime-logs", 
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": yesterday, "planned_hours": 30},
                         timeout=10)
        self.check("Reject planned_hours > 24", r.status_code == 400, f"status={r.status_code}")
        
        # Test planned_hours <= 0
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": yesterday, "planned_hours": 0},
                         timeout=10)
        self.check("Reject planned_hours = 0", r.status_code == 400, f"status={r.status_code}")
        
        # Test negative planned_hours
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": yesterday, "planned_hours": -5},
                         timeout=10)
        self.check("Reject negative planned_hours", r.status_code == 400, f"status={r.status_code}")
        
        # Test legacy body format (should fail with 422)
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": yesterday, "calendar_hours": 24, "run_hours": 20},
                         timeout=10)
        self.check("Reject legacy body format", r.status_code == 422, f"status={r.status_code}")
    
    def test_planned_runtime_creation(self):
        """Test creating planned runtime entries"""
        print("\n=== PLANNED RUNTIME CREATION TESTS ===")
        day1 = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        day2 = (datetime.now(timezone.utc) - timedelta(days=11)).date().isoformat()
        
        # Create entry with 16 hours
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": day1, "planned_hours": 16},
                         timeout=10)
        if self.check("Create planned runtime 16h", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            self.test_runtime_entries.append({"line": "PC21", "date": day1})
            self.check("Response has planned_hours", data.get('planned_hours') == 16.0)
            self.check("Response has downtime_hours", 'downtime_hours' in data)
            self.check("Response has run_hours", 'run_hours' in data)
            self.check("Response has availability", 'availability' in data)
            self.check("Response has clamped flag", 'clamped' in data)
            self.check("Initial availability is 100%", data.get('availability') == 100.0, f"avail={data.get('availability')}")
        
        # Create entry with 8 hours
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": day2, "planned_hours": 8},
                         timeout=10)
        if self.check("Create planned runtime 8h", r.status_code == 200, f"status={r.status_code}"):
            self.test_runtime_entries.append({"line": "PC21", "date": day2})
    
    def test_derived_downtime(self):
        """Test downtime derivation from breakdowns"""
        print("\n=== DERIVED DOWNTIME TESTS ===")
        if not self.test_machine_id:
            print("Skipping - no test machine")
            return
        
        day1 = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        
        # Create a breakdown with exactly 2 hours downtime
        start_time = f"{day1}T08:00:00+00:00"
        end_time = f"{day1}T10:00:00+00:00"
        
        # Create breakdown
        r = requests.post(f"{BASE}/breakdowns",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"machine_id": self.test_machine_id, 
                              "description": "Test 2h breakdown for runtime",
                              "failure_mode": "Mechanical",
                              "assigned_to": "tech"},
                         timeout=10)
        if self.check("Create test breakdown", r.status_code in (200, 201), f"status={r.status_code}"):
            bd = r.json()
            self.test_breakdowns.append(bd['id'])
            
            # Close breakdown with specific times
            r = requests.put(f"{BASE}/breakdowns/{bd['id']}",
                           headers={"Authorization": f"Bearer {self.admin_token}"},
                           json={"action": "close", 
                                "start_time": start_time,
                                "end_time": end_time,
                                "action_taken": "Test closure",
                                "assigned_to": "tech"},
                           timeout=10)
            if self.check("Close breakdown with 2h downtime", r.status_code == 200, f"status={r.status_code}"):
                close_data = r.json()
                downtime_min = close_data.get('downtime_minutes', 0)
                self.check("Downtime is 120 minutes", abs(downtime_min - 120) < 1, f"downtime={downtime_min}min")
                
                # Check if RCA was triggered (>30min)
                if close_data.get('rca_required'):
                    print(f"  ℹ️  RCA triggered as expected (downtime > 30min): rca_task_id={close_data.get('rca_task_id')}")
        
        # Read runtime log to verify derived downtime
        r = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={day1}&date_to={day1}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        if self.check("Read runtime logs", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            if data.get('items'):
                row = data['items'][0]
                self.check("Derived downtime ≈ 2h", abs(row.get('downtime_hours', 0) - 2.0) < 0.1, 
                          f"downtime={row.get('downtime_hours')}h")
                self.check("Derived run ≈ 14h", abs(row.get('run_hours', 0) - 14.0) < 0.1,
                          f"run={row.get('run_hours')}h")
                expected_avail = (14.0 / 16.0) * 100
                self.check("Availability ≈ 87.5%", abs(row.get('availability', 0) - expected_avail) < 1.0,
                          f"avail={row.get('availability')}%")
                self.check("Not clamped", row.get('clamped') == False, f"clamped={row.get('clamped')}")
    
    def test_clamp_logic(self):
        """Test availability clamping when downtime > planned"""
        print("\n=== CLAMP LOGIC TESTS ===")
        if not self.test_machine_id:
            print("Skipping - no test machine")
            return
        
        day_clamp = (datetime.now(timezone.utc) - timedelta(days=15)).date().isoformat()
        
        # Create a 2h breakdown first
        start_time = f"{day_clamp}T02:00:00+00:00"
        end_time = f"{day_clamp}T04:00:00+00:00"
        
        r = requests.post(f"{BASE}/breakdowns",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"machine_id": self.test_machine_id,
                              "description": "Test clamp breakdown",
                              "failure_mode": "Mechanical",
                              "assigned_to": "tech"},
                         timeout=10)
        if r.status_code in (200, 201):
            bd = r.json()
            self.test_breakdowns.append(bd['id'])
            
            # Close with 2h downtime
            requests.put(f"{BASE}/breakdowns/{bd['id']}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        json={"action": "close",
                             "start_time": start_time,
                             "end_time": end_time,
                             "action_taken": "Test",
                             "assigned_to": "tech"},
                        timeout=10)
        
        # Now log only 1h planned runtime (less than 2h downtime)
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": day_clamp, "planned_hours": 1},
                         timeout=10)
        if self.check("Create planned runtime 1h (< downtime)", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            self.test_runtime_entries.append({"line": "PC21", "date": day_clamp})
            self.check("Availability clamped to 0%", data.get('availability') == 0.0, 
                      f"avail={data.get('availability')}%")
            self.check("Clamped flag is True", data.get('clamped') == True,
                      f"clamped={data.get('clamped')}")
    
    def test_warnings_exclusion(self):
        """Test that warnings do NOT count as downtime"""
        print("\n=== WARNINGS EXCLUSION TESTS ===")
        if not self.test_machine_id:
            print("Skipping - no test machine")
            return
        
        day1 = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        
        # Get current downtime
        r = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={day1}&date_to={day1}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        downtime_before = 0
        if r.status_code == 200 and r.json().get('items'):
            downtime_before = r.json()['items'][0].get('downtime_hours', 0)
        
        # Create a warning
        r = requests.post(f"{BASE}/warnings",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"machine_id": self.test_machine_id,
                              "description": "Test warning - should not affect downtime",
                              "warning_type": "MECHANICAL"},
                         timeout=10)
        warning_created = r.status_code in (200, 201)
        if warning_created:
            self.test_warnings.append(r.json().get('id'))
            self.check("Warning created", True, f"status={r.status_code}")
        else:
            print(f"  ⚠️  Warning creation failed (status={r.status_code}), may not have /warnings endpoint")
        
        # Read downtime again
        r = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={day1}&date_to={day1}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        if r.status_code == 200 and r.json().get('items'):
            downtime_after = r.json()['items'][0].get('downtime_hours', 0)
            self.check("Downtime unchanged after warning", 
                      abs(downtime_after - downtime_before) < 0.01,
                      f"before={downtime_before}h, after={downtime_after}h")
    
    def test_control_room_apis(self):
        """Test Control Room KPI endpoints"""
        print("\n=== CONTROL ROOM API TESTS ===")
        day1 = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        
        # Test custom date range
        r = requests.get(f"{BASE}/control-room/line-kpis?date_from={day1}&date_to={day1}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        if self.check("Control Room custom date range", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            self.check("Response has lines array", 'lines' in data and isinstance(data['lines'], list))
            self.check("Response has plant_availability", 'plant_availability' in data)
            
            # Find PC21 line
            pc21 = next((l for l in data.get('lines', []) if l.get('line') == 'PC21'), None)
            if pc21:
                self.check("PC21 has planned_minutes", 'planned_minutes' in pc21)
                self.check("PC21 has downtime_minutes", 'downtime_minutes' in pc21)
                self.check("PC21 has availability", 'availability' in pc21)
                self.check("PC21 has clamped field", 'clamped' in pc21)
                print(f"  ℹ️  PC21: planned={pc21.get('planned_minutes')}min, down={pc21.get('downtime_minutes')}min, avail={pc21.get('availability')}%")
        
        # Test live window (24h, unlogged days use 24/7 fallback)
        r = requests.get(f"{BASE}/control-room/line-kpis?hours=24",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        if self.check("Control Room live 24h window", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            lines = data.get('lines', [])
            all_have_avail = all(l.get('availability') is not None for l in lines)
            self.check("All lines have availability (24/7 fallback)", all_have_avail,
                      f"lines_with_null_avail={sum(1 for l in lines if l.get('availability') is None)}")
    
    def test_analytics_apis(self):
        """Test Analytics KPI endpoints"""
        print("\n=== ANALYTICS API TESTS ===")
        day1 = (datetime.now(timezone.utc) - timedelta(days=15)).date().isoformat()
        day2 = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        
        # Test plant level
        r = requests.get(f"{BASE}/analytics/kpis?level=plant&date_from={day1}&date_to={day2}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        if self.check("Analytics plant level", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            self.check("Has planned_hours key", 'planned_hours' in data)
            self.check("Has run_hours key", 'run_hours' in data)
            self.check("NO calendar_hours key", 'calendar_hours' not in data)
            self.check("Has availability", 'availability' in data)
            self.check("Has availability_trend", 'availability_trend' in data and isinstance(data['availability_trend'], list))
            print(f"  ℹ️  Plant: planned={data.get('planned_hours')}h, run={data.get('run_hours')}h, avail={data.get('availability')}%")
        
        # Test machine level (inherits line's planned hours)
        if self.test_machine_id:
            r = requests.get(f"{BASE}/analytics/kpis?level=machine&value={self.test_machine_id}&date_from={day1}&date_to={day2}",
                            headers={"Authorization": f"Bearer {self.admin_token}"},
                            timeout=10)
            if self.check("Analytics machine level", r.status_code == 200, f"status={r.status_code}"):
                data = r.json()
                self.check("Machine has planned_hours", 'planned_hours' in data and data.get('planned_hours', 0) > 0)
    
    def test_machine_detail(self):
        """Test machine detail runtime block"""
        print("\n=== MACHINE DETAIL TESTS ===")
        if not self.test_machine_id:
            print("Skipping - no test machine")
            return
        
        r = requests.get(f"{BASE}/machines/{self.test_machine_id}",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        if self.check("Machine detail endpoint", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            runtime = data.get('runtime', {})
            self.check("Has runtime block", len(runtime) > 0)
            self.check("Runtime has planned_hours", 'planned_hours' in runtime)
            self.check("Runtime has downtime_hours", 'downtime_hours' in runtime)
            self.check("Runtime has run_hours", 'run_hours' in runtime)
            self.check("Runtime has logged_days", 'logged_days' in runtime)
            self.check("Runtime has availability", 'availability' in runtime)
            print(f"  ℹ️  Runtime: planned={runtime.get('planned_hours')}h, down={runtime.get('downtime_hours')}h, run={runtime.get('run_hours')}h, days={runtime.get('logged_days')}")
    
    def test_csv_import(self):
        """Test CSV import with planned model"""
        print("\n=== CSV IMPORT TESTS ===")
        day_csv = (datetime.now(timezone.utc) - timedelta(days=20)).date().isoformat()
        
        # Valid CSV
        csv_text = f"line,date,planned_hours\nPC21,{day_csv},20"
        r = requests.post(f"{BASE}/runtime-logs/import",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"csv_text": csv_text, "apply": True},
                         timeout=10)
        if self.check("CSV import with planned model", r.status_code == 200, f"status={r.status_code}"):
            data = r.json()
            self.check("Imported 1 row", data.get('imported') == 1, f"imported={data.get('imported')}")
            self.test_runtime_entries.append({"line": "PC21", "date": day_csv})
        
        # Legacy CSV (should fail)
        bad_csv = "line,date,run_hours\nPC21,2026-01-01,20"
        r = requests.post(f"{BASE}/runtime-logs/import",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"csv_text": bad_csv, "apply": False},
                         timeout=10)
        self.check("CSV rejects legacy columns", r.status_code == 400, f"status={r.status_code}")
    
    def test_delete_runtime(self):
        """Test deleting runtime entries"""
        print("\n=== DELETE RUNTIME TESTS ===")
        day_del = (datetime.now(timezone.utc) - timedelta(days=25)).date().isoformat()
        
        # Create entry
        r = requests.post(f"{BASE}/runtime-logs",
                         headers={"Authorization": f"Bearer {self.admin_token}"},
                         json={"line": "PC21", "date": day_del, "planned_hours": 12},
                         timeout=10)
        if r.status_code == 200:
            # Delete it
            r = requests.delete(f"{BASE}/line-runtime-logs?line=PC21&date={day_del}",
                               headers={"Authorization": f"Bearer {self.admin_token}"},
                               timeout=10)
            self.check("Delete runtime entry", r.status_code == 200, f"status={r.status_code}")
            
            # Verify it's gone (unlogged)
            r = requests.get(f"{BASE}/line-runtime-logs?line=PC21&date_from={day_del}&date_to={day_del}",
                            headers={"Authorization": f"Bearer {self.admin_token}"},
                            timeout=10)
            if r.status_code == 200:
                items = r.json().get('items', [])
                self.check("Day reverted to unlogged", len(items) == 0, f"items_count={len(items)}")
    
    def test_reliability_regression(self):
        """Test reliability metrics endpoint still works"""
        print("\n=== RELIABILITY REGRESSION TESTS ===")
        r = requests.get(f"{BASE}/reliability/metrics",
                        headers={"Authorization": f"Bearer {self.admin_token}"},
                        timeout=10)
        self.check("Reliability metrics endpoint", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            self.check("Returns list of metrics", isinstance(data, list))
            if data:
                sample = data[0]
                self.check("Metrics have machine_id", 'machine_id' in sample)
                self.check("Metrics have mtbf", 'mtbf' in sample)
    
    def cleanup(self):
        """Clean up test data"""
        print("\n=== CLEANUP ===")
        
        # Delete test breakdowns
        for bd_id in self.test_breakdowns:
            try:
                requests.delete(f"{BASE}/breakdowns/{bd_id}",
                              headers={"Authorization": f"Bearer {self.admin_token}"},
                              timeout=10)
                print(f"  🗑️  Deleted breakdown {bd_id}")
            except:
                pass
        
        # Delete test warnings
        for warn_id in self.test_warnings:
            try:
                requests.delete(f"{BASE}/warnings/{warn_id}",
                              headers={"Authorization": f"Bearer {self.admin_token}"},
                              timeout=10)
                print(f"  🗑️  Deleted warning {warn_id}")
            except:
                pass
        
        # Delete test runtime entries
        for entry in self.test_runtime_entries:
            try:
                requests.delete(f"{BASE}/line-runtime-logs?line={entry['line']}&date={entry['date']}",
                              headers={"Authorization": f"Bearer {self.admin_token}"},
                              timeout=10)
                print(f"  🗑️  Deleted runtime entry {entry['line']} {entry['date']}")
            except:
                pass
    
    def run_all_tests(self):
        """Run all tests"""
        print("=" * 80)
        print("RUNTIME MODULE COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        
        if not self.test_auth():
            print("\n❌ Authentication failed - cannot continue")
            return False
        
        if not self.get_test_machine():
            print("\n❌ Could not get test machine - some tests will be skipped")
        
        self.test_runtime_validation()
        self.test_planned_runtime_creation()
        self.test_derived_downtime()
        self.test_clamp_logic()
        self.test_warnings_exclusion()
        self.test_control_room_apis()
        self.test_analytics_apis()
        self.test_machine_detail()
        self.test_csv_import()
        self.test_delete_runtime()
        self.test_reliability_regression()
        
        self.cleanup()
        
        print("\n" + "=" * 80)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print(f"Success rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        print("=" * 80)
        
        return self.failed == 0

if __name__ == "__main__":
    tester = RuntimeModuleTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
