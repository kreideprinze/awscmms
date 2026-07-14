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

- **PM Compliance KPI correctness objective (Phase AF, completed; tolerance update completed in Phase AG)**:
  - PM Compliance card must never render blank.
  - PM Compliance = **(Completed PM Tasks ÷ Scheduled PM Tasks) × 100**, scoped to the Analytics slicer and hierarchy.
  - Scheduled = completions within range + active pending tasks due by end-of-range cutoff (overdue backlog counts; future-dated does not).
  - Department/PG scopes resolve via machine-id sets because `pm_completions` does not store department/PG fields.
  - Card renders **0%** for 0 completed of N scheduled, and **N/A** when 0 scheduled.
  - **On-time definition (updated in Phase AG):** `pm_completions.on_time` uses a ± tolerance window based on `reminder_offset_days`.

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

- **Universal “jump to Red Tag” deep linking** (rename from Warning; Phase AH):
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
    - Red Tags (Warnings) → Warning detail dialog
    - PM Tasks → PM row highlight
    - Fallback → Machine drawer

- **Global “My Tasks” filter** for technicians across: Breakdowns, Work Orders (Kanban), PMs.
- **Fuzzy/typeahead search** on Report Breakdown form dropdowns for Area/Line and Machine.
- **Red Tags (Warnings) are observation-only** and **always dispatch an Inspection WO** (no Corrective option).

### UX + Security objectives (NEW — Phase AH)
- **Mobile-friendly login & public kiosk UX**:
  - Login card fully responsive on phone widths (no horizontal scroll, tap-friendly controls, legible without zoom).
  - Remove the dev/demo **default-credentials hint block** from the login page.
  - Keep public entry points (Report Breakdown + Report Red Tag) visible on login page.
  - Make public kiosk forms (Report Breakdown / Report Red Tag) mobile-friendly too.

- **Terminology + icon consistency**:
  - Rename user-facing “Warning” → **“Red Tag”** everywhere.
  - Keep **existing yellow theme** for this feature (do not change to red).
  - Swap the Warning icon (exclamation) to a **Tag** icon everywhere it appears.

### Deployment objectives (NEW — Phase AH)
- Produce a **single-script, one-step deployment** for Ubuntu Server (22.04/24.04 LTS), LAN-only.
  - Nginx on **port 80** serving built frontend.
  - Reverse proxy `/api` to backend on `127.0.0.1:8001`.
  - MongoDB 7.0 installed via apt.
  - Backend runs as a **systemd service** (auto-start, auto-restart).
  - Install path: `/opt/factory-ops`.
  - Script is **idempotent where reasonable** and logs each stage clearly.

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
**Status:** ✅ COMPLETE *(workflow rules updated/superseded by newer governance rules; terminology will be renamed in Phase AH)*

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

*(Phase AB details unchanged; runtime model is single source of truth.)*

---

### Phase AC — Assignment Enforcement + Closure Attribution (P0)
**Status:** ✅ COMPLETE — VERIFIED

---

### Phase AD — Mandatory-field Validation Pack + Pareto Correction (P0)
**Status:** ✅ COMPLETE — VERIFIED

---

### Phase AE — Analytics Pareto regrouped MACHINE-WISE (P0 amendment)
**Status:** ✅ COMPLETE — VERIFIED

---

### Phase AF — Bugfix: PM Compliance KPI blank card (P0)
**Status:** ✅ COMPLETE — VERIFIED *(superseded by Phase AG tolerance update for `on_time` semantics)*

---

### Phase AG — AWS strict category filter + PM on-time tolerance + Analytics Time Utilization donut (P0)
**Status:** ✅ COMPLETE — VERIFIED

- ✅ AWS category filter now strictly hides other pools and recalculates KPIs from the selected pool.
- ✅ PM completion `on_time` uses ± reminder offset window + admin backfill endpoint exists.
- ✅ Analytics Time Utilization donut added + backend aggregation added.
- ✅ Testing: `/app/test_reports/iteration_14.json`.

---

### Phase AH — Mobile login cleanup + single-script deployment + “Warning”→“Red Tag” rename (P0)
**Status:** ⏳ NOT STARTED (user confirmed requirements)

#### AH1) Mobile-responsive Login page + remove default credentials block
- **Frontend files to inspect:**
  - Login page component (e.g. `/app/frontend/src/pages/Login.jsx` or wherever the login route renders).
  - Any shared auth layout components.
- Implement:
  - Responsive layout for ~360px width:
    - No horizontal scroll
    - Inputs/buttons ≥44px height or equivalent tap target
    - Text legible without browser zoom
    - Avoid fixed widths; use `max-w`, `w-full`, responsive padding.
  - Remove the **default credentials** help block entirely.
  - Keep public entry points: **Report Breakdown** and **Report Red Tag**.
- Testing:
  - Frontend: emulate phone viewport; verify no scroll-x; all CTA buttons visible.

#### AH2) Mobile-friendly public kiosk report forms (Breakdown + Red Tag)
- **Frontend files to inspect:**
  - Report Breakdown page
  - Report Warning/Red Tag page
- Implement:
  - Responsive form fields/selects and submit buttons.
  - Ensure dropdowns/search fields are usable on mobile.
  - Maintain no-login requirement.
