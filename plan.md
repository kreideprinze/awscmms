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
  - Availability + downtime **per Line** and **per Section/Process Group**, configurable window.
  - Keep plant-wide totals accessible but demoted.
- Enable **deep personalization and white-labeling**:
  - Per-user sidebar ordering and icon colors.
  - Admin-managed logo and brand accent color (hex) that re-themes the entire platform instantly.
- Standardize UI interaction language:
  - All buttons/icons/pills follow **outlined hairline border styling**.
  - Background theme is **pure black** (no deep-blue undertone), while maintaining readable contrast.
- Ensure maintenance execution is **audit-ready and printable**:
  - PM execution is driven by **structured checklists** (component → sub-item rows) with per-row OK/NOT OK + per-row remarks.
  - Every PM task supports **PDF export** for blank templates and completed instances, formatted like the real checklist sheet.
- Remove friction for shop-floor reporting:
  - Provide **public kiosk reporting** entry points (no login required) capturing Reporter Name and flagging submissions as public.
- Ensure reliability analytics are **verifiable with seeded data**:
  - Provide deterministic, labeled demo datasets to validate **Weibull** fit outputs (beta/eta/mean life/B10) and AWS UI behavior.
- **Differentiate downtime vs non-downtime events** clearly:
  - Add **Warning** observations that **do not affect** Availability/MTBF/MTTR but **do auto-dispatch** a WO and visually appear yellow across the HUD.
- Ensure execution governance in CMMS:
  - Work order completion requires **Admin closure** before final CLOSED — applies to **Corrective AND PM-generated Work Orders**.
- Improve Kanban operational UX:
  - Kanban cards open a **detail popout modal** for fast inspection and quick edits.
  - Work Orders support **editable Start/End times** (admin + assigned technician) with validation and audit trail.
- **NEW (Phase L)**: Enforce standardized **Root Cause Analysis (5-Why)** governance:
  - Auto-trigger RCA when downtime/duration exceeds threshold (default 30 min; admin-configurable).
  - RCA requires structured 5-Why submission and cannot complete/close without it.
  - RCA records link bidirectionally to originating Breakdown/Work Order and appear in timeline.
- **NEW (Phase L)**: Provide **Admin-only Technician Analytics** in Plant Analytics:
  - Enforced by backend role permissions (403 for non-admin), not just UI hiding.
- **NEW (Phase L)**: Runtime is logged **per line** (not per machine) to compute availability correctly:
  - Line-level runtime entry; machines inherit line runtime for reliability computations.
- **NEW (Phase L)**: AWS supports Mechanical/Electrical/PLC category sorting/filtering:
  - Category chips + per-machine failure category counts + dominant category.
- Maintain **UI excellence without logic risk**:
  - Allow iterative UI polish improvements **without changing backend/frontend business logic**.

---

## 2) Implementation Steps

### Phase 1 — Core “Operational Loop” POC (Isolation) (WebSocket + eventing + derived machine state)
> Core = if this breaks, the system isn’t “live”: machine state aggregation + timeline/notifications + Digital Twin can’t be trusted.

**Status:** ✅ COMPLETE

---

### Phase 2 — V1 App Development (MVP, end-to-end usable)
**Status:** ✅ COMPLETE

---

### Phase 3 — Reliability/AWS + Predictive + Analytics (multi-level)
**Status:** ✅ COMPLETE

---

### Phase 4 — Spares/Inventory + Administration hardening + scale readiness
**Status:** ✅ COMPLETE

---

### Phase E — Control Room Ribbon + Customization + Theming
> This phase turns the Control Room into a true shift-lead “command center”: availability + downtime at the exact hierarchy level people manage (line/section), plus personalization (sidebar order/colors) and proper white-label branding.

#### E1) Control Room KPI Ribbon v2 (Line/Section Availability + Downtime) (P0)
**Status:** ✅ COMPLETE

#### E2) Sidebar Icon Customization (Per-user) (P0)
**Status:** ✅ COMPLETE

#### E3) Custom Branding: Admin Uploadable Logo + Hex Brand Color (P0)
**Status:** ✅ COMPLETE

#### E4) Outlined Buttons / Icon Border Styling Standardization (P1)
**Status:** ✅ COMPLETE

#### E5) Theme Background: Pure Black Base (P1)
**Status:** ✅ COMPLETE

