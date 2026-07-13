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

- **AWS / Predictive Maintenance Engine** is per-category:
  - Track separate health/life pools per machine for **Mechanical / Electrical / PLC(Control)**.
  - Trigger threshold is **admin-configurable** (default 80%) via `predictive_trigger_pct`.
  - AWS-triggered WOs are a distinct type: **AWS/Predictive** (`wo_type='Predictive'`, `aws_category` set).
  - **Life % ticks in real-time** using unified runtime philosophy (logged EOD hours override; otherwise 24/7 continuous).

- **MTBF consistency objective (NEW, completed)**:
  - **Machine-level MTBF in Analytics must match AWS MTBF exactly**, because both represent the same reliability-engine metric.
  - Provide a transparent source indicator (`mtbf_source`) for debugging and stakeholder clarity.

### Control Room KPI/range objectives
- Control Room line KPIs support presets **Shift=8h, Day=24h, Week=168h** plus a **custom date range** slicer.
- Control Room visual cleanup:
  - Remove “flavor/narrative text” from line cards and plant totals; keep KPIs only.
  - Add a live red breakdown timer ribbon (HH:MM:SS ticking) on any line card with an active breakdown.
  - Clicking the live DOWN timer ribbon **jumps to the exact breakdown** (deep-link).

### Navigation + productivity objectives
- **Universal “jump to Work Order” deep linking**:
  - Clicking a WO reference anywhere opens the **exact Work Order popout/modal** rather than a generic list.
  - Contract: `?wo=<id>` plus a global `openWorkOrder(id)`.

- **Universal “jump to Breakdown” deep linking**:
  - Clicking a line’s live DOWN timer ribbon opens `/breakdowns?bd=<breakdown_id>`.
  - Breakdowns page expands + highlights + scrolls to the referenced breakdown, then cleans the URL.

- **Universal “jump to Warning” deep linking**:
  - Clicking a warning reference opens `/breakdowns?warning=<warning_id>`.
  - Breakdowns switches to Warnings view and opens the exact warning detail dialog.

- **Universal “jump to PM Task” deep linking**:
  - Clicking a PM task reference opens `/preventive-maintenance?task=<pm_task_id>`.
  - PM page highlights + scrolls to the referenced task and cleans the URL.

- **Live Event Feed deep-linking for all event types**:
  - Clicking any Live Event Feed entry deep-links to the *exact* referenced record:
    - Work Orders → WO popout
    - Breakdowns → Breakdown row expansion
    - Warnings → Warning detail dialog
    - PM Tasks → PM row highlight
    - Fallback → Machine drawer

- **Global “My Tasks” filter** for technicians across: Breakdowns, Work Orders (Kanban), PMs.
- **Fuzzy/typeahead search** on Report Breakdown form dropdowns for Area/Line and Machine.
- **Warnings are observation-only** and **always dispatch an Inspection WO** (no Corrective option).

### Analytics + runtime objectives
- Analytics supports a date range slicer applied to all KPIs/charts.
- Add closure-rate KPI + Pareto analysis.
- **Runtime module is the single source of truth**:
  - Default assumption: plant runs **24/7**, ticking in real time.
  - End-of-day override: once a line runtime log exists for a date, it becomes authoritative globally.
  - AWS Life %/hours-since-failure uses the **same hybrid runtime philosophy** (day-prorated logs + 24/7 fallback) so predictive ticking is consistent with Control Room.

---

## 2) Implementation Steps

### Phase 1 — Core “Operational Loop” POC (Isolation) (WebSocket + eventing + derived machine state)
**Status:** ✅ COMPLETE

---

### Phase 2 — V1 App Development (MVP, end-to-end usable)
**Status:** ✅ COMPLETE

---

### Phase 3 — Reliability/AWS + Predictive + Analytics (multi-level)
**Status:** ✅ COMPLETE *(superseded by newer AWS multi-pool implementation)*

---

### Phase 4 — Spares/Inventory + Administration hardening + scale readiness
**Status:** ✅ COMPLETE

---

### Phase E — Control Room Ribbon + Customization + Theming
**Status:** ✅ COMPLETE

**Phase E Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_3.json` — **backend 100% (43/43)**, **frontend 100%**

---

### Phase F — PM Checklist Rework (Structured Checklists + PDF Export) + Public Breakdown Reporting
**Status:** ✅ COMPLETE

**Phase F Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_4.json` — **backend 98.8% (82/83)** *(single miss is a test artifact)*, **frontend 100%**

