# plan.md

## 1) Objectives
- Deliver a production-ready, LAN-only **Factory Operations Platform** (Digital Twin Control Room + CMMS + Reliability/AWS + Predictive + Analytics + Spares + Admin) that is **machine-centric** in every workflow.
- Ship **non-empty** on first boot: seed full hierarchy, machine layout positions, templates/rules, **default users** (admin/admin123, tech/tech123, operator/operator123), and realistic starter spares.
- Provide real-time **timeline + notifications** (WebSocket) and scalable MongoDB data model (indexes/pagination) to hit performance targets.
- Ensure Control Room UX is **bounded and usable**:
  - **No zoom** / no zoom-to-infinity behavior.
  - A fixed/controlled canvas with **vertical scrolling** to view all machines.
- Ensure time references are unambiguous across operations:
  - Display **current actual wall-clock time** (date + HH:MM:SS ticking every second) so users can cross-reference Breakdown/WO timestamps.
- Deliver a coherent, app-wide **Cyberpunk HUD aesthetic** across *every* module and component.
- Provide **shift-lead command-center intelligence** at the point of use:
  - Availability + downtime **per Line** and **per Department/Process Group**, configurable window.
  - Keep plant-wide totals accessible but demoted.
- Enable **deep personalization and white-labeling**:
  - Per-user sidebar ordering and icon colors.
  - Admin-managed logo and brand accent color (hex) that re-themes the entire platform instantly.
- Standardize UI interaction language:
  - All buttons/icons/pills follow **outlined hairline border styling**.
  - Background theme is **pure black** (no deep-blue undertone), while maintaining readable contrast.

### Updated governance + workflow objectives (current)
- **Hierarchy is Line-first** (real world): **Line → Department → Process Group → Machine**.
  - Implemented via in-place DB migration keeping all transactional history.
  - All UI + Admin CRUD + seed logic reflect Line-first.

- **Work orders support Unassigned creation universally** (including public kiosk).
  - Kanban includes an **UNASSIGNED** column.
  - **Technicians can self-assign/claim** an unassigned WO.
  - **Admins do not “claim”**: admins explicitly **assign technicians via dropdown** in the WO popout.

- **Breakdowns support Unassigned creation**, but **closure is governed**:
  - A breakdown can **never be closed without a technician on record**.
  - If a technician closes an unassigned breakdown, the system records that technician automatically.
  - If an admin closes an unassigned breakdown, an **assigned technician must be selected** (otherwise 400).

- **Assignment-based action enforcement (P0, implemented)**:
  - For **Breakdowns** and **Work Orders**: only the **current assignee** (or an **Admin**) can perform **Start / Complete / Close** actions.
  - Other technicians must **claim** (if unassigned) or receive a **transfer** first; they cannot complete someone else’s assigned task.

- **Mandatory field validation (P0, implemented)**:
  - Breakdown repair cannot be completed/closed without **Action Taken**.
  - Corrective/Inspection/Predictive work orders cannot be completed without **Action Taken**.
  - PM checklist: any row marked **NOT OK** must include **Remarks** (OK rows optional).

- **PM Tasks support Unassigned creation universally** (same philosophy as WOs/Breakdowns).
  - Unassigned PM Tasks are visible to all technicians.
  - Technicians can claim unassigned PM Tasks.
  - Admins explicitly assign a technician.
  - Assignment syncs to any open PM-generated work order.

- **Admin-closure requirement is type-conditional (Work Orders)**:
  - Corrective + Inspection + AWS/Predictive WOs: technician can close directly.
  - Preventive (PM) + RCA WOs: technician completes → `PENDING_ADMIN_CLOSURE` → admin closes.

- **Task transfer & assignment**:
  - Assigned tasks (WO/PM/Breakdown) can be transferred.
  - Governance: current assignee or admin may transfer/reassign.
  - Unassigned tasks present both Claim for Me and Assign To…

- **RCA exception**:
  - RCA work orders are strictly locked to the technician who closed the triggering breakdown (> threshold downtime).
  - RCA tasks cannot be transferred, unassigned, or claimed (even by admins).

- **Immediate RCA completion flow**:
  - When a breakdown closes and downtime exceeds threshold, the 5-Why form opens immediately in-flow.
  - Dismissed popup leaves a locked pending RCA task (prevents data loss).

- **Correct action attribution + audit trail (P0, implemented)**:
  - Breakdown repairs now accurately record performer vs actor and log overrides.
  - Work orders now record started_by/completed_by and timeline attribution.

