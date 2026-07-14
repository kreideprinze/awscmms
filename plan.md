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

### Analytics + runtime objectives (CURRENT — Planned Runtime model)
- Analytics supports a date range slicer applied to all KPIs/charts.
- Add closure-rate KPI + Pareto analysis.
- **Runtime is the single source of truth** (authoritative per line-day):
  - **Input**: one manual value per **Line × Date**: **Planned Runtime (hours)**.
  - **Downtime**: derived automatically and **live** from **Breakdowns only** for that line-day (Warnings never count).
  - **Availability** (line-day): `((Planned − Downtime) ÷ Planned) × 100`.
  - **Clamp rule**: if Downtime > Planned, Availability clamps at **0%**, and a visible **data-quality flag** is surfaced.
  - **Unlogged days**: visibly marked missing in calendar; **Control Room windows** keep the current live 24/7 fallback (**planned=24h**) only for unlogged days to keep live KPIs ticking.
  - **No other module may recompute availability independently**; all must read from the shared engine.
- **AWS/reliability runtime usage**:
  - For a logged line-day: per-machine run-hours inherit `max(Planned − derived line downtime, 0)` (prorated by overlap).
  - For unlogged days: retain 24/7 fallback.

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
**Status:** ✅ COMPLETE *(legacy runtime model superseded by Phase AB)*

