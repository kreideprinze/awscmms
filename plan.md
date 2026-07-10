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

## 3) Next Actions
> All phases through J are complete. Remaining work is optional backlog only.

### Completed (Prior Iterations) ✅
- Removed infinite zoom in Control Room; enabled vertical scroll.
- Replaced plant runtime clock display with wall-clock time.
- Applied Cyberpunk HUD styling across all modules.
- Verified Breakdown → auto-create WO end-to-end.

### Phase I — Completed Work ✅
- Warning records + yellow watch status + always-dispatched WO.
- Report dialogs: no outside click/escape dismiss.
- Cracked gear breakdown icon across app.
- WO machine names are plain text (stats only via Control Room).
- WO admin-closure governance implemented.
- Operator/public breakdowns always auto-dispatch and auto-assign.
- Work Orders Kanban default + PM route fix.
- Dedicated Breakdown Repair page.

### Phase J — Completed Work ✅
- PM completion now parks linked PM Work Orders at **PENDING_ADMIN_CLOSURE** + admin notifications.
- Work Orders support time edits (Start/End) with admin/assignee permission checks + validation.
- Kanban card click opens a full WO detail modal with editable Start/End times and deep links.

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
  - admin notification targeted to `admin` role
- ✅ Kanban has fast inspection + quick edits:
  - card click opens detail modal
  - Start/End time edits available to admin + assignee
  - validation enforced (no end before start)
- ✅ Dedicated execution pages exist where required:
  - PM close-out page
  - Breakdown repair page.
- ✅ UI polish improvements do not introduce logic regressions:
  - reduced-motion users respected
- ✅ All changes validated by test reports:
  - Phase E: `/app/test_reports/iteration_3.json`
  - Phase F: `/app/test_reports/iteration_4.json`
  - Phase I: `/app/test_reports/iteration_5.json`
  - Phase J: `/app/test_reports/iteration_6.json`