- **AWS / Predictive Maintenance Engine** is per-category:
  - Track separate health/life pools per machine for Mechanical / Electrical / PLC(Control).
  - Trigger threshold configurable via `predictive_trigger_pct`.
  - AWS-triggered WOs are `wo_type='Predictive'` with `aws_category`.

- **MTBF consistency objective (completed)**:
  - Machine-level MTBF in Analytics matches AWS MTBF exactly via reliability engine.
  - Response includes `mtbf_source`.

- **PM Compliance KPI correctness objective (completed; tolerance update implemented)**:
  - Compliance card never blank.
  - Scheduled/Completed scoped to slicer + hierarchy.
  - **On-time definition:** uses a ± tolerance window based on `reminder_offset_days`.

### Control Room KPI/range objectives
- Presets Shift/Day/Week + custom date range.
- Visual cleanup + live breakdown timer ribbon deep-linking.

### Navigation + productivity objectives
- Universal deep links: Work Orders, Breakdowns, Red Tags, PM Tasks.
- Live Event Feed deep links.
- Global “My Tasks” filter.
- Typeahead search on public report forms.
- Red Tags dispatch an Inspection WO (observation-only).

### UX + Security objectives (Phase AH — completed)
- Mobile-friendly login & public kiosk UX.
- “Warning” renamed to **Red Tag** (yellow theme retained; Tag icon used).

### Deployment objectives (Phase AH — completed)
- One-step deployment script `/app/deploy.sh` for Ubuntu 22.04/24.04.

### Phase AG objectives (completed)
- AWS strict category filtering + KPI recalculation.
- PM compliance tolerance window + historical backfill.
- Analytics Time Utilization donut.

### Phase AI objectives (completed)
- RCA rejection loop (admin reject with reason; returns to locked technician; timeline + notifications).
- Analytics Breakdown Type pie (Count vs Downtime toggle).
- Admin-only Technician Leaderboard + drill-down card.
- Mid-repair WO/Breakdown handoff with mandatory Pass-On Note; multi-handoff trail; MTTR/MTBF/AWS integrity preserved.

### Phase AJ objectives (COMPLETED)
- **Autonomous Maintenance (AM) Checklist module**:
  - Operator-driven, shift-based (A/B/C) routine checks, separate from PM.
  - Reuses PM structured checklist builder pattern (Sub-Component → multiple items).
  - Tri-state per item: OK / NOT OK / NA; remarks mandatory on NOT OK.
  - Public entry point on login/front page (no full login required) + full in-app module.
  - Machine Drawer integration (history with shift + date filters).
  - PDF export (blank + completed) matching PM tabular style.
  - Today’s per-shift coverage board (A/B/C done/pending).
  - AM→AWS leading-indicator integration explicitly **future scope only**.

---

## 2) Implementation Steps

### Phase 1 — Core “Operational Loop” POC
**Status:** ✅ COMPLETE

### Phase 2 — V1 App Development
**Status:** ✅ COMPLETE

### Phase 3 — Reliability/AWS + Predictive + Analytics
**Status:** ✅ COMPLETE

### Phase 4 — Spares/Inventory + Administration
**Status:** ✅ COMPLETE

### Phase AG — AWS strict category filter + PM tolerance + Time Utilization
**Status:** ✅ COMPLETE — VERIFIED (`/app/test_reports/iteration_14.json`)

### Phase AH — Mobile login + deploy script + Red Tag rename
**Status:** ✅ COMPLETE — VERIFIED (`/app/test_reports/iteration_15.json`)

### Phase AI — RCA Rejection + Breakdown-Type Pie + Technician Leaderboard + Mid-repair Handoff
**Status:** ✅ COMPLETE — VERIFIED (`/app/test_reports/iteration_16.json` + live UI verification)

---

### Phase AJ — Autonomous Maintenance (AM) Checklist Module (P0)
**Status:** ✅ COMPLETE — VERIFIED (`/app/test_reports/iteration_17.json`)

#### AJ0) Key decisions (confirmed)
- Templates are **per machine** (no machine-type concept). Provide **duplicate template to another machine**.
- Template management: **Admin-only**.
- AM module includes a **today shift-coverage board** (A/B/C done/pending) per machine.

#### AJ1) Backend — Router + schema
**New file:** `/app/backend/routers_am.py` (implemented, registered in `server.py`)

**Collections**
- `am_templates`
  - `id`, `machine_id`, `machine_name`, `line`, `department`, `process_group`
  - `template_name` (e.g. `AM — Fryer`)
  - `checklist_groups` (reuses PM structure): `[{ description: <sub-component>, items: [{ checked_for, parameter }] }]`
  - `frequency='per_shift'` (AM-only model)
  - `active`, `created_at`, `created_by`, `updated_at`, `updated_by`