- Testing:
  - Frontend: phone viewport screenshot + basic submission flow.

#### AH3) Rename “Warning” → “Red Tag” everywhere (UI + new backend strings)
- **Constraints:**
  - Behavior unchanged (non-downtime; auto-generates Inspection WO; no breakdown).
  - Keep existing **yellow theme**.
  - Replace warning/exclamation icon with a **Tag** icon.
  - Leave historical DB text as-is.
  - Keep API routes/internal field names unchanged.
- **Frontend sweep:**
  - Sidebar label
  - Buttons (Report Warning → Report Red Tag)
  - Filters/tabs
  - Badges/tags
  - Live Event Feed labels
  - Notifications UI labels
  - Any helper text / tooltips
- **Backend sweep (newly generated strings only):**
  - Notification titles/bodies
  - Timeline event titles
  - Work order titles/descriptions that mention warnings
- Testing:
  - Frontend: global search to ensure “Warning” no longer appears in user-facing UI.
  - Backend: trigger a new warning/red-tag creation and verify strings.

#### AH4) Single-script deployment (`/app/deploy.sh`)
- Create `/app/deploy.sh` that performs (idempotently where possible):
  1. Preconditions checks (Ubuntu 22.04/24.04, root, ports 80/443 availability)
  2. Install system packages: nginx, mongodb-org (7.0), python3-venv, nodejs (LTS), build essentials
  3. Create deploy user/group and `/opt/factory-ops`
  4. Pull/copy app source (assumes script run inside repo; copies to `/opt/factory-ops/current`)
  5. Backend:
     - create venv, install requirements
     - write `.env`/settings file(s)
     - install systemd unit `factory-ops-backend.service` listening on 127.0.0.1:8001
  6. MongoDB:
     - start/enable mongod
     - create DB and ensure indexes
     - run seeding: only if seed marker/collections empty
  7. Frontend:
     - `npm ci`
     - build (`npm run build`)
     - place build output at `/var/www/factory-ops` or `/opt/factory-ops/www`
  8. Nginx:
     - site config to serve static frontend and proxy `/api` to backend
     - `nginx -t` then reload
  9. Post-checks:
     - curl `/api/health` (or equivalent)
     - print final URL and credentials note (do **not** print passwords)
- Script UX:
  - Clear stage headers and success/failure logging
  - Safe re-run behavior (do not clobber existing configs without backup)
- Documentation:
  - Prerequisites, ports, and configuration knobs included as comments at top.

#### AH5) Phase AH verification
- Create test report: `/app/test_reports/iteration_15.json`
- Verify:
  - Login page mobile layout OK; no credential hint shown.
  - Public Breakdown/Red Tag forms mobile layout OK.
  - “Red Tag” terminology and Tag icon consistent.
  - Deployment script runs through on a clean Ubuntu VM (documented manual validation steps).

---

## 3) Next Actions

### P0 (Active)
- **Phase AH** (mobile login + single-script deployment + Red Tag rename): implement AH1–AH5.

### P0 (Pending approval)
- **Reliability data-quality guard**: prevent breakdown start-times from predating a machine’s `commissioned_at` (or otherwise ignore invalid negative TBF intervals) to avoid Weibull/MTBF poisoning.

### P1
- UI hint for `mtbf_source` (show whether MTBF is from reliability engine vs aggregate).
- E2E regression test asserting AWS MTBF == machine analytics MTBF.

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
- ✅ **AWS category filter strictness (Phase AG)**
  - Selecting **Mechanical/Electrical/PLC** hides other pools entirely.
  - AWS KPI cards recalc using **only the selected pool**.
  - “All Pools” preserves blended behavior.

### Analytics + Runtime
- ✅ Date slicer exists.
- ✅ Closure rate + Pareto exist.
- ✅ Pareto plots **downtime** and groups **by Machine**.
- ✅ PM Compliance KPI is non-blank and correct (Completed ÷ Scheduled × 100) across all scopes.
- ✅ **PM on-time tolerance (Phase AG)**
  - New completions compute `pm_completions.on_time` using `[due − offset, due + offset]`.
  - Historical `pm_completions.on_time` can be recomputed via admin backfill endpoint.
- ✅ Runtime is single source of truth.
- ✅ MTBF consistency: Machine-level analytics MTBF matches AWS MTBF.
- ✅ **Time Utilization donut (Phase AG)**
  - Analytics shows donut/pie minutes by AWS/Predictive, PM/Preventive, Breakdown/Corrective.
  - Respects date slicer + hierarchy scope.
  - Handles empty ranges with explicit “No maintenance time logged…” state.

### NEW (Phase AH)
- ⏳ **Mobile login + public kiosk UX**
  - Login page is fully usable on phone screens; no credential hint block.
  - Public Report Breakdown + Report Red Tag remain accessible from login.
  - Public forms are mobile-friendly.
- ⏳ **Red Tag rename + Tag icon**
  - No user-facing “Warning” text remains; “Red Tag” used consistently.
  - Yellow theme preserved; Tag icon used everywhere.
- ⏳ **Single-script deployment**
  - `/app/deploy.sh` performs one-step install + seed + build + service setup + nginx reverse proxy.
  - Safe to re-run (idempotent where reasonable) and logs each stage clearly.
