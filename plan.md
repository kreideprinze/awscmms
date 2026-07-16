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
  - **Breakdown repair** cannot be completed/closed without **Action Taken**.
  - **Corrective/Inspection/Predictive work orders** cannot be completed without **Action Taken**.
  - **PM checklist**: any row marked **NOT OK** must include **Remarks** (OK rows optional).

- **PM Tasks support Unassigned creation universally** (same philosophy as WOs/Breakdowns).
  - A PM Task can be created with no technician.
  - Unassigned PM Tasks are visible to all technicians (not hidden).
  - Technicians can **claim** unassigned PM Tasks.
  - Admins explicitly **assign** a technician (no admin claim).
  - Assignment syncs to any open PM-generated work order.

- **Admin-closure requirement is type-conditional (Work Orders)**:
  - **Corrective + Inspection + AWS/Predictive** WOs: technician can close directly (no admin approval).
  - **Preventive (PM) + RCA** WOs: technician completes → `PENDING_ADMIN_CLOSURE` → admin closes.

- **Task transfer & assignment**:
  - **Assigned tasks (WO/PM/Breakdown)** can be **transferred** to another technician.
  - **Transfer governance**: the **current assignee** *or* an **admin** may transfer/reassign.
  - **Unassigned tasks** present BOTH:
    - **Claim for Me** (tech self-claim)
    - **Assign To…** (direct assignment to another technician)

- **RCA exception**:
  - RCA work orders are **strictly locked** to the technician who closed the triggering breakdown (> threshold downtime).
  - RCA tasks **cannot** be transferred, unassigned, or claimed (even by admins).

- **Immediate RCA completion flow**:
  - When a breakdown is closed and downtime exceeds threshold (default 30 min), the **5-Why RCA form opens immediately in-flow**.
  - If the user dismisses the immediate RCA popup, the RCA **remains as a locked pending task** assigned to that technician (prevents data loss).

- **Correct action attribution + audit trail (P0, implemented)**:
  - Breakdown repairs now accurately record:
    - `assigned_to` = **repairing technician** (actual performer),
    - `closed_by` = **actor** who executed the close call,
    - timeline event describes **Repaired by X; closed by Y**, and records admin override reassignment when applicable.
  - Work orders now record `completed_by` / `started_by` for actor attribution; timeline event describes performer-vs-actor mismatch where applicable.

- **AWS / Predictive Maintenance Engine** is per-category:
  - Track separate health/life pools per machine for **Mechanical / Electrical / PLC(Control)**.
  - Trigger threshold is **admin-configurable** (default 80%) via `predictive_trigger_pct`.
  - AWS-triggered WOs are a distinct type: **AWS/Predictive** (`wo_type='Predictive'`, `aws_category` set).

- **MTBF consistency objective (completed)**:
  - **Machine-level MTBF in Analytics matches AWS MTBF exactly** (same reliability-engine metric), via `/api/analytics/kpis?level=machine` reading from `reliability_metrics.mtbf`.
  - Response includes `mtbf_source` (`reliability_engine` | `aggregate`) for transparency.

- **PM Compliance KPI correctness objective (completed; tolerance update implemented)**:
  - PM Compliance card must never render blank.
  - PM Compliance = **(Completed PM Tasks ÷ Scheduled PM Tasks) × 100**, scoped to the Analytics slicer and hierarchy.
  - Scheduled = completions within range + active pending tasks due by end-of-range cutoff (overdue backlog counts; future-dated does not).
  - Department/PG scopes resolve via machine-id sets because `pm_completions` does not store department/PG fields.
  - Card renders **0%** for 0 completed of N scheduled, and **N/A** when 0 scheduled.
  - **On-time definition (updated):** `pm_completions.on_time` uses a ± tolerance window based on `reminder_offset_days`.