- `am_submissions`
  - `id`, `template_id`, `template_name`, `machine_id`, `machine_name`, `line`, `department`, `process_group`
  - metadata (required): `name`, `gpid`, `shift ∈ {A,B,C}`
  - `email` (auto: user.email/username if logged in; else `'anonymous'`)
  - timing: `started_at` (client open time), `completed_at` (server), `duration_minutes` (derived)
  - `row_results`: `[{ description, checked_for, parameter, status: 'OK'|'NOT_OK'|'NA', remarks }]`
  - `not_ok_count`
  - `submitted_via`: `'authenticated'|'public_kiosk'`

**Validation**
- Reuses `_normalize_groups()` from `routers_maintenance.py`.
- Enforces: every template item must be answered; status ∈ OK/NOT_OK/NA; remarks mandatory for NOT_OK.

**Endpoints (implemented)**
- Templates (admin-only):
  - `GET /api/am-templates?machine_id=&active=`
  - `POST /api/am-templates`
  - `PUT /api/am-templates/{template_id}`
  - `DELETE /api/am-templates/{template_id}`
  - `POST /api/am-templates/{template_id}/duplicate` (copy to another machine)
- Submissions (authenticated):
  - `GET /api/am-submissions?machine_id=&template_id=&shift=&date_from=&date_to=&limit=`
  - `POST /api/am-submissions`
- Coverage board:
  - `GET /api/am-coverage?date=YYYY-MM-DD` → per-template shift status A/B/C
- PDF export (authenticated):
  - `GET /api/am-templates/{template_id}/pdf?submission_id=latest|<id>`
  - PDF mirrors PM sheet format, includes header + signature lines and tri-state checkboxes on blank.
- Public (no-auth kiosk):
  - `GET /api/public/am-context`
  - `GET /api/public/am-templates/{template_id}`
  - `POST /api/public/am-submissions`

**Timeline + notifications (implemented)**
- Always logs timeline event `am_submitted`.
- If NOT_OK items exist: creates warning notification with `notif_type='am_checklist'`.

#### AJ2) Frontend — Module + public entry + drawer integration
**New files:**
- `/app/frontend/src/components/AmChecklistForm.jsx`
  - `AmChecklistForm` (tri-state UI + remarks gating + started_at capture)
  - `AmSubmissionHistory` (filters + expandable detail + per-row PDF)
  - `downloadAmPdf()` helper
- `/app/frontend/src/pages/AMChecklistPublic.jsx` (public kiosk)
- `/app/frontend/src/pages/AMChecklists.jsx` (in-app module)

**Routing** (`/app/frontend/src/App.js`)
- Public route: `/am-checklist` (no Protected wrapper)
- In-app module: `/am-checklists` (Protected)

**Sidebar** (`/app/frontend/src/components/Layout.jsx`)
- Adds `AM Checklists` entry for roles `[admin, technician, operator]`.

**Login/front page** (`/app/frontend/src/pages/Login.jsx`)
- Adds a 3rd public button **AM Checklist** (green) linking to `/am-checklist`.

**Machine Drawer** (`/app/frontend/src/components/MachineDrawer.jsx`)
- Adds `AM Checklist` tab displaying submission history for that machine.

#### AJ3) Seed data + indexes
**File:** `/app/backend/seed.py`
- Adds idempotent demo template `AM — Fryer` (4 sub-components / 17 items).
- Adds indexes:
  - `am_templates.machine_id`
  - `am_submissions.machine_id + completed_at`
  - `am_submissions.template_id + completed_at`

**Demo data preserved**
- Template: `AM — Fryer`
- Submissions:
  - Ravi Operator (Shift A, 1 NOT OK)
  - Sita Operator (Shift B, all OK)

#### AJ4) Future scope note (explicitly not implemented)
- Use repeated NOT_OK patterns per item as a reliability/AWS leading indicator.
  - Candidate: same item NOT_OK ≥ N times within rolling window.
  - Not fed into AWS yet (by design).

#### AJ5) Testing + report
- **Test report:** `/app/test_reports/iteration_17.json`
  - Backend: 43/44 reported pass; the single “failure” was confirmed **false alarm** (notification query used wrong field; notifications exist as `notif_type='am_checklist'`).
  - Frontend: major flows verified (public kiosk + in-app + drawer). The “overlay” item is a test-script sequencing artifact; dialogs function normally.
- All testing artifacts were cleaned (extra templates/submissions removed; demo data preserved).

