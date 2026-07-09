"""Test new features: line KPIs, UI prefs, branding.
Tests:
1. Line KPIs endpoint with different window sizes (8h, 24h, 168h)
2. Invalid hours parameter rejection
3. UI preferences GET/PUT per user with validation
4. Branding accent color validation
5. Logo upload/delete with size/type validation
"""
import asyncio
import base64
import json
import sys

import httpx

BASE = 'https://content-extractor-75.preview.emergentagent.com/api'

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    status = 'PASS' if ok else 'FAIL'
    print(f"{status}: {name} {detail}")


async def main():
    async with httpx.AsyncClient(timeout=30) as http:
        # 1. Login as admin
        r = await http.post(f'{BASE}/auth/login', json={'username': 'admin', 'password': 'admin123'})
        check('admin login', r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"Login failed: {r.text}")
            sys.exit(1)
        admin_token = r.json()['token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}

        # 2. Login as tech user
        r = await http.post(f'{BASE}/auth/login', json={'username': 'tech', 'password': 'tech123'})
        check('tech login', r.status_code == 200)
        tech_token = r.json()['token']
        tech_headers = {'Authorization': f'Bearer {tech_token}'}

        # ---- LINE KPIs TESTS ----
        print("\n=== LINE KPI TESTS ===")
        
        # Test default (24h)
        r = await http.get(f'{BASE}/control-room/line-kpis', headers=admin_headers)
        check('line-kpis default (24h)', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            data = r.json()
            check('line-kpis has window_hours', 'window_hours' in data, str(data.get('window_hours')))
            check('line-kpis has lines array', 'lines' in data and isinstance(data['lines'], list))
            if data.get('lines'):
                line = data['lines'][0]
                required = ['line', 'department', 'machines', 'availability', 'downtime_minutes', 'sections']
                for field in required:
                    check(f'line-kpis line has {field}', field in line, str(line.keys()))
                if line.get('sections'):
                    section = line['sections'][0]
                    sec_required = ['process_group', 'machines', 'availability', 'downtime_minutes']
                    for field in sec_required:
                        check(f'line-kpis section has {field}', field in section, str(section.keys()))

        # Test 8h window
        r = await http.get(f'{BASE}/control-room/line-kpis?hours=8', headers=admin_headers)
        check('line-kpis 8h window', r.status_code == 200 and r.json().get('window_hours') == 8)

        # Test 168h (week) window
        r = await http.get(f'{BASE}/control-room/line-kpis?hours=168', headers=admin_headers)
        check('line-kpis 168h window', r.status_code == 200 and r.json().get('window_hours') == 168)

        # Test invalid hours (0)
        r = await http.get(f'{BASE}/control-room/line-kpis?hours=0', headers=admin_headers)
        check('line-kpis rejects hours=0', r.status_code == 422, str(r.status_code))

        # Test invalid hours (200)
        r = await http.get(f'{BASE}/control-room/line-kpis?hours=200', headers=admin_headers)
        check('line-kpis rejects hours=200', r.status_code == 422, str(r.status_code))

        # ---- UI PREFERENCES TESTS ----
        print("\n=== UI PREFERENCES TESTS ===")
        
        # Get admin's current prefs (save for restoration)
        r = await http.get(f'{BASE}/users/me/ui-prefs', headers=admin_headers)
        check('get ui-prefs admin', r.status_code == 200)
        admin_original_prefs = r.json() if r.status_code == 200 else {}
        print(f"Admin original prefs: {admin_original_prefs}")

        # Get tech's current prefs
        r = await http.get(f'{BASE}/users/me/ui-prefs', headers=tech_headers)
        check('get ui-prefs tech', r.status_code == 200)
        tech_original_prefs = r.json() if r.status_code == 200 else {}

        # Test PUT sidebar_order for admin
        test_order = ['analytics', 'control-room', 'breakdowns', 'work-orders']
        r = await http.put(f'{BASE}/users/me/ui-prefs', headers=admin_headers, json={'sidebar_order': test_order})
        check('put ui-prefs sidebar_order', r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            check('sidebar_order persisted', data.get('sidebar_order') == test_order, str(data.get('sidebar_order')))

        # Test PUT icon_colors for admin
        test_colors = {'control-room': '#ff0000', 'breakdowns': '#00ff00'}
        r = await http.put(f'{BASE}/users/me/ui-prefs', headers=admin_headers, json={'icon_colors': test_colors})
        check('put ui-prefs icon_colors', r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            check('icon_colors persisted', data.get('icon_colors', {}).get('control-room') == '#ff0000')

        # Test invalid hex color rejection
        r = await http.put(f'{BASE}/users/me/ui-prefs', headers=admin_headers, json={'icon_colors': {'control-room': 'red'}})
        check('ui-prefs rejects invalid hex', r.status_code == 400, str(r.status_code))

        # Test invalid hex color #12345 (5 chars)
        r = await http.put(f'{BASE}/users/me/ui-prefs', headers=admin_headers, json={'icon_colors': {'control-room': '#12345'}})
        check('ui-prefs rejects short hex', r.status_code == 400, str(r.status_code))

        # Test duplicate module keys rejection
        r = await http.put(f'{BASE}/users/me/ui-prefs', headers=admin_headers, json={'sidebar_order': ['control-room', 'breakdowns', 'control-room']})
        check('ui-prefs rejects duplicate keys', r.status_code == 400, str(r.status_code))

        # Test tech user has independent prefs
        r = await http.put(f'{BASE}/users/me/ui-prefs', headers=tech_headers, json={'sidebar_order': ['pm', 'work-orders', 'breakdowns']})
        check('tech ui-prefs independent', r.status_code == 200)
        
        # Verify admin prefs unchanged
        r = await http.get(f'{BASE}/users/me/ui-prefs', headers=admin_headers)
        if r.status_code == 200:
            admin_prefs = r.json()
            check('admin prefs unchanged by tech', admin_prefs.get('sidebar_order') == test_order)

        # Restore admin's original prefs
        if admin_original_prefs:
            r = await http.put(f'{BASE}/users/me/ui-prefs', headers=admin_headers, json=admin_original_prefs)
            check('restore admin original prefs', r.status_code == 200)
            print(f"Restored admin prefs to: {admin_original_prefs}")

        # ---- BRANDING TESTS ----
        print("\n=== BRANDING TESTS ===")
        
        # Get current branding (save for restoration)
        r = await http.get(f'{BASE}/branding')
        check('get branding', r.status_code == 200)
        original_branding = r.json() if r.status_code == 200 else {}
        print(f"Original branding: {original_branding}")

        # Test PUT valid accent color
        r = await http.put(f'{BASE}/branding', headers=admin_headers, json={'accent': '#ff9e1c'})
        check('put branding valid accent', r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            check('accent persisted', data.get('accent') == '#ff9e1c', str(data.get('accent')))

        # Test invalid accent color 'red'
        r = await http.put(f'{BASE}/branding', headers=admin_headers, json={'accent': 'red'})
        check('branding rejects invalid accent', r.status_code == 400, str(r.status_code))

        # Test invalid accent color #12345
        r = await http.put(f'{BASE}/branding', headers=admin_headers, json={'accent': '#12345'})
        check('branding rejects short hex', r.status_code == 400, str(r.status_code))

        # Test logo upload - create small PNG
        png_data = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        )
        files = {'file': ('test.png', png_data, 'image/png')}
        r = await http.post(f'{BASE}/branding/logo', headers=admin_headers, files=files)
        check('logo upload success', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            data = r.json()
            check('logo returns data URI', 'logo_data' in data and data['logo_data'].startswith('data:image/'))

        # Test oversized file rejection (create 600KB fake file)
        large_data = b'x' * (600 * 1024)
        files = {'file': ('large.png', large_data, 'image/png')}
        r = await http.post(f'{BASE}/branding/logo', headers=admin_headers, files=files)
        check('logo rejects oversized', r.status_code == 400, str(r.status_code))

        # Test invalid file type rejection
        files = {'file': ('test.txt', b'hello', 'text/plain')}
        r = await http.post(f'{BASE}/branding/logo', headers=admin_headers, files=files)
        check('logo rejects non-image', r.status_code == 400, str(r.status_code))

        # Test DELETE logo
        r = await http.delete(f'{BASE}/branding/logo', headers=admin_headers)
        check('logo delete success', r.status_code == 200)

        # Verify logo removed
        r = await http.get(f'{BASE}/branding')
        if r.status_code == 200:
            data = r.json()
            check('logo removed from branding', 'logo_data' not in data or not data.get('logo_data'))

        # Restore original branding accent to #00fff5
        r = await http.put(f'{BASE}/branding', headers=admin_headers, json={'accent': '#00fff5'})
        check('restore accent to #00fff5', r.status_code == 200)
        print("Restored branding accent to #00fff5")

    # Summary
    failed = [r for r in results if not r[1]]
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(results)}  PASS: {len(results)-len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("\nFAILED TESTS:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
    print('='*60)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    asyncio.run(main())