### Control Room KPI/range objectives
- Control Room line KPIs support presets **Shift=8h, Day=24h, Week=168h** plus a **custom date range** slicer.
- Control Room visual cleanup:
  - Remove “flavor/narrative text” from line cards and plant totals; keep KPIs only.
  - Add a live red breakdown timer ribbon (HH:MM:SS ticking) on any line card with an active breakdown.
  - Clicking the live DOWN timer ribbon **jumps to the exact breakdown** (deep-link).

### Navigation + productivity objectives
- **Universal “jump to Work Order” deep linking**:
  - Clicking a WO reference anywhere opens the **exact Work Order popout/modal** rather than a generic list.
  - Contract: `?wo=<id>` plus a global `openWorkOrder(id)`

- **Universal “jump to Breakdown” deep linking**:
  - Clicking a line’s live DOWN timer ribbon opens `/breakdowns?bd=<breakdown_id>`.
  - Breakdowns page expands + highlights + scrolls to the referenced breakdown, then cleans the URL.

- **Universal “jump to Red Tag” deep linking** *(renamed from Warning)*:
  - Clicking a Red Tag reference opens `/breakdowns?warning=<warning_id>`.
  - Breakdowns switches to Red Tags view and opens the exact warning detail dialog.
  - **Note:** API/query parameter names remain unchanged for compatibility; UI labels change only.

- **Universal “jump to PM Task” deep linking**:
  - Clicking a PM task reference opens `/preventive-maintenance?task=<pm_task_id>`.
  - PM page highlights + scrolls to the referenced task and cleans the URL.

- **Live Event Feed deep-linking for all event types**:
  - Clicking any Live Event Feed entry deep-links to the *exact* referenced record:
    - Work Orders → WO popout
    - Breakdowns → Breakdown row expansion
    - Red Tags → Warning detail dialog
    - PM Tasks → PM row highlight
    - Fallback → Machine drawer

- **Global “My Tasks” filter** for technicians across: Breakdowns, Work Orders (Kanban), PMs.
- **Fuzzy/typeahead search** on Report Breakdown form dropdowns for Area/Line and Machine.
- **Red Tags are observation-only** and **always dispatch an Inspection WO** (no Corrective option).

### UX + Security objectives (Phase AH — completed)
- Mobile-friendly login & public kiosk UX (done)
- Terminology + icon consistency: “Warning” → “Red Tag” (done)

### Deployment objectives (Phase AH — completed)
- One-step deployment script `/app/deploy.sh` for Ubuntu 22.04/24.04 (done)

### Phase AG objectives (completed)
- AWS strict category filtering + KPI recalculation (done)
- PM compliance tolerance window + historical backfill endpoint (done)
- Analytics Time Utilization donut (done)

### Phase AI objectives (completed)
- **RCA rejection loop**: Admins can reject a submitted RCA with a reason; RCA reopens and returns to the same locked technician; rejection/resubmission is tracked in Timeline + notifications.
- **Analytics: Breakdown Type Pie**: Breakdown-type pie chart (Mechanical/Electrical/PLC) with toggle **Count vs Downtime-weighted**, respecting existing slicers.
- **Admin-only Technician Leaderboard**: Leaderboard with metric tabs + **Overall composite** toggle, and technician drill-down card.
- **Mid-repair Work Order handoff**: Transfer of **IN_PROGRESS** work orders/breakdowns with mandatory **Pass-On Note**, multiple handoffs, timeline/audit trail, MTTR/MTBF/AWS integrity preserved.

### NEW Objectives (Phase AJ — current)
- **Autonomous Maintenance (AM) Checklist module**:
  - Operator-driven, shift-based routine checks (distinct from PM).
  - Reuses the existing structured checklist builder pattern (Sub-Component → multiple items).
  - Per-item tri-state: **OK / NOT OK / NA**; remarks mandatory on **NOT OK**.
  - Public entry point on login/front page (no full login required) + full in-app module.
  - Machine Drawer integration (history with shift + date filters) + PDF export (blank + completed).
  - Show **today’s per-shift (A/B/C) coverage board**.
  - Reliability/AWS integration explicitly **future scope** only.

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