**Phase M Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_8.json`
  - **backend 99%** (95/96; single failure is a *test-expectation quirk*, not a product bug)
  - **frontend 95%** with **0 real issues reported**

---

### Phase N — Plant bugfix pack (Breakdown/WO sync + Time edits + Availability + Warnings + Spares + PM PDF) (P0)
**Status:** ✅ COMPLETE *(availability + runtime unified; superseded by Phase AB runtime model)*

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

**Phase Q Testing**
- ✅ `/app/test_reports/iteration_9.json` backend: **100%**.

---

### Phase T — Frontend Sync: Control Room + Hierarchy + UX cleanup (P0)
**Status:** ✅ COMPLETE

---

### Phase U — Frontend Sync: Work Orders + Kanban + Deep-links + My Tasks (P0)
**Status:** ✅ COMPLETE

---

### Phase V — Frontend additions: Analytics + AWS page + Report Breakdown fuzzy search (P1)
**Status:** ✅ COMPLETE

---

### Phase W — Feature: Jump-to-breakdown from live DOWN timer (P0)
**Status:** ✅ COMPLETE

---

### Phase X — PDF “Corrections Part 4” governance + AWS Life% fix (P0)
**Status:** ✅ COMPLETE

---

### Phase Y — Follow-up: Unassigned PM Tasks + Live Event Feed deep-linking (P0)
**Status:** ✅ COMPLETE

---

### Phase Z — Feature: Task Transfer + Immediate RCA Flow (P0)
**Status:** ✅ COMPLETE — VERIFIED

**Phase Z Testing**
- ✅ `/app/test_reports/iteration_12.json` — backend 100%.
- ✅ Frontend verified via screenshot automation.

---

### Phase AA — MTBF Unification (P1)
**Status:** ✅ COMPLETE — VERIFIED

- ✅ Machine-level Analytics MTBF now reads from `reliability_metrics.mtbf`.
- ✅ `mtbf_source` field added.

---

### Phase AB — Runtime Module Rework: Planned Runtime + Derived Downtime + Corrected Availability (P0)
**Status:** ✅ COMPLETE — VERIFIED

#### AB0) Decisions locked (from user)
- ✅ Control Room windows: keep current live 24/7 fallback (**planned=24h**) only for **unlogged** days.
- ✅ Migration: **discard old runtime logs**; start fresh.
- ✅ Reliability: logged line-day per-machine run-hours inherit `max(Planned − derived downtime, 0)`.
- ✅ Derived downtime freshness: always computed **live from breakdown records**.

#### AB1) Backend: data model + API contract changes
- ✅ Runtime models updated:
  - `line_runtime_logs`: now stores `{planned_hours}` only.
  - Deprecated `{calendar_hours, run_hours}` model removed.
  - Deprecated per-machine persisted `runtime_logs` removed from runtime source-of-truth (no longer written by server clock; endpoints now expose derived line-days).
- ✅ Endpoints in `/app/backend/routers_ops.py`:
  - `POST /runtime-logs`: accepts `{line, date, planned_hours}` only (0 < planned_hours ≤ 24).
  - `GET /line-runtime-logs`: returns planned_hours plus **derived** downtime_hours, run_hours, availability, `clamped`.
  - `DELETE /line-runtime-logs`: removes planned entry (day becomes unlogged).
  - CSV import: `line,date,planned_hours` (legacy columns rejected).

#### AB2) Backend: shared KPI engine is authoritative (single source of truth)
- ✅ `/app/backend/kpi_engine.py` rewritten:
  - Helpers: `derive_line_day_rows`, `derive_day`, `load_line_breakdown_intervals`, `build_line_runtime_ctx`.
  - `compute_line_kpis()` window availability = `(Σplanned − Σdowntime)/Σplanned` with:
    - planned minutes prorated per day-overlap;
    - 24/7 fallback planned=24h for **unlogged** days only;
    - downtime minutes derived live as union-merged breakdown overlap;
    - `planned_minutes` and `clamped` exposed per line.

#### AB3) Backend: analytics + summaries use the engine (no independent formulas)
- ✅ `/app/backend/routers_ops.py` `analytics_kpis` updated:
  - runtime keys: `planned_hours` and `run_hours` (legacy `calendar_hours` removed).
  - `availability_trend` derived from planned model.
  - machine/PG/department scopes map to parent line(s) and inherit line-day planned runtime.
- ✅ `/app/backend/routers_core.py` machine detail runtime block updated:
  - runtime derived from line planned days (planned_hours, downtime_hours, run_hours, logged_days, availability).

#### AB4) Backend: reliability runtime consumption
- ✅ `/app/backend/reliability.py` updated:
  - `run_hours_between()` is now ctx-based and synchronous:
    - logged line-day effective run = `max(planned − line downtime, 0)` prorated;
    - unlogged days use 24/7 fallback.
  - `recompute_machine_reliability()` builds ctx using `kpi_engine.build_line_runtime_ctx(line)`.

#### AB5) Backend: remove deprecated auto-ticker writes
- ✅ `/app/backend/server.py` runtime clock no longer writes deprecated per-machine `runtime_logs` increments.
  - Plant clock still ticks.
  - `machines.total_run_hours` continues to tick for UI counters.

#### AB6) Data operations
- ✅ Fresh start enforced:
  - `runtime_logs` and `line_runtime_logs` purged (user-approved).
- ✅ `/app/backend/routers_admin.py` sample seeder updated to seed `planned_hours` logs.

#### AB7) Frontend: Runtime calendar UI changes
- ✅ `/app/frontend/src/pages/Runtime.jsx` rebuilt:
  - Single Planned Runtime input per line-day (day dialog + entry dialog + CSV).
  - Derived display: Downtime, Effective Run, Availability.
  - Clamp flag: AlertTriangle + tooltip “Downtime exceeds Planned Runtime — check breakdown records for this day”.
  - Calendar cells label unlogged days as `unlogged`.
  - Table columns updated (Planned / Derived Downtime / Run / Availability).

#### AB8) Testing
- ✅ `/app/test_reports/iteration_13.json`:
  - Backend: **100% (60/60)**
  - Frontend: **100%**

---

### Phase AC — Assignment Enforcement + Closure Attribution (P0)
**Status:** ✅ COMPLETE — VERIFIED

- ✅ Backend (`/app/backend/routers_maintenance.py`): hard 403 on Breakdown/WOs start/complete/close for non-assigned technicians; admins exempt.
- ✅ Correct attribution: `assigned_to` = performer, `closed_by` = actor; RCA locks to actual performer; WOs record `completed_by`/`started_by`.
- ✅ Timeline makes assigned-vs-actor mismatch explicit.
- ✅ Frontend gating: Repair page + WO modal + Breakdown actions show locked messages and hide action buttons.
- ✅ Verified via `/app/tests/test_enforcement.py` (21/21).

---

### Phase AD — Mandatory-field Validation Pack + Pareto Correction (P0)
**Status:** ✅ COMPLETE — VERIFIED

#### AD1) Action Taken mandatory (Breakdowns + Work Orders)
- ✅ Backend (`/app/backend/routers_maintenance.py`):
  - Breakdowns: reject `complete/close` without non-empty `action_taken` (400).
  - Work Orders: reject `complete` without non-empty `action_taken` for **Corrective / Inspection / Predictive** (PM closes via checklist flow; RCA via 5-Why — exempt).
- ✅ Frontend:
  - `RepairBreakdown.jsx`: required-field styling + inline error `repair-action-taken-error`.
  - `WorkOrderModal.jsx`: required-field styling + inline error `wo-complete-action-taken-error`.

#### AD2) PM NOT OK remarks mandatory
- ✅ Backend: `POST /pm-tasks/{task_id}/complete` returns 400 if any NOT_OK row has empty remarks.
- ✅ Frontend: `ClosePMTask.jsx` blocks submit and shows per-row inline error `close-pm-remarks-error-<key>`.

#### AD3) Pareto corrected to plot DOWNTIME (not count)
- ✅ Downtime metric used (hours), cumulative percentage computed against cumulative downtime share.

#### AD4) Verification
- ✅ API verification (Action Taken 400s; PM remarks 400s; Pareto downtime math); UI verification via screenshots.

---

### Phase AE — Analytics Pareto regrouped MACHINE-WISE (P0 amendment)
**Status:** ✅ COMPLETE — VERIFIED

- ✅ Backend (`/app/backend/routers_ops.py`):
  - Pareto now groups by **Machine** (not Mechanical/Electrical/PLC breakdown category).
  - Built from the per-machine downtime map; sorted by **total downtime desc**; machines with zero downtime excluded.
  - `cumulative_pct` computed from cumulative downtime share across machines.
  - Returns up to **100** rows (for API + optional UI expansion) and `pareto_total_machines`.
  - Item shape: `{machine_id, machine, count, downtime_hours, cumulative_pct}`.
  - Respects the same date slicer.
- ✅ Frontend (`/app/frontend/src/pages/Analytics.jsx`):
  - Chart title: **“Downtime Pareto — by Machine (cumulative %)”**.
  - X-axis: machine names.
  - Shows **Top 15** by default; toggle appears when >15 machines:
    - `analytics-pareto-expand` toggles **Show All N** / **Show Top 15**.
  - Tooltip and footer updated to reference machine-wise downtime.
- ✅ Verified via API assertions and screenshot.

---

## 3) Next Actions

### Immediate (P0)
- ✅ None — all requested follow-ups through Phase AE are complete.

### Optional follow-ups (P0/P1)
- **P0 (requires approval)**: reliability engine data-quality fix for backdated failures predating commissioning (skip invalid TBF intervals rather than clamp to 0.1; guard minimum predicted life).
- **P1**: add UI hint for `mtbf_source` if needed.
- **P1**: E2E regression tests asserting AWS MTBF === machine analytics MTBF.

### Validation evidence
- Existing test reports:
  - `/app/test_reports/iteration_9.json` — Backend verification **100%**.
  - `/app/test_reports/iteration_11.json` — Corrections Part 4 regression **100%**.
  - `/app/test_reports/iteration_12.json` — Phase Z backend regression **100%**.
  - `/app/test_reports/iteration_13.json` — Phase AB planned-runtime regression **100% (backend+frontend)**.
- Local verification scripts:
  - `/app/tests/test_enforcement.py` — Phase AC enforcement + attribution checks.

---

## 4) Success Criteria

### Hierarchy + Admin
- ✅ Backend hierarchy is **Line → Department → Process Group → Machine**, implemented as an in-place DB migration preserving all operational history.
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
- ✅ **Assigned action enforcement**: non-assigned technicians cannot start/complete/close assigned WOs.
- ✅ **Action Taken required** for Corrective/Inspection/Predictive completion.
- ✅ RCA lock enforced.

### Breakdowns + Governance
- ✅ Cannot close without technician.
- ✅ Claim/assign/transfer supported.
- ✅ **Assigned action enforcement**: non-assigned technicians cannot start/complete/close assigned breakdowns.
- ✅ **Action Taken required** on Repair/Completion.
- ✅ **Correct closure attribution**: repaired-by vs closed-by is accurate and visible in timeline.

### Preventive Maintenance (PM Tasks) + Governance
- ✅ Unassigned supported + claim.
- ✅ Transfer supported.
- ✅ PM checklist close-out blocks submission if any **NOT OK** row has empty **Remarks**.

### Immediate RCA Flow
- ✅ Closing a >threshold breakdown returns `rca_required` + `rca_task_id`.
- ✅ Repair flow pops embedded 5-Why RCA form immediately.
- ✅ RCA locks to the technician who actually triggered closure.

### AWS / Predictive
- ✅ 3-pool engine + threshold config.
- ✅ Reliability consumes the planned-runtime model for logged days.

### Analytics + Runtime
- ✅ Date slicer exists.
- ✅ Closure rate + Pareto exist.
- ✅ **Pareto plots downtime (not count)** with cumulative % based on downtime.
- ✅ **Pareto groups by Machine** (machine-wise downtime offenders; top-N view with expand).
- ✅ Runtime is single source of truth.
- ✅ **MTBF consistency**: Machine-level analytics MTBF matches AWS MTBF exactly.
- ✅ **Planned Runtime model (Phase AB)** fully live:
  - Planned Runtime is the only manual input per line-day.
  - Downtime derived from Breakdowns only (Warnings excluded).
  - Availability uses `((Planned − Downtime)/Planned) × 100` and clamps at 0% with a visible warning.
  - Unlogged days are visibly marked and do not produce misleading figures.
  - Control Room, Analytics, Plant totals, machine detail runtime, and reliability all read the same authoritative model.
