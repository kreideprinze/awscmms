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

### NEW Objectives (Phase AI — current)
- **RCA rejection loop**: Admins can reject a submitted RCA with a reason; RCA reopens and returns to the same locked technician; rejection/resubmission is tracked in Timeline + notifications.
- **Analytics: Breakdown Type Pie**: Add breakdown-type pie chart (Mechanical/Electrical/PLC) with toggle **Count vs Downtime-weighted**, respecting existing slicers.
- **Admin-only Technician Leaderboard**: Extend Technician Analytics with leaderboard, metric tabs + **Overall composite** toggle, and technician drill-down card.
- **Mid-repair Work Order handoff**: Allow transfer of **IN_PROGRESS** work orders with mandatory **Pass-On Note**, multiple handoffs, timeline/audit trail, and ensure MTTR/MTBF/AWS integrity.

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

---

### Phase AI — RCA Rejection + Breakdown-Type Pie + Technician Leaderboard + Mid-repair Handoff (P0)
**Status:** ⏳ NOT STARTED

#### AI1) Admin can reject a submitted 5-Why RCA
**Goal:** Add a Reject action for Admins reviewing RCA work orders.

**Backend (primary):** `/app/backend/routers_maintenance.py`
- Add new RCA lifecycle states or flags (recommended minimal change):
  - `status` remains `PENDING_ADMIN_CLOSURE` when technician submits.
  - On reject: set `status='IN_PROGRESS'` (or `ASSIGNED`) and keep `assigned_to` unchanged.
  - Add fields:
    - `rca_rejected: bool`
    - `rca_rejection_reason: str`
    - `rca_rejected_at: iso`
    - `rca_rejected_by: username`
    - optional: `rca_resubmissions_count`
- Add endpoint: `POST /api/work-orders/{wo_id}/rca-reject` (admin-only)
  - Requires non-empty `reason`.
  - Verifies WO is `wo_type='RCA'` and `status='PENDING_ADMIN_CLOSURE'`.
  - Writes rejection fields + returns updated WO.
  - Timeline event: `rca_rejected` (“RCA rejected by Admin — reason: …”).
  - Notification to the assigned technician (targeted): “RCA rejected — resubmission required”.

**Frontend:** `/app/frontend/src/pages/RcaForm.jsx` and admin WO closure UX
- In admin review area for RCA:
  - Add **Reject** button next to Approve/Close.
  - Prompt for rejection reason (modal or inline textarea).
  - On success: WO returns to technician’s task list.
- Technician reopens RCA:
  - **Prefill previous answers** for editing/resubmission (choice 2a).
  - Add “Rejected by Admin” banner with reason.

**Testing:**
- Admin rejects → WO status back to technician, reason saved.
- Technician resubmits → status back to `PENDING_ADMIN_CLOSURE`.
- Timeline shows both events; technician receives notification.

#### AI2) Breakdown-type pie chart in Analytics (count + downtime toggle)
**Backend:** `/app/backend/routers_ops.py` (`GET /api/analytics/kpis`)
- Add aggregation for breakdowns in current scope/date range:
  - buckets: `MECHANICAL`, `ELECTRICAL`, `CONTROL_PLC`
  - return both:
    - `breakdown_type_share_count: [{type, count}]`
    - `breakdown_type_share_downtime: [{type, downtime_minutes}]`

**Frontend:** `/app/frontend/src/pages/Analytics.jsx`
- Add new Cyberpunk panel with pie chart.
- Toggle control: **Count / Downtime** (choice 1c).
- Tooltip: show value + percentage.
- Respect existing slicers (date range + hierarchy level/value).

**Testing:**
- With empty range → “No breakdowns in range”.
- With data → sums match KPI totals.

#### AI3) Technician Leaderboard + Technician drill-down card (Admin-only)
**Backend:** `/app/backend/routers_ops.py` (`GET /api/analytics/technicians`)
- Extend response:
  - `leaderboard` computed server-side.
  - Rankings by metric tabs:
    - Breakdowns Closed
    - Avg MTTR
    - PM Compliance
    - WO On-Time
  - Add **Overall composite** option (user request):
    - Provide normalized score formula (documented), e.g. weighted z-scores or min-max.
- Add endpoint for drill-down:
  - `GET /api/analytics/technicians/{username}` (admin-only)
  - returns detailed card stats:
    - breakdowns handled, breakdowns closed
    - avg MTTR
    - avg WO duration
    - PM count + compliance
    - RCA completion count
    - total hours

**Frontend:** `/app/frontend/src/pages/Analytics.jsx` (TechnicianAnalytics section)
- Add Leaderboard view:
  - Metric tabs + “Overall” toggle.
  - Click technician row → open Technician card panel/modal.
- Ensure entire section remains admin-only (already gated by backend; keep UI hide).

**Testing:**
- Non-admin gets 403.
- Leaderboard order changes per metric tab.
- Drill-down card matches list numbers.

#### AI4) Mid-repair Work Order handoff with Pass-On Notes
**Goal:** Allow transfer while `IN_PROGRESS` with mandatory pass-on note.

**Backend:** `/app/backend/routers_maintenance.py`
- Extend existing transfer endpoint to accept optional `pass_on_note`.
- Rule:
  - If WO status is `IN_PROGRESS`, `pass_on_note` is **required** (choice 4a).
  - If WO not yet started (OPEN/ASSIGNED), transfer remains as-is (note optional).
- Persist handoffs:
  - Add array field `handoffs: [{from,to,note,at,by}]` to work_orders.
  - Timeline event per handoff: “WO handed off from A → B” + note.
  - Notification to incoming technician.
- Integrity constraints:
  - Do **not** change `started_at` on handoff.
  - Do **not** touch breakdown start_time / downtime.
  - Do **not** trigger reliability/AWS reset logic (handoff is assignee-only change).

**Frontend:** Work order modal / transfer UI
- When transferring an IN_PROGRESS WO:
  - show required Pass-On Note textarea.
  - show history of previous handoffs.

**Testing:**
- Transfer IN_PROGRESS without note → 400.
- Multiple handoffs record multiple entries.
- Completion duration remains from original start to final completion.
- No duplicate AWS reset events.

#### AI5) Phase AI testing + report
- Create `/app/test_reports/iteration_16.json`.
- Run both backend + frontend verification.

---

## 3) Next Actions

### Current (P0)
- Implement Phase AI (AI1–AI5).

### P0 (Pending approval)
- Reliability data-quality guard: prevent breakdown start-times predating commissioned date.

### P1
- UI hint for `mtbf_source`.
- E2E regression test asserting AWS MTBF == machine analytics MTBF.

---

## 4) Success Criteria

### Existing (already satisfied)
- Governance rules, runtime model, AWS strict pool filtering, PM tolerance, Time Utilization, Red Tag rename, mobile login, deploy script.

### Phase AI (NEW)
- ✅ **RCA rejection**:
  - Admin can reject submitted RCA with reason.
  - RCA returns to locked technician; resubmission required with prefilled data.
  - Timeline + notification capture full cycle.
- ✅ **Analytics breakdown-type pie**:
  - Pie chart with toggle Count vs Downtime-weighted.
  - Respects date range + scope filters.
- ✅ **Technician Leaderboard (Admin-only)**:
  - Metric tabs + Overall toggle.
  - Drill-down technician card with detailed stats.
  - Technicians cannot view.
- ✅ **Mid-repair handoff**:
  - IN_PROGRESS transfer requires Pass-On Note.
  - Multiple handoffs stored + timeline.
  - MTTR/MTBF/AWS integrity preserved (no timer reset, no reliability side effects).