### Phase AI — RCA Rejection + Breakdown-Type Pie + Technician Leaderboard + Mid-repair Handoff (P0)
**Status:** ✅ COMPLETE — VERIFIED (`/app/test_reports/iteration_16.json` + live UI verification)

---

### Phase AJ — Autonomous Maintenance (AM) Checklist Module (P0)
**Status:** ⏳ NOT STARTED

#### AJ0) Key decisions (confirmed)
- Templates are **per machine** (no machine-type concept). Provide **duplicate template to another machine**.
- Template management: **Admin-only**.
- AM page includes a **today shift-coverage board** (A/B/C done/pending) per machine.

#### AJ1) Backend — New router + schema
**New file:** `/app/backend/routers_am.py`

**Collections**
- `am_templates`
  - `id`, `machine_id`, `machine_name`, `line`, `department`, `process_group`
  - `template_name` (e.g. `AM — Fryer`)
  - `checklist_groups` (REUSE PM structure): `[{ description: <sub-component>, items: [{ checked_for: <check item>, parameter: <optional> }] }]`
  - `active`, `created_at`, `created_by`, `updated_at`, `updated_by`
- `am_submissions`
  - `id`, `template_id`, `machine_id`, `machine_name`, `line`, `department`, `process_group`
  - metadata (required): `name`, `gpid`, `shift` in `{'A','B','C'}`
  - `email` (auto from user if logged in else `'anonymous'`)
  - timing: `started_at` (client-sent when opened), `completed_at` (server now), `duration_minutes` (derived)
  - `row_results`: `[{ description, checked_for, parameter, status: 'OK'|'NOT_OK'|'NA', remarks }]`
  - `not_ok_count`
  - `submitted_via`: `'authenticated'|'public_kiosk'`

**Shared validation reuse**
- Reuse `_normalize_groups()` from `routers_maintenance.py` to validate checklist group structure.
- Add `am_rows(template, submission=None)` helper (AM needs 3-state mapping instead of PM’s 2-state).

**Endpoints**
- Templates (admin-only):
  - `GET /api/am-templates?machine_id=&line=&active=`
  - `POST /api/am-templates`
  - `PUT /api/am-templates/{template_id}`
  - `DELETE /api/am-templates/{template_id}`
  - `POST /api/am-templates/{template_id}/duplicate` with `{target_machine_id}`
- Submissions (authenticated):
  - `GET /api/am-submissions?machine_id=&template_id=&date_from=&date_to=&shift=&limit=`
  - `POST /api/am-submissions` (validates tri-state + remarks on NOT_OK)
- Coverage board:
  - `GET /api/am-coverage?date=YYYY-MM-DD&line=&department=`
    - returns per-machine `A/B/C` done status + last submission time
- PDF export (authenticated):
  - `GET /api/am-templates/{template_id}/pdf?submission_id=...`
    - ReportLab, mirrored from PM PDF:
      - Header fields: Machine / Line / Shift / Date
      - Table columns: Sub-Component / Check Item / Parameter / Status / Remarks
      - Status boxes: `☐ OK ☐ NOT OK ☐ NA` for blank sheets
      - Done-by line includes Name + GPID + signature

**Public (no-auth) entry points**
- `GET /api/public/am-context` (machines + minimal template list)
- `GET /api/public/am-templates/{template_id}` (template detail)
- `POST /api/public/am-submissions`
  - Must require Name/GPID/Shift.
  - Email defaults to `'anonymous'`.

**Timeline + notifications**
- Always create `timeline_event` on submission: `am_submitted` with machine context.
- If any NOT_OK items:
  - create a **warning** severity notification for admins/technicians (or at least admins) with a summary count.

**Server registration**
- Register `routers_am.router` in `/app/backend/server.py`.

#### AJ2) Frontend — New pages/components

**Routing** (`/app/frontend/src/App.js`)
- Public route:
  - `Route /am-checklist` (no Protected wrapper)
- In-app module:
  - `Route /am-checklists` inside Protected (all roles)