**Phase E Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_3.json` — **backend 100% (43/43)**, **frontend 100%**

---

### Phase F — PM Checklist Rework (Structured Checklists + PDF Export) + Public Breakdown Reporting
> This phase makes PM execution **structured, repeatable, and printable**, and ensures **breakdown reporting is never blocked by authentication**.

#### F1) Structured PM Templates (Checklist Builder with one-to-many grouping) (P0)
**Status:** ✅ COMPLETE

#### F2) Dedicated “Close PM Task” Page (Per-row status + per-row remarks) (P0)
**Status:** ✅ COMPLETE

#### F3) PDF Export per PM Task (Blank + Completed) (P0)
**Status:** ✅ COMPLETE

#### F4) Public “Report Breakdown” Entry Point (No login required) (P0)
**Status:** ✅ COMPLETE

**Phase F Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_4.json` — **backend 98.8% (82/83)** *(single miss is a test artifact)*, **frontend 100%**

---

### Phase G — Bugfix + Weibull Demo Data (Verification Enablement)
> This phase addresses a production-stopper PDF crash and adds deterministic seeded data to validate Weibull reliability calculations and AWS UI.

#### G1) Fix Close PM “Download PDF” runtime error (P0)
**Status:** ✅ COMPLETE

#### G2) Seed deterministic Weibull verification dataset (P0)
**Status:** ✅ COMPLETE

**Phase G Testing:** ✅ COMPLETE
- Manual + browser validation

---

### Phase H — UI Polish Pass (Creative Freedom; Zero Logic Changes)
> A purely visual refinement pass to improve readability, “HUD coherence”, and perceived quality without touching business logic.

#### H1) Global CSS micro-interactions + HUD detailing (P1)
**Status:** ✅ COMPLETE

#### H2) JSX presentational tweaks (P1)
**Status:** ✅ COMPLETE

**Status:** ✅ COMPLETE

---

### Phase I — Warnings + Workflow Changes + Kanban/Repair Dedicated Pages
> This phase differentiates “machine down” vs “needs attention”, tightens CMMS governance (admin closure), improves Kanban as default execution surface, and standardizes dedicated-page patterns for execution (repair page).

#### I1) Add “Warning” entry type (non-downtime, yellow-tagged) (P0)
**Status:** ✅ COMPLETE

#### I2) Report Breakdown/Warning modal must not close on outside click/escape (P0)
**Status:** ✅ COMPLETE

#### I3) Change Breakdown icon from flame → cracked gear (P0)
**Status:** ✅ COMPLETE

#### I4) Work Orders: machine name not clickable to machine stats (P0)
**Status:** ✅ COMPLETE

#### I5) Work Order completion requires Admin closure (Corrective lifecycle) (P0)
**Status:** ✅ COMPLETE

#### I6) Operator/public breakdown submissions always auto-dispatch WO + auto-assign tech (P0)
**Status:** ✅ COMPLETE

#### I7) Work Orders defaults to Kanban + PM-from-Kanban navigation fix + density improvements (P0)
**Status:** ✅ COMPLETE

#### I8) Dedicated Repair page for breakdown execution (P0)
**Status:** ✅ COMPLETE