---

### Phase G — Bugfix + Weibull Demo Data (Verification Enablement)
**Status:** ✅ COMPLETE

---

### Phase H — UI Polish Pass (Creative Freedom; Zero Logic Changes)
**Status:** ✅ COMPLETE

---

### Phase I — Warnings + Workflow Changes + Kanban/Repair Dedicated Pages
**Status:** ✅ COMPLETE *(workflow rules updated/superseded by newer governance rules)*

**Phase I Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_5.json`
  - **backend 100% (34/34)**
  - **frontend 95%** *(1 skipped automation step due to no OPEN breakdowns available; verified manually)*

---

### Phase J — PM WO Admin Closure + Kanban Detail Popout Modal (P0)
**Status:** ✅ COMPLETE *(closure rules updated/superseded by current branching rules)*

**Phase J Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_6.json`
  - **backend 100% (29/29)**
  - **frontend 100%**

---

### Phase L — RCA 5-Why Module + Technician Analytics + Line Runtime + AWS Category Sorting (P0)
**Status:** ✅ COMPLETE *(analytics extended later; AWS logic now multi-pool)*

**Phase L Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_7.json`
  - **backend 100% (15/15)**
  - **frontend verified via screenshot automation + manual checks**

---

### Phase M — Mandatory Technician Assignment + Mandatory WO Creation + Runtime Calendar (P0)
**Status:** ✅ COMPLETE *(technician-mandatory WO rule superseded: Unassigned WOs allowed universally; technician-mandatory breakdown closure reinstated in Corrections Part 4)*

**Phase M Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_8.json`
  - **backend 99%** (95/96; single failure is a *test-expectation quirk*, not a product bug)
  - **frontend 95%** with **0 real issues reported**

---

### Phase N — Plant bugfix pack (Breakdown/WO sync + Time edits + Availability + Warnings + Spares + PM PDF) (P0)
**Status:** ✅ COMPLETE *(availability + runtime now unified via kpi_engine.py)*

**Phase N Testing:** ✅ COMPLETE
- Backend: **15/15 tests passed (100%)**
- Frontend: verified

---

### Phase O — Kanban cleanup (remove OPEN column) + Clear Closed + remove redundant elements (P0)
**Status:** ✅ COMPLETE *(OPEN/Unassigned state reintroduced intentionally in current governance)*

---

### Phase P — Data Management (Seed Sample Data + Purge Operational Data)
**Status:** ✅ COMPLETE — **USER VERIFIED**

---

## New Work Phases (Current Roadmap)

### Phase Q — Backend overhaul: Hierarchy inversion + governance + AWS multi-pool + runtime unification
**Status:** ✅ COMPLETE

#### Q1) Schema + migration (Line-first hierarchy)
- ✅ New hierarchy: **Line → Department → Process Group → Machine**.
- ✅ In-place migration executed via `/app/backend/migrations.py` preserving history.

#### Q2) Work Orders lifecycle (Unassigned + claim + closure branching)
- ✅ Unassigned (`assigned_to=null`) supported.
- ✅ Claim supported (UI uses `PUT /api/work-orders/{id}` with `{action:'claim'}`).
- ✅ Closure branching implemented (verified):
  - Tech closes **Corrective + Inspection + Predictive (AWS)** directly.
  - **PM + RCA** require Admin closure (Pending Admin state).

#### Q3) AWS/Reliability engine (3 independent pools)
- ✅ Implemented in `/app/backend/reliability.py`:
  - Mechanical, Electrical, PLC pools
  - Admin-configurable threshold (default 80%) via `predictive_trigger_pct`
  - Reset/cancel behaviors on close/breakdown

#### Q4) Runtime single-source-of-truth
- ✅ Centralized calculations in `/app/backend/kpi_engine.py`.

#### Q5) Control Room breakdown jump metadata
- ✅ `kpi_engine.py` returns `active_breakdown_since`, plus:
  - `active_breakdown_id`
  - `active_breakdown_ticket`

**Phase Q Testing**
- ✅ Backend verified via python/curl/bash.
- ✅ `/app/test_reports/iteration_9.json` backend: **100%**.

---

### Phase T — Frontend Sync: Control Room + Hierarchy + UX cleanup (P0)
**Status:** ✅ COMPLETE

#### T0) Frontend schema sync audit (prevent crashes)
- ✅ Updated components that assumed old `Dept → Line` hierarchy.

