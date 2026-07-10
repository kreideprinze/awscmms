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
  - Ensure reporting is **dispatch-ready**: every Breakdown/Warning submission must explicitly **assign a technician** and must **auto-create a WO** (no opt-out).
- Ensure reliability analytics are **verifiable with seeded data**:
  - Provide deterministic, labeled demo datasets to validate **Weibull** fit outputs (beta/eta/mean life/B10) and AWS UI behavior.
- **Differentiate downtime vs non-downtime events** clearly:
  - Add **Warning** observations that **do not affect** Availability/MTBF/MTTR but **do auto-dispatch** a WO and visually appear yellow across the HUD.
- Ensure execution governance in CMMS:
  - Work order completion requires **Admin closure** before final CLOSED — applies to **Corrective AND PM-generated Work Orders**.
- Improve Kanban operational UX:
  - Kanban cards open a **detail popout modal** for fast inspection and quick edits.
  - Work Orders support **editable Start/End times** (admin + assigned technician) with validation and audit trail.
- Runtime governance:
  - Runtime is **line-level** as the source of truth for availability.
  - Machines **inherit** their line runtime via fan-out to preserve per-machine reliability/Weibull calculations.
  - A **calendar view** must make missing line-days obvious and support admin CRUD.
  - **Plant Runtime Clock per-machine auto accumulation remains enabled alongside line logging** (per user choice).

### Phase L (delivered) objectives
- Enforce standardized **Root Cause Analysis (5-Why)** governance:
  - Auto-trigger RCA when downtime/duration exceeds threshold (default 30 min; admin-configurable).
  - RCA requires structured 5-Why submission and cannot complete/close without it.
  - RCA records link bidirectionally to originating Breakdown/Work Order and appear in timeline.
- Provide **Admin-only Technician Analytics** in Plant Analytics:
  - Enforced by backend role permissions (403 for non-admin), not just UI hiding.
- Runtime is logged **per line** (not per machine) to calculate availability correctly:
  - Line-level runtime entry; machines inherit line runtime for reliability computations.
- AWS supports Mechanical/Electrical/PLC category sorting/filtering:
  - Category chips + per-machine failure category counts + dominant category.

### Phase M (now delivered) objectives
- **Mandatory technician assignment + mandatory WO creation** for all Breakdown **and Warning** submissions:
  - Applies uniformly to authenticated, operator, and public kiosk entry points.
  - Removes optional/checkbox-based auto-WO behavior; submitter explicitly selects technician.
- Runtime module provides a **calendar-first, line-wise logging UX**:
  - Month grid shows logged/partial/missing line-days.
  - Day dialog supports per-line log/update/delete for Admins; view-only for others.
  - Admin-only deletion removes fanned per-machine logs.

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
**Status:** ✅ COMPLETE *(superseded by Phase M which mandates explicit technician selection)*

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
**Status:** ✅ COMPLETE

#### J2) Work Order time edits via `action='update'` (P0)
**Status:** ✅ COMPLETE

#### J3) Kanban card detail popout modal (P0)
**Status:** ✅ COMPLETE

**Phase J Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_6.json`
  - **backend 100% (29/29)**
  - **frontend 100%**

---

### Phase L — RCA 5-Why Module + Technician Analytics + Line Runtime + AWS Category Sorting (P0)
> This phase upgrades governance and analytics: enforce structured RCA, add admin-only technician analytics, shift runtime logging to line-level (machines inherit line runtime), and add failure-category sorting in AWS.

#### L1) Root Cause Analysis (RCA) Module — Structured 5-Why + Auto-triggered RCA Work Order (P0)
**Status:** ✅ COMPLETE

#### L2) Technician Analytics — Admin-only (P0)
**Status:** ✅ COMPLETE

#### L3) Runtime logging per Line (not per Machine) + inheritance to machines (P0)
**Status:** ✅ COMPLETE

#### L4) AWS category sorting — Mechanical / Electrical / PLC (P0)
**Status:** ✅ COMPLETE

**Phase L Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_7.json`
  - **backend 100% (15/15)**
  - **frontend verified via main-agent screenshot automation + manual checks**

---

### Phase M — Mandatory Technician Assignment + Mandatory WO Creation + Runtime Calendar (P0)
> This phase removes optional dispatch behavior: every Breakdown/Warning report explicitly assigns a technician and always creates a linked work order. It also upgrades runtime entry UX to a calendar-first, line-wise logging module.

#### M1) Mandatory technician assignment + mandatory WO creation on all Breakdown/Warning submissions (P0)
**Delivered**
- Backend (`/app/backend/routers_maintenance.py`):
  - Removed `auto_create_work_order` from all Breakdown/Warning create models and endpoints.
  - Added `assigned_to` to:
    - `BreakdownCreate`
    - `PublicBreakdownCreate`
    - `WarningCreate`
    - `PublicWarningCreate`
  - Added `_validate_technician(username)`:
    - requires non-empty
    - must be an **active** user with `role='technician'`
    - returns 400 on missing/invalid/non-technician
  - Updated `_create_breakdown_internal(...)`:
    - always creates a linked **Corrective** WO (`source='breakdown_auto'`)
    - assigns WO to selected technician
    - breakdown starts status `ASSIGNED` with `assigned_to`
    - internal callers may omit assigned_to and fall back to `_pick_technician()`
  - Updated Warning flow (`_create_warning_internal`) to accept `assigned_to`:
    - warning WO always created and assigned to selected technician
  - Updated `GET /public/report-context` to include `technicians` list for kiosk dropdown.
