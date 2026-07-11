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
  - Any technician can **self-assign/claim** an unassigned WO.
- **Admin-closure requirement is type-conditional**:
  - **Corrective + Inspection + AWS/Predictive** WOs: technician can close directly (no admin approval).
  - **Preventive (PM) + RCA** WOs: technician completes → `PENDING_ADMIN_CLOSURE` → admin closes.
- **AWS / Predictive Maintenance Engine** is per-category:
  - Track separate health/life pools per machine for **Mechanical / Electrical / PLC(Control)**.
  - Trigger threshold is **admin-configurable** (default 80%) via `predictive_trigger_pct`.
  - AWS-triggered WOs are a distinct type: **AWS/Predictive** (`wo_type='Predictive'`, `aws_category` set).

### Control Room KPI/range objectives
- Control Room line KPIs support presets **Shift=8h, Day=24h, Week=168h** plus a **custom date range** slicer.
- Control Room visual cleanup:
  - Remove “flavor/narrative text” from line cards and plant totals; keep KPIs only.
  - Add a live red breakdown timer ribbon (HH:MM:SS ticking) on any line card with an active breakdown.
  - **New:** Clicking the live DOWN timer ribbon **jumps to the exact breakdown** (deep-link).

### Navigation + productivity objectives
- **Universal “jump to Work Order” deep linking**:
  - Clicking a WO reference anywhere opens the **exact Work Order popout/modal** rather than a generic list.
  - Contract: `?wo=<id>` plus a global `openWorkOrder(id)`.
- **New:** **Universal “jump to Breakdown” deep linking** from Control Room:
  - Clicking a line’s live DOWN timer ribbon opens `/breakdowns?bd=<breakdown_id>`.
  - Breakdowns page expands + highlights + scrolls to the referenced breakdown, then cleans the URL.
- **Global “My Tasks” filter** for technicians across: Breakdowns, Work Orders (Kanban), PMs.
- **Fuzzy/typeahead search** on Report Breakdown form dropdowns for Area/Line and Machine.

### Analytics + runtime objectives
- Analytics supports a date range slicer applied to all KPIs/charts.
- Add closure-rate KPI + Pareto analysis.
- **Runtime module is the single source of truth**:
  - Default assumption: plant runs **24/7**, ticking in real time.
  - End-of-day override: once a line runtime log exists for a date, it becomes authoritative globally.

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
**Status:** ✅ COMPLETE *(technician-mandatory rule superseded: Unassigned WOs allowed universally)*

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
- ✅ `kpi_engine.py` now returns:
  - `active_breakdown_id`
  - `active_breakdown_ticket`
  alongside `active_breakdown_since` for each line.

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
- ✅ Claim action integrated (button shows when unassigned).
- ✅ Claim verified end-to-end as technician.

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

### Phase W — New Feature: Jump-to-breakdown from live DOWN timer (P0)
**Status:** ✅ COMPLETE

#### W1) Backend support
- ✅ `kpi_engine.py` now includes `active_breakdown_id` + `active_breakdown_ticket` per line KPI.

#### W2) Control Room UI
- ✅ Live DOWN ribbon in `LineKpiRibbon.jsx` is clickable.
- ✅ Clicking navigates to `/breakdowns?bd=<id>`.

#### W3) Breakdowns deep-link handler
- ✅ `Breakdowns.jsx` reads `?bd=`:
  - expands the matching row
  - highlights it in red
  - scrolls it into view
  - then cleans the URL
- ✅ Added a visible expand chevron indicator on each breakdown row (`data-testid=breakdown-expand-*`).

**Phase W Testing**
- ✅ End-to-end verified via screenshot automation.

---

## 3) Next Actions

### Immediate (P0)
- ✅ All major roadmap phases completed (Q/T/U/V/W).
- ✅ Test artifacts cleaned from DB (temporary test WOs and TEST-* hierarchy entries removed).

### Validation evidence (P0)
- Current test reports:
  - `/app/test_reports/iteration_9.json` — Backend verification **100%**.
  - `/app/test_reports/iteration_10.json` — Frontend automation report (contained false positives + real issues).
- Post-iteration fixes completed:
  - Dialog overlay interception resolved.
  - Fuzzy search interaction stabilized.
  - Breakdown expand affordance added.
  - Jump-to-breakdown from live DOWN timer shipped.

### Optional hardening / Refactor (P1)
- Consolidate hierarchy selectors and fuzzy pickers into shared hooks/components.
- Add E2E regression tests for deep-links:
  - `?wo=<id>` (WO modal)
  - `?bd=<id>` (Breakdowns expand + highlight)
- Add/verify MongoDB indexes for large plants if latency observed.

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
- ✅ **Clicking the DOWN timer jumps to the exact breakdown**.

### Work Orders + Governance
- ✅ Backend supports Unassigned WOs universally (including kiosk) + claim.
- ✅ Kanban shows UNASSIGNED.
- ✅ Techs can claim unassigned WOs via UI.
- ✅ Closure branching:
  - Corrective + Inspection + AWS/Predictive close directly by technician.
  - PM/RCA require admin closure.
- ✅ UI enforces/displays closure branching correctly.

### AWS / Predictive
- ✅ Backend per-category health pools (Mechanical/Electrical/PLC) computed independently.
- ✅ Backend threshold is admin-configurable.
- ✅ AWS page shows 3 pools + admin threshold setting.

### Navigation + Technician productivity
- ✅ Any WO reference deep-links into the exact WO popout.
- ✅ “My Tasks” filter exists across technician-accessible modules.
- ✅ Breakdown report Area/Line + Machine selectors have fuzzy/typeahead.
- ✅ Breakdown deep-link `?bd=` expands + highlights + scrolls.

### Analytics + Runtime
- ✅ Backend runtime is unified via `kpi_engine.py` and used by Control Room endpoints.
- ✅ Analytics has a date range slicer affecting all KPIs/charts.
- ✅ Closure rate KPI and Pareto chart exist.
- ✅ Runtime is a single source of truth (backend).