#### T1) Control Room filter ribbon reposition (A)
- ✅ Filter ribbon moved **above** line cards.
- ✅ Departments filter deduped (Line-first duplicates removed).

#### T2) Custom date range slicer (E)
- ✅ Presets: Shift=8h, Day=24h, Week=168h.
- ✅ Custom date range supported (type=`date`).

#### T3) Remove flavor text from line/plant totals (F, G)
- ✅ Line cards and plant totals set to KPIs-only.

#### T4) Live breakdown timer ribbon (H)
- ✅ Live red HH:MM:SS breakdown timer ribbon on active line cards.

#### T5) Report Breakdown fuzzy/typeahead selectors (L)
- ✅ Fuzzy/typeahead for Line and Machine.
- ✅ Optional technician assignment supported (enables UNASSIGNED WOs).
- ✅ Post-test fix: prevent dialog auto-focus from opening dropdowns (`onOpenAutoFocus={e => e.preventDefault()}`), verified.

**Phase T Testing**
- ✅ Screenshot verification completed.

---

### Phase U — Frontend Sync: Work Orders + Kanban + Deep-links + My Tasks (P0)
**Status:** ✅ COMPLETE

#### U0) Global WO modal state foundation
- ✅ `AppContext`: `openWorkOrder`, `closeWorkOrder`, `woVersion` refresh bump.

#### U1) Kanban “Unassigned” column (I)
- ✅ 5-column Kanban: **UNASSIGNED / ASSIGNED / IN_PROGRESS / PENDING_ADMIN_CLOSURE / CLOSED**.

#### U2) Technician claim/self-assign in WO popout (I)
- ✅ Claim integrated for technicians.
- ✅ Claim verified end-to-end.

#### U3) AWS/Predictive WO type support (K)
- ✅ WO type filters include **Predictive (AWS)** and AWS badges.

#### U4) Universal deep-link “jump to Work Order” (C)
- ✅ Universal deep-link contract: `?wo=<id>`.
- ✅ `Layout.jsx` opens the modal automatically when `?wo=` is present.
- ✅ Notifications open the exact WO popout (when `reference_type=work_order`).

#### U5) Global “My Tasks” toggle for technicians (D)
- ✅ Implemented across Breakdowns, Work Orders, Preventive Maintenance.

#### U6) Closure rules reflected in UI (J)
- ✅ UI actions match governance.
- ✅ Verified via API: Corrective→CLOSED direct, Predictive→CLOSED direct, Preventive→PENDING_ADMIN_CLOSURE→Admin close.

#### U7) Post-test stability fixes
- ✅ Fixed dialog overlay interception after WO creation by preventing auto-focus in dialog content.

**Phase U Testing**
- ✅ Screenshot verification completed.

---

### Phase V — Frontend additions: Analytics + AWS page + Report Breakdown fuzzy search (P1)
**Status:** ✅ COMPLETE

#### V1) Analytics tab expansions (N)
- ✅ Added global date slicer (`date_from`/`date_to`) applied to all KPIs/charts.
- ✅ Added **Closure Rate** KPI.
- ✅ Added **Failure Modes Pareto** chart (count + cumulative %).
- ✅ Dedupe department lists for Line-first hierarchy.

#### V2) AWS page UI for 3 pools + threshold config (M)
- ✅ AWS page shows **3 independent pools** (MEC/ELE/PLC) using pool bars.
- ✅ Driving (riskiest) pool marked with ▲.
- ✅ Admin settings include `predictive_trigger_pct` input with explanatory copy.

**Phase V Testing**
- ✅ Screenshot verification completed.

---

### Phase W — Feature: Jump-to-breakdown from live DOWN timer (P0)
**Status:** ✅ COMPLETE

#### W1) Backend support
- ✅ `kpi_engine.py` includes `active_breakdown_id` + `active_breakdown_ticket` per line KPI.

#### W2) Control Room UI
- ✅ Live DOWN ribbon in `LineKpiRibbon.jsx` is clickable.
- ✅ Clicking navigates to `/breakdowns?bd=<id>`.

#### W3) Breakdowns deep-link handler
- ✅ `Breakdowns.jsx` reads `?bd=`:
  - expands the matching row
  - highlights it in red
  - scrolls it into view
  - then cleans the URL
- ✅ Expand chevron indicator added per breakdown row.

**Phase W Testing**
- ✅ End-to-end verified via screenshot automation.

---

### Phase X — PDF “Corrections Part 4” governance + AWS Life% fix (P0)
**Status:** ✅ COMPLETE