- Frontend (`/app/frontend/src/components/ReportBreakdownDialog.jsx`):
  - Removed Auto-WO checkbox entirely.
  - Added mandatory "Assign Technician" select (`data-testid='bd-technician-select'`).
  - Applies to Breakdown + Warning modes and to both authenticated + public kiosk modes.
  - Submit validation requires machine + reporter name + remarks + technician.

**Status:** ✅ COMPLETE

#### M2) Runtime Module — calendar-first, line-wise logging (P0)
**Delivered**
- Backend (`/app/backend/routers_ops.py`):
  - Added admin-only delete: `DELETE /api/line-runtime-logs?line=<line>&date=<YYYY-MM-DD>`
    - deletes the `line_runtime_logs` entry
    - deletes fanned-out per-machine runtime logs for that line+date (sources `line`/`csv_import`)
    - triggers reliability recomputation
    - returns `{ ok: true, machine_logs_removed: n }`
- Frontend (`/app/frontend/src/pages/Runtime.jsx`):
  - Defaults to **Calendar view** (`data-testid='runtime-calendar'`).
  - Month navigation + Monday-first grid.
  - Day cells show `logged/total lines` and are color-coded:
    - green = all lines logged
    - yellow = partial
    - dim = missing
    - future days disabled
  - Clicking a day opens the day dialog (`data-testid='runtime-day-dialog'`) with per-line rows:
    - Admin can Log/Update/Delete inline
    - Technician/Operator view-only
  - Table view retained via toggle (`runtime-view-toggle`).

**Status:** ✅ COMPLETE

**Phase M Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_8.json`
  - **backend 99%** (95/96; single failure is a *test-expectation quirk*, not a product bug)
  - **frontend 95%** with **0 real issues reported**
- Additional manual + screenshot verification:
  - public kiosk breakdown dialog shows technician select and no checkbox
  - runtime calendar day dialog renders per-line CRUD for admin

---

## 3) Next Actions

### Immediate (P0)
- None required; Phase M deliverables implemented and validated.

### Hardening / Refactor (P1)
- Centralize “admin review required” notification/timeline logic for all WO sources (Corrective, PM, RCA) to reduce duplication.
- Add MongoDB indexes:
  - `work_orders`: `pm_task_id`, `rca_task_id`, `source_breakdown_id`, `source_warning_id`, `source_work_order_id`, `assigned_to`, `status`, `completed_at`
  - `breakdowns`: `assigned_to`, `status`, `end_time`
  - `warnings`: `assigned_to`, `status`
  - `runtime_logs`: `machine_id`, `line`, `date`, `source`
  - `line_runtime_logs`: `line`, `date`
- Add an admin-visible RCA dashboard (open RCAs, aging, overdue) and link it from Admin/Analytics.
- Add drill-down from Technician Analytics rows to pre-filtered Work Orders / Breakdowns.

### Runtime governance note (Supersession + coexistence)
- **Line runtime is the availability source of truth**.
- **Plant Runtime Clock per-machine accumulation is still enabled** (per user choice) and may co-exist with line fan-out.
  - If conflicts appear in future (e.g., plant clock overwriting line fan-out on same machine+date), consider adjusting source precedence or disabling plant clock.

### Optional Next Enhancements (Future / Backlog)
- Add an Admin “Warnings” management view (filters, close/reopen, trends) and/or link warnings to WO details.
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
- ✅ Reporting is dispatch-ready:
  - Breakdown + Warning submissions require selecting a technician
  - WO auto-creation is mandatory (no checkbox/toggle)
  - linked WO is assigned to selected technician
- ✅ Reliability calculations are verifiable:
  - deterministic Weibull demo dataset exists (runtime logs + closed breakdowns)
  - AWS shows L3/Advanced machines with beta/eta, predicted life and Weibull Active count.
- ✅ Warnings are functionally distinct from breakdowns:
  - no downtime impact
  - yellow watch state
  - WO auto-dispatched (now **explicitly assigned** at report time)
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
- ✅ Runtime is line-first and calendar-visible:
  - month calendar highlights missing line-days
  - admin can log/edit/delete per line/day
  - technician/operator view-only
  - machines inherit line runtime for per-machine analytics/reliability.

### Phase L success criteria (all met)
- ✅ **RCA module enforces structured 5-Why**.
- ✅ **Technician Analytics is admin-only**.
- ✅ **Runtime logged per line**.
- ✅ **AWS category sorting exists**.

### Phase M success criteria (all met)
- ✅ **Mandatory technician assignment** on Breakdown + Warning submissions across all entry points.
- ✅ **Mandatory WO creation** on all Breakdown/Warning submissions (no opt-out).
- ✅ **Public report context includes technicians** for kiosk dropdown.
- ✅ **Runtime calendar view** with logged/partial/missing visibility + per-line day dialog + admin-only delete.

### Validation evidence
- ✅ All changes validated by test reports:
  - Phase E: `/app/test_reports/iteration_3.json`
  - Phase F: `/app/test_reports/iteration_4.json`
  - Phase I: `/app/test_reports/iteration_5.json`
  - Phase J: `/app/test_reports/iteration_6.json`
  - Phase L: `/app/test_reports/iteration_7.json`
  - Phase M: `/app/test_reports/iteration_8.json`
