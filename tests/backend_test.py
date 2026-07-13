#!/usr/bin/env python3
"""
Backend API tests for Task Transfer & Immediate RCA Flow feature.
Tests all endpoints for Work Orders, PM Tasks, Breakdowns, and RCA governance.
"""
import requests
import json
import sys
from datetime import datetime, timedelta, timezone

BASE_URL = "https://content-extractor-75.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.admin_token = None
        self.tech_token = None
        self.machine_id = None
        
    def login(self, username, password):
        """Login and return auth headers"""
        try:
            r = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
            r.raise_for_status()
            token = r.json().get('token')
            if not token:
                print(f"❌ Login failed for {username}: no token in response")
                return None
            return {"Authorization": f"Bearer {token}"}
        except Exception as e:
            print(f"❌ Login failed for {username}: {e}")
            return None
    
    def test(self, name, func):
        """Run a test function"""
        self.tests_run += 1
        try:
            func()
            self.tests_passed += 1
            print(f"✅ {name}")
            return True
        except AssertionError as e:
            self.tests_failed += 1
            print(f"❌ {name}: {e}")
            return False
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ {name}: Unexpected error: {e}")
            return False
    
    def run_all_tests(self):
        print("=" * 80)
        print("BACKEND API TESTS - Task Transfer & Immediate RCA Flow")
        print("=" * 80)
        
        # Setup: Login
        print("\n🔐 Authentication Tests")
        self.test("Login as admin/admin123", lambda: self._test_login_admin())
        self.test("Login as tech/tech123", lambda: self._test_login_tech())
        
        if not self.admin_token or not self.tech_token:
            print("\n❌ Cannot proceed without valid tokens")
            return
        
        # Get a machine for testing
        self._setup_machine()
        
        # Work Order Tests
        print("\n📋 Work Order Tests")
        self.test("Create unassigned WO", lambda: self._test_wo_create_unassigned())
        self.test("Tech claims unassigned WO", lambda: self._test_wo_claim())
        self.test("Tech transfers WO to another tech", lambda: self._test_wo_transfer_by_holder())
        self.test("Admin transfers WO", lambda: self._test_wo_transfer_by_admin())
        self.test("Cannot claim already-assigned WO", lambda: self._test_wo_claim_assigned_fails())
        self.test("Cannot assign to same current assignee", lambda: self._test_wo_assign_same_fails())
        
        # PM Task Tests
        print("\n🔧 PM Task Tests")
        self.test("Tech self-claims unassigned PM", lambda: self._test_pm_claim())
        self.test("Admin transfers PM task", lambda: self._test_pm_transfer_by_admin())
        self.test("Cannot claim already-assigned PM", lambda: self._test_pm_claim_assigned_fails())
        
        # Breakdown Tests
        print("\n⚠️  Breakdown Tests")
        self.test("Create unassigned breakdown", lambda: self._test_bd_create_unassigned())
        self.test("Tech claims unassigned breakdown", lambda: self._test_bd_claim())
        self.test("Tech transfers breakdown", lambda: self._test_bd_transfer())
        self.test("Admin transfers breakdown", lambda: self._test_bd_admin_transfer())
        
        # Immediate RCA Tests
        print("\n🔍 Immediate RCA Flow Tests")
        self.test("Close breakdown with >30 min downtime triggers RCA", lambda: self._test_rca_trigger())
        self.test("RCA task is locked - cannot transfer", lambda: self._test_rca_lock_transfer())
        self.test("RCA task is locked - cannot claim", lambda: self._test_rca_lock_claim())
        
        # Regression Tests
        print("\n🔄 Regression Tests")
        self.test("Close breakdown with <30 min downtime - no RCA", lambda: self._test_no_rca_short_downtime())
        
        # Summary
        print("\n" + "=" * 80)
        print(f"📊 TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        return self.tests_failed == 0
    
    def _test_login_admin(self):
        self.admin_token = self.login("admin", "admin123")
        assert self.admin_token is not None, "Admin login failed"
        assert "Authorization" in self.admin_token, "No Authorization header"
    
    def _test_login_tech(self):
        self.tech_token = self.login("tech", "tech123")
        assert self.tech_token is not None, "Tech login failed"
        assert "Authorization" in self.tech_token, "No Authorization header"
    
    def _setup_machine(self):
        """Get a machine for testing"""
        r = requests.get(f"{BASE_URL}/machines", headers=self.admin_token)
        machines = r.json()
        if machines:
            self.machine_id = machines[0]["id"]
            print(f"\n🏭 Using machine: {machines[0]['name']} ({self.machine_id})")
    
    def _test_wo_create_unassigned(self):
        r = requests.post(f"{BASE_URL}/work-orders", headers=self.admin_token, json={
            "machine_id": self.machine_id,
            "title": "Test Transfer WO",
            "wo_type": "Corrective",
            "priority": "medium"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        wo = r.json()
        self.test_wo_id = wo["id"]
        assert wo.get("assigned_to") is None, "WO should be unassigned"
        assert wo.get("status") == "OPEN", "Unassigned WO should have OPEN status"
    
    def _test_wo_claim(self):
        r = requests.put(f"{BASE_URL}/work-orders/{self.test_wo_id}", headers=self.tech_token, json={"action": "claim"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == "tech", "WO should be assigned to tech"
        assert result.get("status") == "ASSIGNED", "Status should be ASSIGNED"
    
    def _test_wo_transfer_by_holder(self):
        # Get list of technicians
        r = requests.get(f"{BASE_URL}/users", headers=self.admin_token)
        users = r.json()
        other_tech = next((u["username"] for u in users if u.get("role") == "technician" and u["username"] != "tech"), None)
        assert other_tech, "Need another technician for transfer test"
        
        r = requests.put(f"{BASE_URL}/work-orders/{self.test_wo_id}", headers=self.tech_token, json={
            "action": "assign",
            "assigned_to": other_tech
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == other_tech, f"WO should be assigned to {other_tech}"
        self.other_tech = other_tech
    
    def _test_wo_transfer_by_admin(self):
        r = requests.put(f"{BASE_URL}/work-orders/{self.test_wo_id}", headers=self.admin_token, json={
            "action": "assign",
            "assigned_to": "tech"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == "tech", "WO should be assigned back to tech"
    
    def _test_wo_claim_assigned_fails(self):
        # WO is already assigned to tech, try to claim again
        r = requests.put(f"{BASE_URL}/work-orders/{self.test_wo_id}", headers=self.tech_token, json={"action": "claim"})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        assert "already assigned" in r.json().get("detail", "").lower(), "Should indicate already assigned"
    
    def _test_wo_assign_same_fails(self):
        # Try to assign to the same person (tech)
        r = requests.put(f"{BASE_URL}/work-orders/{self.test_wo_id}", headers=self.admin_token, json={
            "action": "assign",
            "assigned_to": "tech"
        })
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        assert "already assigned" in r.json().get("detail", "").lower(), "Should indicate already assigned to same person"
    
    def _test_pm_claim(self):
        # Get or create an unassigned PM task
        r = requests.get(f"{BASE_URL}/pm-tasks", headers=self.admin_token)
        pms = r.json().get("items", [])
        unassigned_pm = next((p for p in pms if not p.get("assigned_to")), None)
        
        if not unassigned_pm:
            # Create one
            r = requests.post(f"{BASE_URL}/pm-tasks", headers=self.admin_token, json={
                "machine_id": self.machine_id,
                "task_name": "Test PM Transfer",
                "frequency": "monthly",
                "priority": "medium",
                "checklist_groups": [{"description": "Test", "items": [{"checked_for": "Check", "parameter": ""}]}]
            })
            assert r.status_code == 200, f"Failed to create PM: {r.text}"
            unassigned_pm = r.json()
        
        self.test_pm_id = unassigned_pm["id"]
        
        # Tech claims it
        r = requests.post(f"{BASE_URL}/pm-tasks/{self.test_pm_id}/claim", headers=self.tech_token, json={})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == "tech", "PM should be assigned to tech"
    
    def _test_pm_transfer_by_admin(self):
        r = requests.post(f"{BASE_URL}/pm-tasks/{self.test_pm_id}/claim", headers=self.admin_token, json={
            "assigned_to": self.other_tech
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == self.other_tech, f"PM should be assigned to {self.other_tech}"
    
    def _test_pm_claim_assigned_fails(self):
        # PM is already assigned, try to claim with empty body
        r = requests.post(f"{BASE_URL}/pm-tasks/{self.test_pm_id}/claim", headers=self.tech_token, json={})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        assert "already assigned" in r.json().get("detail", "").lower(), "Should indicate already assigned"
    
    def _test_bd_create_unassigned(self):
        r = requests.post(f"{BASE_URL}/breakdowns", headers=self.admin_token, json={
            "machine_id": self.machine_id,
            "description": "Test breakdown for transfer",
            "failure_mode": "Mechanical",
            "breakdown_type": "MECHANICAL"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        bd = r.json()
        self.test_bd_id = bd["id"]
        assert bd.get("assigned_to") is None, "Breakdown should be unassigned"
        assert bd.get("status") == "OPEN", "Unassigned breakdown should have OPEN status"
    
    def _test_bd_claim(self):
        r = requests.put(f"{BASE_URL}/breakdowns/{self.test_bd_id}", headers=self.tech_token, json={"action": "claim"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == "tech", "Breakdown should be assigned to tech"
    
    def _test_bd_transfer(self):
        r = requests.put(f"{BASE_URL}/breakdowns/{self.test_bd_id}", headers=self.tech_token, json={
            "action": "assign",
            "assigned_to": self.other_tech
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == self.other_tech, f"Breakdown should be assigned to {self.other_tech}"
    
    def _test_bd_admin_transfer(self):
        r = requests.put(f"{BASE_URL}/breakdowns/{self.test_bd_id}", headers=self.admin_token, json={
            "action": "assign",
            "assigned_to": "tech"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("assigned_to") == "tech", "Breakdown should be assigned back to tech"
    
    def _test_rca_trigger(self):
        # Create a new breakdown for RCA testing
        r = requests.post(f"{BASE_URL}/breakdowns", headers=self.admin_token, json={
            "machine_id": self.machine_id,
            "description": "Test RCA trigger breakdown",
            "failure_mode": "Mechanical",
            "breakdown_type": "MECHANICAL"
        })
        bd = r.json()
        rca_bd_id = bd["id"]
        
        # Claim it as tech
        r = requests.put(f"{BASE_URL}/breakdowns/{rca_bd_id}", headers=self.tech_token, json={"action": "claim"})
        assert r.status_code == 200, "Failed to claim breakdown"
        
        # Close with >30 min downtime
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=45)
        r = requests.put(f"{BASE_URL}/breakdowns/{rca_bd_id}", headers=self.tech_token, json={
            "action": "close",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "action_taken": "Test repair action"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("rca_required") == True, "RCA should be required for >30 min downtime"
        assert result.get("rca_task_id") is not None, "RCA task ID should be returned"
        assert result.get("rca_assigned_to") == "tech", "RCA should be assigned to closing tech"
        assert result.get("downtime_minutes") >= 30, "Downtime should be >= 30 minutes"
        
        self.rca_wo_id = result.get("rca_task_id")
    
    def _test_rca_lock_transfer(self):
        # Try to transfer RCA as admin - should fail
        r = requests.put(f"{BASE_URL}/work-orders/{self.rca_wo_id}", headers=self.admin_token, json={
            "action": "assign",
            "assigned_to": self.other_tech
        })
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        detail = r.json().get("detail", "")
        assert "locked" in detail.lower() or "cannot" in detail.lower(), "Should indicate RCA is locked"
    
    def _test_rca_lock_claim(self):
        # Try to claim RCA - should fail
        r = requests.put(f"{BASE_URL}/work-orders/{self.rca_wo_id}", headers=self.tech_token, json={"action": "claim"})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        detail = r.json().get("detail", "")
        assert "locked" in detail.lower() or "cannot" in detail.lower(), "Should indicate RCA is locked"
    
    def _test_no_rca_short_downtime(self):
        # Create a breakdown and close with <30 min downtime
        r = requests.post(f"{BASE_URL}/breakdowns", headers=self.admin_token, json={
            "machine_id": self.machine_id,
            "description": "Short downtime breakdown",
            "failure_mode": "Mechanical",
            "breakdown_type": "MECHANICAL"
        })
        bd = r.json()
        short_bd_id = bd["id"]
        
        # Claim and close with 15 min downtime
        r = requests.put(f"{BASE_URL}/breakdowns/{short_bd_id}", headers=self.tech_token, json={"action": "claim"})
        
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=15)
        r = requests.put(f"{BASE_URL}/breakdowns/{short_bd_id}", headers=self.tech_token, json={
            "action": "close",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "action_taken": "Quick fix"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()
        assert result.get("rca_required") == False, "RCA should NOT be required for <30 min downtime"
        assert result.get("rca_task_id") is None, "No RCA task should be created"

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