---

## 3) Next Actions

### Current (P0)
- No active P0 work items.

### P0 (Pending approval)
- Reliability data-quality guard: prevent breakdown start-times predating commissioned date.

### P1
- UI hint for `mtbf_source`.
- E2E regression test asserting AWS MTBF == machine analytics MTBF.

### Future (AM → AWS)
- Leading-indicator signal: repeated AM NOT_OK on same item affecting AWS health pools.

---

## 4) Success Criteria

### Existing (already satisfied)
- Governance rules, runtime model, AWS strict pool filtering, PM tolerance, Time Utilization, Red Tag rename, mobile login, deploy script.
- Phase AI features validated: RCA rejection, breakdown-type pie, technician leaderboard + card, mid-repair handoff.

### Phase AJ (now satisfied)
- ✅ AM Templates:
  - Admin can create/edit/delete AM templates per machine using the existing builder pattern.
  - Admin can duplicate an AM template to another machine.
- ✅ AM Submissions:
  - Operators submit checklists once per shift (A/B/C) with Name + GPID + Shift required.
  - Start/complete times are captured; duration derived.
  - Each item supports OK/NOT OK/NA; remarks are mandatory on NOT OK; all items must be answered.
- ✅ Access:
  - Public entry point exists on login/front page; no full login required.
  - In-app module is available via sidebar for all roles.
- ✅ Machine Drawer:
  - AM Checklist tab shows history for the machine with date + shift filters.
- ✅ PDF:
  - Blank template PDF and completed submission PDF match the PM tabular style and include header + signature lines.
- ✅ Integrity:
  - AM is separate from PM frequency models.
  - No AWS/reliability engine coupling yet (explicit future scope).
### Phase AK: Admin-scheduled AM tasks + AM Compliance KPI — Status: ✅ COMPLETED
- Verified via `/app/test_reports/iteration_18.json`: 10/10 backend + all frontend tests PASSED, zero bugs.
- Test data cleanup done: removed 3 test am_submissions + 3 SUBMITTED test am_tasks (2026-07-16). Fryer schedule + today's PENDING tasks kept (legit).

### Phase AL: AWS → eWACS-90 rename + custom module icon — Status: ✅ COMPLETED
- Label-only rename (zero logic changes): sidebar, page header, WO type labels/badges ("eWACS-90 / Predictive"), Analytics donut legend & footnote, PM predictive badge, WO modal badge, backend WO description + timeline alert title.
- Internal identifiers untouched: aws_* fields/collections, /api routes, /aws path, variable names.
- Icon: attached asset was an app screenshot (no SVG) → FALLBACK path taken: custom `EwacsIcon` SVG (radar sweep + plane silhouette + "90" badge) added to StatusBits.jsx, applied in sidebar + page header.

### Pending (user-approved backlog)
- P1: Breakdown start-time vs commissioned_at validation (MTBF poisoning guard).
- P1: mtbf_source UI hint.
- P2: AM "Not OK" recurrence → eWACS-90 degradation signal.

### Phase AM2: Historical breakdown import + MTBF guard — Status: ✅ COMPLETED
- P1 guard: breakdown start_time can no longer predate machine commissioned_at (create + edit paths, routers_maintenance.py).
- Imported 367/367 historical breakdowns from Pune Excel (2025-07-23 → 2026-07-13) as CLOSED records, reporter='excel-import', no WOs/notifications triggered.
- User-approved mappings: KKR Blending→Blending System, PC36 Optyx infeed vibratory→Optyx, created new machine "Trim & Pare Conveyor" on PC32.
- commissioned_at backdated on 89 machines (user-approved) so MTBF/Weibull stays valid; ticket numbers issued via real counter (dup collision found + fixed).
- Import tool kept at backend/import_breakdowns.py (dry-run by default).

### Phase AN: Technician roster + password editor + manual eWACS-90 WO — Status: ✅ COMPLETED
- Wiped 16 old technician accounts; created 9 from Excel "Attended By" (dattatray, nitin, ravindra, namdev, raju, premraj, bhausaheb, chandrakant, jalindar — default pw tech123). Also seeded in seed.py for fresh deployments.
- 349 imported breakdowns now linked to their real technicians (leaderboard-ready); stale open WOs unassigned back to claimable.
- Admin → Users: "Set Password" dialog per user (PUT /api/users/{id} with password).
- eWACS-90 page: +MEC/+ELE/+PLC buttons per row → POST /api/reliability/manual-wo (identical to auto-generated predictive WO, duplicate-guarded, admin/tech only).