**Phase I Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_5.json`
  - **backend 100% (34/34)**
  - **frontend 95%** *(1 skipped automation step due to no OPEN breakdowns available; verified manually via direct repair URL)*

---

### Phase J — PM WO Admin Closure + Kanban Detail Popout Modal (P0)
> This phase standardizes the WO lifecycle across **all** WO sources (Corrective + PM), and upgrades Kanban UX with a fast detail popout for inspection and time edits.

#### J1) PM completion must park linked Work Order at `PENDING_ADMIN_CLOSURE` (P0)
**Delivered**
- Backend (`/app/backend/routers_maintenance.py`):
  - `POST /api/pm-tasks/{task_id}/complete` now finds any linked Work Orders:
    - match: `pm_task_id == task_id`
    - status in: `OPEN | ASSIGNED | IN_PROGRESS`
  - Updates WO to:
    - `status = PENDING_ADMIN_CLOSURE`
    - `completed_at = now`
    - `duration_minutes` computed from `started_at` (fallback `created_at`)
    - `pm_completion_id` stored for traceability
  - Emits:
    - timeline event (`wo_completed`) with “awaiting admin closure” language
    - notification: **"Admin Review Required"** with `target_role='admin'`

**Status:** ✅ COMPLETE

#### J2) Work Order time edits via `action='update'` (P0)
**Delivered**
- Backend (`/app/backend/routers_maintenance.py`):
  - `WOUpdate` model extended:
    - `started_at` (ISO datetime)
    - `completed_at` (ISO datetime)
  - `PUT /api/work-orders/{wo_id}` with `action='update'` now:
    - allows edits only for **admin** OR **assigned_to == current user** (403 otherwise)
    - rejects `completed_at < started_at` (400)
    - recomputes `duration_minutes` when both times are present
    - creates a timeline event `wo_updated`
    - returns `{ ok: true, work_order: <updated> }`

**Status:** ✅ COMPLETE

#### J3) Kanban card detail popout modal (P0)
**Delivered**
- Frontend (`/app/frontend/src/pages/WorkOrders.jsx`):
  - Clicking any Kanban card opens `WODetailModal` (`data-testid='wo-detail-modal'`)
  - Modal displays full WO details: number, badges, machine/type/assignee/created/duration/closed_by, description, root cause, action taken, spares.
  - Includes **Execution Times** panel:
    - `datetime-local` Start/End inputs
    - Save Times button
    - enabled only for **admin + assigned tech** (others see read-only)
  - Maintains execution flows:
    - Start / Complete / Admin Close buttons contextual by status
    - Preventive completion routes to PM closeout page
    - Repair/PM deep links provided (Open Repair Page / PM Closeout Page)
  - Card action buttons (Start/Complete/Admin Close) use `stopPropagation` so they do not open the modal.

**Status:** ✅ COMPLETE

**Phase J Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_6.json`
  - **backend 100% (29/29)**
  - **frontend 100%**

---

### Phase L — RCA 5-Why Module + Technician Analytics + Line Runtime + AWS Category Sorting (P0)
> This phase upgrades governance and analytics: enforce structured RCA, add admin-only technician analytics, correct runtime logging to line-level while maintaining machine reliability computations, and add failure-category sorting in AWS.

#### L1) Root Cause Analysis (RCA) Module — Structured 5-Why + Auto-triggered RCA Work Order (P0)
**Scope**
- Replace the current “RCA follow-up” rule with a dedicated RCA module.
- **Trigger conditions** (threshold from `reliability_settings.root_cause_downtime_minutes`, default 30):
  - Breakdown downtime > threshold (existing trigger)
  - **NEW:** Work Order duration > threshold on technician completion
- **Auto-generated RCA Work Order**:
  - `wo_type = 'RCA'` (new type)
  - assigned to the **attending technician** (Breakdown.assigned_to or WO.assigned_to)
  - lifecycle matches global governance: completion → `PENDING_ADMIN_CLOSURE` → admin close → `CLOSED`
- **Mandatory RCA submission**:
  - 5 sequential “Why did this happen?” fields
  - final `root_cause` and `corrective_action`
  - RCA WO cannot be completed unless all required fields are present (400).
- **Linking & visibility**:
  - RCA record linked back to origin (Breakdown and/or Work Order)
  - appears in originating record’s detail view and timeline.

**Backend Deliverables**
- Work Order schema additions for RCA records:
  - `wo_type: 'RCA'`
  - `rca`: `{ why_1..why_5, final_root_cause, corrective_action, submitted_at, submitted_by }`
  - linkage fields: `source_breakdown_id`, `source_work_order_id` (and reciprocal `rca_task_id` on origin)
- New/updated endpoints:
  - `PUT /api/work-orders/{wo_id}/rca` — submit/update RCA (admin or assigned tech only)
  - `GET /api/work-orders/{wo_id}` — return WO + linked RCA summary (or linked origin summary when WO is RCA)
  - Add RCA trigger logic:
    - Breakdown close handler (already has downtime trigger): generate RCA WO of type RCA and set breakdown.rca_task_id
    - Work Order completion handler: if duration > threshold and no existing RCA link, generate RCA WO and set work_order.rca_task_id
- Timeline + notifications:
  - create timeline events for RCA creation, submission, completion
  - notify assigned technician when RCA is created
  - notify admins when RCA is completed (parks at `PENDING_ADMIN_CLOSURE`).

**Frontend Deliverables**
- Add `RCA` into WO type filters (WorkOrders page).
- New RCA form page:
  - route: `/work-orders/rca/:woId`
  - five Why fields with progressive unlock
  - final Root Cause + Corrective Action
  - submit button, validation, and cyberpunk styling.