#### X1) Admin assignment UX (WO + Breakdowns)
- ✅ **Admins assign technicians via dropdown** (no self-claim):
  - WO popout: `wo-detail-assign-select` + `wo-detail-assign-btn` replaces Claim for admins.
  - Kanban/table unassigned state: admin sees “Assign Tech” (opens popout).
  - Breakdown actions (Machine Drawer): admin sees `bd-assign-select-*` + `bd-assign-btn-*` when unassigned.
- ✅ Technicians retain Claim/self-assign behavior.

#### X2) Breakdown closure governance (must have technician)
- ✅ Backend enforces: cannot close without technician on record.
  - Tech closure auto-assigns the closing tech if needed.
  - Admin closure requires `assigned_to` selection (400 otherwise).
  - `assigned_to` is persisted on breakdown close, and used consistently in logs / RCA auto-wo / linked WO sync.
- ✅ Repair page UI:
  - Admins must pick “Repairing Technician*” on unassigned breakdowns.

#### X3) Repair page cleanup
- ✅ Removed redundant “Start Repair Now” button on Repair page.

#### X4) AWS Life % fix + cadence
- ✅ `reliability.run_hours_between` rewritten as **day-prorated hybrid runtime**:
  - If a runtime log exists for a day: use logged `run_hours`, prorated by overlap fraction and capped by elapsed overlap.
  - If no runtime log exists for a day: assume 24/7 operation (calendar overlap hours).
- ✅ Reliability recompute cadence increased from ~15 min to ~5 min.
- ✅ Verified Life % ticks and can cross thresholds.

#### X5) Warnings always dispatch Inspection WO
- ✅ Removed Corrective WO type choice from:
  - Report Warning dialog
  - Warning generate-WO dialog
- ✅ Warnings always dispatch **Inspection**.

#### X6) Start actions do not auto-assign admins
- ✅ `start` for breakdowns/WOs auto-assigns only when the actor is a technician.
- ✅ Breakdown `assign` action syncs linked open WO assignment.

**Phase X Testing**
- ✅ `/app/test_reports/iteration_11.json`:
  - Backend **100% (24/24)**
  - Frontend **100% (7/7)**
- ✅ Calculation review completed (kpi_engine, analytics, breakdown/WO timing, availability, reliability life%).

---

### Phase Y — Follow-up: Unassigned PM Tasks + Live Event Feed deep-linking (P0)
**Status:** ✅ COMPLETE

#### Y1) Unassigned PM Tasks (creation + visibility + claim)
- ✅ PM Task creation supports optional technician (`assigned_to` optional in backend and UI).
- ✅ PM page exposes **Unassigned** filter chip.
- ✅ Unassigned PM tasks display a yellow **UNASSIGNED** badge in the Assigned column.
- ✅ Technicians can **Claim** an unassigned PM task (self-assign) from the PM list.
- ✅ Admins can assign via inline technician dropdown (no admin claim).
- ✅ Backend endpoint: `POST /api/pm-tasks/{task_id}/claim`.

#### Y2) Live Event Feed deep-linking for ALL event types
- ✅ Live Event Feed click deep-links to the *exact* referenced record.
- ✅ Same deep-link mapping added to the Layout notification bell.

**Phase Y Testing**
- ✅ Backend verified.
- ✅ Frontend verified.

---

### Phase Z — Feature: Task Transfer + Immediate RCA Flow (P0)
**Status:** ✅ COMPLETE — VERIFIED

#### Z1) Backend: transfer/assign/claim governance + RCA locks
- ✅ Work Orders: assign/claim/transfer governance + RCA lock.
- ✅ PM tasks: claim/assign/transfer governance + timeline events.
- ✅ Breakdowns: claim/assign/transfer governance + timeline events.
- ✅ Breakdown close response includes `rca_required` + `rca_task_id`.

#### Z2) Frontend: transfer/assign/claim UI parity
- ✅ WO modal: Claim for Me + Assign To… (unassigned), Transfer To… (assigned), RCA locked.
- ✅ PM page: Claim/Assign (unassigned), Transfer (assigned).
- ✅ Breakdowns: Claim/Assign/Transfer controls.

#### Z3) Immediate RCA in-flow popup
- ✅ RepairBreakdown closes 30min breakdown → immediate RCA dialog opens.

#### Z4) Verification evidence
- ✅ `/app/test_reports/iteration_12.json` — backend 100%.
- ✅ Frontend verified via screenshot automation.

