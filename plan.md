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
**Status:** ✅ COMPLETE — VERIFIED (`/app/test_reports/iteration_16.json` + live UI verification by main agent)

#### AI1) Admin can reject a submitted 5-Why RCA
**Status:** ✅ DONE

**Backend:** `/app/backend/routers_maintenance.py`
- Added `PUT /api/work-orders/{wo_id}/rca-reject` (admin-only)
  - Requires non-empty `reason`
  - Only for `wo_type='RCA'` and `status='PENDING_ADMIN_CLOSURE'`
  - Reopens to `status='IN_PROGRESS'` and keeps the same locked `assigned_to`
  - Stores `rca_rejection={reason,rejected_by,rejected_at}` + increments `rca_rejections_count`
  - Clears `completed_at`, `completed_by`, `duration_minutes` (so it must be completed again)
  - Logs timeline event `rca_rejected` and sends a warning severity notification
- Updated `PUT /api/work-orders/{wo_id}/rca` submission logic:
  - If resubmitting after rejection, clears `rca_rejection` and logs the event as **re-submitted**

**Frontend:**
- `/app/frontend/src/components/WorkOrderModal.jsx`
  - Added **Reject RCA** action for admins on `PENDING_ADMIN_CLOSURE` RCAs
  - Inline rejection reason form + disabled confirm until reason present
  - Added a visible **RCA Rejected** banner when `wo.rca_rejection` exists
- `/app/frontend/src/pages/RcaForm.jsx`
  - Added rejection banner with reason
  - Previous 5-Why answers stay **prefilled** (RCA content is retained)

**Testing:**
- Full reject → resubmit → complete → admin close cycle verified.

#### AI2) Breakdown-type pie chart in Analytics (count + downtime toggle)
**Status:** ✅ DONE

**Backend:** `/app/backend/routers_ops.py` (`GET /api/analytics/kpis`)
- Added `breakdown_types: [{type, count, downtime_minutes}]`
- Respects date range and hierarchy scope.

**Frontend:** `/app/frontend/src/pages/Analytics.jsx`
- Added **Breakdowns by Type** donut card (`analytics-breakdown-types`)
- Toggle: **Downtime / Count**
- Cyberpunk styling + empty-state for no data.

#### AI3) Technician Leaderboard + Technician drill-down card (Admin-only)
**Status:** ✅ DONE

**Backend:** `/app/backend/routers_ops.py` (`GET /api/analytics/technicians`, admin-only)
- Added:
  - `rca_completed`
  - `overall_score` (0–100) via min-max normalized composite of:
    - breakdowns resolved ↑
    - WOs completed ↑
    - avg repair minutes ↓ (inverted)
    - WO on-time ↑
    - PM compliance ↑

**Frontend:** `/app/frontend/src/pages/Analytics.jsx`
- Added leaderboard panel (`tech-leaderboard`) with metric tabs:
  - Overall / Breakdowns Closed / Best Avg MTTR / PM Compliance / WO On-Time
- Clicking a row opens the Technician Card modal (`tech-card-modal`)
- Clicking a table row also opens the same card.
- Section remains **admin-only** (`isAdmin && <TechnicianAnalytics />`).

#### AI4) Mid-repair Work Order handoff with Pass-On Notes
**Status:** ✅ DONE

**Backend:** `/app/backend/routers_maintenance.py`
- Extended models:
  - `WOUpdate.pass_on_note`
  - `BreakdownUpdate.pass_on_note`
- Enforced rule:
  - If transferring an **IN_PROGRESS** WO or breakdown, `pass_on_note` is **required** (400 otherwise).
  - Pre-start transfers (OPEN/ASSIGNED) remain unchanged (note optional).
- Stored handoff history:
  - Appends into `handoffs[] = [{from,to,note,at,by,mid_repair}]`
  - Timeline + notification include verb **“handed off mid-repair”** and Pass-On Note.
- Integrity:
  - `started_at` / `start_time` not modified
  - completion duration remains original start → final completion
  - no AWS/reliability resets triggered (handoff is assignee change only)

**Frontend:**
- `/app/frontend/src/components/Shared.jsx`
  - `TransferControl(requireNote)` shows Pass-On Note textarea and gates “Hand Off”.
- `/app/frontend/src/components/WorkOrderModal.jsx`
  - Requires note only when `wo.status==='IN_PROGRESS'`
  - Displays Pass-On Notes history (`wo-detail-handoffs`).
- `/app/frontend/src/components/MachineDrawer.jsx`
  - Breakdown transfer requires note when IN_PROGRESS.
- `/app/frontend/src/pages/RepairBreakdown.jsx`
  - Displays Pass-On Notes history (`repair-handoffs`).

#### AI5) Phase AI testing + report
**Status:** ✅ DONE
- Automated test report: `/app/test_reports/iteration_16.json` (backend 100%)
- Frontend verified by:
  - testing agent code-review
  - main agent live Playwright screenshots
- Test artifacts cleaned:
  - test breakdowns/WOs/RCAs deleted
  - machine statuses restored
  - reliability recomputed

---

## 3) Next Actions

### Current
- No P0 remaining from Phase AI.

### P0 (Pending approval)
- Reliability data-quality guard: prevent breakdown start-times predating commissioned date.

### P1
- UI hint for `mtbf_source`.
- E2E regression test asserting AWS MTBF == machine analytics MTBF.

---

## 4) Success Criteria

### Existing (already satisfied)
- Governance rules, runtime model, AWS strict pool filtering, PM tolerance, Time Utilization, Red Tag rename, mobile login, deploy script.

### Phase AI (now satisfied)
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