- Detail modal additions:
  - show RCA summary/links for origin WOs
  - if WO is RCA, show “Open RCA Form” action.
- Breakdown details:
  - show link to RCA WO when present.

**Status:** 🔶 IN PROGRESS

#### L2) Technician Analytics — Admin-only (P0)
**Scope**
- Add a new **Technician Analytics** section inside Analytics.
- Must be **backend-enforced admin-only** (403 for non-admin).
- Filters:
  - `date_from`, `date_to`
  - `line`, `department`
  - `wo_type`

**Backend Deliverables**
- `GET /api/analytics/technicians` (Depends: `require_admin`)
- Metrics per technician (from breakdowns, work_orders, pm_completions):
  - total and average time per breakdown/WO/PM
  - breakdown resolved count leaderboard
  - average resolution/repair time
  - WO completion count and on-time completion rate
  - PM completion count and compliance rate.

**Frontend Deliverables**
- In `Analytics.jsx`, when `isAdmin`:
  - render “Technician Analytics” panel/tab
  - leaderboard table + KPI cards
  - filter controls for date range + line/department + WO type.

**Status:** 🔶 IN PROGRESS

#### L3) Runtime logging per Line (not per Machine) + machine inheritance for Weibull/availability (P0)
**Scope**
- Runtime input becomes **line-level** (one entry per line/day).
- Availability computed per line based on line run hours vs calendar hours.
- Machines **inherit** their line runtime for reliability calculations (Weibull) without requiring machine-level entry.

**Backend Deliverables**
- New collection + endpoints:
  - `line_runtime_logs`: `{ line, department, date, calendar_hours, run_hours, dark_hours, availability, entered_by, source, created_at }`
  - `POST /api/runtime-logs` updated to accept `{ line, date, run_hours, calendar_hours }` (line-level)
  - `GET /api/line-runtime-logs` for line entries
  - CSV import updated to: `line, date, run_hours[, calendar_hours]`
- Fan-out strategy to preserve existing metrics/Weibull compatibility:
  - on write/import of a line log, generate/upsert per-machine `runtime_logs` rows for all machines in that line with `source='line'`
  - Weibull and analytics continue to read from `runtime_logs` as before.

**Frontend Deliverables**
- Update `Runtime.jsx`:
  - replace MachineSelect with a Line select
  - show line runtime table and summary
  - keep cyberpunk outlined controls.

**Status:** 🔶 IN PROGRESS

#### L4) AWS category sorting — Mechanical / Electrical / PLC (P0)
**Scope**
- Add category filter chips to AWS page.
- Show per-machine failure-category distribution and dominant category.

**Backend Deliverables**
- Extend `GET /api/reliability/metrics` to attach:
  - `failure_categories`: counts for `MECHANICAL`, `ELECTRICAL`, `CONTROL_PLC`
  - `dominant_category`: max-count category (ties deterministic)
- Optional query param support: `?category=MECHANICAL|ELECTRICAL|CONTROL_PLC`.

**Frontend Deliverables**
- Update `AWSPage.jsx`:
  - add category filter chips
  - add table column for dominant category + counts
  - preserve existing health filter chips and admin settings panel.

**Status:** 🔶 IN PROGRESS

**Phase L Testing (planned)**
- New backend test report `iteration_7.json`:
  - RCA generation for breakdowns + long WOs
  - RCA submission validation (mandatory 5-why)
  - RCA lifecycle (complete → pending admin → admin close)
  - technician analytics endpoint permissions and calculations
  - runtime line log fan-out correctness + analytics availability consistency
  - AWS category filters.
- New frontend checks:
  - RCA form progressive unlock + required fields
  - admin-only technician analytics visible/enforced
  - line runtime UI flows
  - AWS category chips.

---

## 3) Next Actions

### Immediate (P0)
1) Implement **Phase L1** RCA module:
- Add `RCA` WO type + data schema
- Auto-trigger logic for breakdown close and long WO completion
- RCA submission endpoint + UI form page
- Bidirectional linking + timeline visibility

2) Implement **Phase L2** Technician Analytics (admin-only):
- Backend endpoint with filters + aggregations
- Frontend admin-only panel

3) Implement **Phase L3** Line runtime:
- Backend new line runtime collection + fan-out to machine runtime
- Update runtime UI + CSV import format

4) Implement **Phase L4** AWS category sorting:
- Add category counts/dominant category to reliability metrics
- Add AWS filter chips + table column