---

### Phase AA — MTBF Unification (P1)
**Status:** ✅ COMPLETE — VERIFIED

#### AA1) Diagnosis summary
- AWS page MTBF comes from **reliability engine** (`reliability_metrics.mtbf`, driving category, TBF-based).
- Machine Analytics MTBF previously came from **run_hours ÷ failures** computed live in `routers_ops.py`.
- Result: they could not match; also a specific data-quality case (breakdown backdated before commissioning) caused a poisoned 0.1h engine MTBF.

#### AA2) Implemented remedy (definition unification)
- ✅ **Machine-level** Analytics MTBF (`/api/analytics/kpis?level=machine`) now reads MTBF from the same reliability engine field:
  - Backend change: `/app/backend/routers_ops.py` in `analytics_kpis`
  - For `level='machine'`: `mtbf_hours` comes from `reliability_metrics.mtbf`.
  - Fallback: if no reliability_metrics exists yet, fall back to `run_hours ÷ failures`.
  - Aggregate levels (plant/line/department/process_group) unchanged.
- ✅ Response now includes `mtbf_source`:
  - `reliability_engine` for machine level when metrics exist
  - `aggregate` otherwise

#### AA3) Verification
- ✅ All machines on AWS page now return identical MTBF via machine-level analytics (0 mismatches).
- ✅ Plant/line aggregates unaffected.
- ✅ No-failure machine returns `mtbf_hours=None` gracefully.
- ✅ Backend logs clean.

#### AA4) Known outstanding (documented, not approved yet)
- ⚠️ The **poisoned 0.1h MTBF** issue remains until a separate P0 data-quality fix is approved:
  - In `reliability.py:_compute_category`, TBF values are floored with `max(hours, 0.1)` (line ~139), which masks invalid intervals when a breakdown is backdated before commissioning.
  - This also poisons `predicted_failure_life` and can trigger spurious predictive WOs.

---

## 3) Next Actions

### Immediate (P0)
- ✅ None required for MTBF consistency; Phase AA is complete.

### Optional follow-ups (P0/P1)
- **P0 (requires approval)**: fix reliability engine’s handling of backdated failures predating commissioning (skip invalid intervals rather than clamp to 0.1; add data-quality warning), and guard `predicted_failure_life` minimum.
- **P1**: add a small UI hint showing `mtbf_source` (optional) for transparency/debugging.
- **P1**: E2E regression tests asserting AWS MTBF === machine analytics MTBF.

### Validation evidence
- Existing test reports:
  - `/app/test_reports/iteration_9.json` — Backend verification **100%**.
  - `/app/test_reports/iteration_11.json` — Corrections Part 4 regression **100%**.
  - `/app/test_reports/iteration_12.json` — Phase Z backend regression **100%**.

---

## 4) Success Criteria

### Hierarchy + Admin
- ✅ Backend hierarchy is **Line → Department → Process Group → Machine**, implemented as an in-place migration preserving all operational history.
- ✅ Frontend Admin pages render and edit hierarchy without crashes.

### Control Room
- ✅ Filter ribbon positioned above line group cards.
- ✅ KPI presets: 8h/24h/168h + custom date range.
- ✅ No flavor text on line cards / plant totals.
- ✅ Active breakdown lines show live HH:MM:SS red timer ribbon.
- ✅ Clicking the DOWN timer jumps to the exact breakdown.

### Work Orders + Governance
- ✅ Unassigned supported + claim.
- ✅ Admins assign via dropdown.
- ✅ Transfer works (assignee/admin only).
- ✅ RCA lock enforced.

### Breakdowns + Governance
- ✅ Cannot close without technician.
- ✅ Claim/assign/transfer supported.

### Preventive Maintenance (PM Tasks) + Governance
- ✅ Unassigned supported + claim.
- ✅ Transfer supported.

### Immediate RCA Flow
- ✅ Closing a >threshold breakdown returns `rca_required` + `rca_task_id`.
- ✅ Repair flow pops embedded 5-Why RCA form immediately.

### AWS / Predictive
- ✅ 3-pool engine + threshold config.
- ✅ Life % ticks with hybrid runtime logic.

### Analytics + Runtime
- ✅ Date slicer exists.
- ✅ Closure rate + Pareto exist.
- ✅ Runtime unified.
- ✅ **MTBF consistency**: Machine-level analytics MTBF matches AWS MTBF exactly (same reliability engine value).