**Sidebar navigation** (`/app/frontend/src/components/Layout.jsx`)
- Add `AM Checklists` entry for roles `[admin, technician, operator]`.

**Front/Login page public entry point** (`/app/frontend/src/pages/Login.jsx`)
- Add a new **AM Checklist** button alongside Breakdown and Red Tag.
  - Opens `/am-checklist`.

**Reusable fill form**
- Create `AmChecklistForm` component:
  - Template selector + machine info
  - Required: Name, GPID, Shift (A/B/C)
  - Auto-capture `started_at` at open
  - Per item tri-state control: OK / NOT OK / NA
  - Remarks field per row, mandatory when NOT OK
  - Submit writes to authenticated or public endpoint based on auth state

**Public page** (`/app/frontend/src/pages/AMChecklistPublic.jsx`)
- Fetch `/api/public/am-context`
- Operator picks machine → template (if multiple) → completes form → submit

**In-app module page** (`/app/frontend/src/pages/AMChecklists.jsx`)
- Today per-shift coverage board:
  - shows machines in scope and A/B/C status
- Admin template management:
  - Create/Edit templates using the existing `ChecklistBuilder` UI (reused)
  - Duplicate-to-another-machine action
  - Download blank PDF
- Submission history:
  - Filters: date_from/date_to, shift, machine
  - Download completed PDF

**Machine Drawer integration** (`/app/frontend/src/components/MachineDrawer.jsx`)
- Add new tab: `AM Checklist`
  - History list for that machine, filterable by date range + shift
  - PDF download per submission

#### AJ3) Seed data
**File:** `/app/backend/seed.py`
- Add 1 representative **AM template** for an existing machine (Fryer-style example), with multiple sub-components and items.
- Ensure seeding is idempotent (don’t duplicate on re-run).

#### AJ4) Future scope note (explicitly not implemented)
- Repeated NOT_OK patterns per item as a reliability/AWS leading indicator.
  - Document candidate signal: “same item NOT_OK ≥ N times within rolling window”
  - Do not feed into AWS yet.

#### AJ5) Testing + report
- Create `/app/test_reports/iteration_17.json`
- Use testing agent **both**:
  - Backend: template CRUD (admin-only), public submit, tri-state + remarks validation, coverage board, PDF endpoint.
  - Frontend: public flow from login → /am-checklist submit; in-app module boards; drawer tab filters; PDF download.

---

## 3) Next Actions

### Current (P0)
- Implement Phase AJ (AJ1–AJ5).

### P0 (Pending approval)
- Reliability data-quality guard: prevent breakdown start-times predating commissioned date.

### P1
- UI hint for `mtbf_source`.
- E2E regression test asserting AWS MTBF == machine analytics MTBF.

---

## 4) Success Criteria

### Existing (already satisfied)
- Governance rules, runtime model, AWS strict pool filtering, PM tolerance, Time Utilization, Red Tag rename, mobile login, deploy script.
- Phase AI features validated: RCA rejection, breakdown-type pie, technician leaderboard + card, mid-repair handoff.

### Phase AJ (NEW)
- ✅ AM Templates:
  - Admin can create/edit/delete AM templates per machine using the existing builder pattern.
  - Admin can duplicate an AM template to another machine.
- ✅ AM Submissions:
  - Operators submit checklists once per shift (A/B/C) with Name + GPID + Shift required.
  - Start/complete times are captured; duration derived.
  - Each item supports OK/NOT OK/NA; remarks are mandatory on NOT OK.
- ✅ Access:
  - Public entry point exists on login/front page; no full login required.
  - In-app module is available via sidebar for all roles.
- ✅ Machine Drawer:
  - New AM Checklist tab shows history for the machine with date + shift filters.
- ✅ PDF:
  - Blank template PDF and completed submission PDF match the PM tabular style and include header + signature lines.
- ✅ Integrity:
  - AM is separate from PM frequency models.
  - No AWS/reliability engine coupling yet (explicit future scope).