### Optional Next Enhancements (Future / Backlog)
- Refactor: centralize admin-review notification logic for all WO sources (reduce duplication across endpoints).
- Add an Admin “Warnings” management view (filters, close/reopen, trends) and/or link warnings to WO details.
- Extend timeline filtering for warnings and add a “Warning” chip in machine tiles.
- Harden public kiosk endpoints:
  - rate limiting / spam throttling
  - optional kiosk PIN
  - optional photo upload.
- PM templates UI in Administration (separate from creating a PM task) to manage reusable templates by machine type.
- True “current shift” time window mode using a configurable shift schedule (timezone-aware) for availability KPIs.
- Control Room ribbon drilldown: click line/section → open filtered breakdown/work-order panel.
- PDF styling polish:
  - embed logo in header
  - optional signature capture.
- Reliability demo management:
  - add an admin endpoint/button to purge `source='weibull_demo'` data
  - show a “DEMO” tag on seeded Weibull models in AWS UI.
- Contrast review pass (WCAG-oriented) for pure black + neon accents.

---

## 4) Success Criteria
- ✅ Control Room ribbon is **line-first**:
  - Availability + downtime per line always visible.
  - Expandable to section/process-group breakdown.
  - Plant-wide totals available but demoted.
- ✅ Sidebar supports per user:
  - icon colors
  - drag-and-drop ordering
  - persistence across refresh/login.
- ✅ Branding supports admin:
  - uploadable logo
  - hex brand accent
  - immediate visual propagation.
- ✅ Buttons/icons are consistently outlined across the app.
- ✅ Theme background is true black without blue undertone.
- ✅ PM execution is structured and auditable:
  - component → sub-item checklist rows
  - per-row OK/NOT OK + per-row remarks
  - dedicated close page
- ✅ PM checklists are printable and consistent:
  - blank + completed PDF export matches checklist sheet format.
- ✅ Reporting is accessible to non-authenticated operators:
  - login-page public reporting
  - reporter accountability captured
  - submissions flagged `public_kiosk` and visually tagged.
- ✅ Reliability calculations are verifiable:
  - deterministic Weibull demo dataset exists (runtime logs + closed breakdowns)
  - AWS shows L3/Advanced machines with beta/eta, predicted life and Weibull Active count.
- ✅ Warnings are functionally distinct from breakdowns:
  - no downtime impact
  - yellow watch state
  - WO auto-dispatched and auto-assigned
  - launchable from all reporting entry points.
- ✅ Work orders require admin closure:
  - `PENDING_ADMIN_CLOSURE` implemented
  - admin notifications sent
  - only admin can final-close.
- ✅ PM Work Orders follow the same governance:
  - PM completion does **not** auto-close a WO
  - linked PM WO transitions to `PENDING_ADMIN_CLOSURE`
  - admin notification targeted to `admin` role.
- ✅ Kanban has fast inspection + quick edits:
  - card click opens detail modal
  - Start/End time edits available to admin + assignee
  - validation enforced (no end before start)
- ✅ Dedicated execution pages exist where required:
  - PM close-out page
  - Breakdown repair page.
- ✅ **RCA module enforces structured 5-Why**:
  - auto-generated RCA WO when downtime/duration exceeds threshold
  - 5-Why + final root cause/corrective action required prior to completion
  - RCA parks at `PENDING_ADMIN_CLOSURE` and requires admin closure
  - RCA linked and visible from originating Breakdown/WO + timeline.
- ✅ **Technician Analytics is admin-only**:
  - backend endpoint returns 403 to non-admins
  - metrics match definitions and are filterable.
- ✅ **Runtime logged per line**:
  - line availability computed from line logs
  - machines inherit line runtime for Weibull/analytics without per-machine entry.
- ✅ **AWS category sorting exists**:
  - filter chips for Mechanical/Electrical/PLC
  - per-machine category counts + dominant category visible.
- ✅ UI polish improvements do not introduce logic regressions:
  - reduced-motion users respected.
- ✅ All changes validated by test reports:
  - Phase E: `/app/test_reports/iteration_3.json`
  - Phase F: `/app/test_reports/iteration_4.json`
  - Phase I: `/app/test_reports/iteration_5.json`
  - Phase J: `/app/test_reports/iteration_6.json`
  - Phase L (planned): `/app/test_reports/iteration_7.json`
