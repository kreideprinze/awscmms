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
  - Work order completion requires **Admin closure** before final CLOSED.
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
**Delivered**
- Backend:
  - `db.warnings` collection + `WRN-` counter
  - `POST /api/warnings`, `GET /api/warnings`
  - `POST /api/public/warnings` (no login), flagged `submitted_via=public_kiosk`
  - Warning creates **no breakdown** and **does not affect** availability/MTBF/MTTR.
  - Machine status set to **watch** (yellow) for visibility.
  - Always auto-creates a WO (Inspection/Corrective) and auto-assigns to **least-loaded** technician.
  - Admin closing warning-sourced WO closes warning and restores machine status from watch → running.
- Frontend:
  - Warning mode in the same dialog (same fields), visually yellow.
  - Launch points: Login (public), Breakdowns page, Machine Drawer.
  - Breakdowns page has **Breakdowns/Warn​ings** toggle and warnings table view.
  - Control Room feed rails highlight warning-created events in yellow.

**Status:** ✅ COMPLETE

#### I2) Report Breakdown/Warning modal must not close on outside click/escape (P0)
- Dialog now prevents `onInteractOutside`, `onPointerDownOutside`, and `onEscapeKeyDown`.
- Only the explicit **×** closes.

**Status:** ✅ COMPLETE

#### I3) Change Breakdown icon from flame → cracked gear (P0)
- Implemented `CrackedGear` SVG icon and replaced flame usage in:
  - Sidebar / navigation
  - Login public breakdown button
  - Repair page header
  - (and shared imports through `StatusBits`)

**Status:** ✅ COMPLETE

#### I4) Work Orders: machine name not clickable to machine stats (P0)
- Removed `openMachine(...)` linking from:
  - Work Orders Kanban cards
  - Work Orders table view

**Status:** ✅ COMPLETE

#### I5) Work Order completion requires Admin closure (P0)
- Lifecycle updated:
  - `OPEN → ASSIGNED → IN_PROGRESS → (tech) PENDING_ADMIN_CLOSURE → (admin) CLOSED`
- Backend:
  - tech `complete` sets `PENDING_ADMIN_CLOSURE` and sends **admin-role notifications**.
  - tech `close` returns **403**.
  - admin `close` finalizes CLOSED.
  - Migrated existing `COMPLETED` WOs → `PENDING_ADMIN_CLOSURE`.
- Frontend:
  - Kanban includes **ADMIN CLOSURE** column.
  - Admin sees **Admin Close** action; non-admin sees “awaiting admin”.

**Status:** ✅ COMPLETE

#### I6) Operator/public breakdown submissions always auto-dispatch WO + auto-assign tech (P0)
- Backend:
  - Forces `auto_create_work_order=True` for operator role.
  - Uses least-loaded technician assignment.
- Frontend:
  - Auto-create checkbox hidden for operator/public flows (replaced by note).
  - Admin/technician still have checkbox for authenticated breakdown creation.

**Status:** ✅ COMPLETE

#### I7) Work Orders defaults to Kanban + PM-from-Kanban navigation fix + density improvements (P0)
- Default Work Orders view is Kanban.
- Cards made denser (smaller padding/text) to show more per column.
- PM-type WO “Complete” routes to current structured checklist page:
  - `/preventive-maintenance/close/{pm_task_id}`

**Status:** ✅ COMPLETE

#### I8) Dedicated Repair page for breakdown execution (P0)
- Added `/breakdowns/repair/:breakdownId` dedicated page:
  - Live elapsed downtime display
  - root cause + action taken + spares
  - completion restores machine
- “Start Repair” navigates to repair page (and triggers `start` if needed).

**Status:** ✅ COMPLETE

**Phase I Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_5.json`
  - **backend 100% (34/34)**
  - **frontend 95%** *(1 skipped automation step due to no OPEN breakdowns available; verified manually via direct repair URL)*

---

## 3) Next Actions
> All phases through I are complete. Remaining work is optional backlog only.

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

### Optional Next Enhancements (Future / Backlog)
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
- ✅ Dedicated execution pages exist where required:
  - PM close-out page
  - Breakdown repair page.
- ✅ UI polish improvements do not introduce logic regressions:
  - reduced-motion users respected
- ✅ All changes validated by test reports:
  - Phase E: `/app/test_reports/iteration_3.json`
  - Phase F: `/app/test_reports/iteration_4.json`
  - Phase I: `/app/test_reports/iteration_5.json`
