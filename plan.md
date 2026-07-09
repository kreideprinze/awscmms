# plan.md

## 1) Objectives
- Deliver a production-ready, LAN-only Factory Operations Platform (Digital Twin Control Room + CMMS + Reliability/AWS + Predictive + Analytics + Spares + Admin) that is **machine-centric** in every workflow.
- Ship **non-empty** on first boot: seed full hierarchy (Appendix A), machine layout positions, templates/rules, **default users** (admin/admin123, tech/tech123, operator/operator123), and realistic starter spares.
- Provide real-time **timeline + notifications** (WebSocket) and scalable MongoDB data model (indexes/pagination) to hit performance targets.
- Ensure Control Room UX is **bounded and usable**:
  - **No infinite zoom** behavior.
  - A **fixed/controlled canvas size** with **vertical scrolling** to view all machines.
- Ensure time references are unambiguous across operations:
  - Replace “plant runtime clock” display with **current actual wall-clock time** so users can cross-reference Breakdown/WO timestamps.
- Apply a coherent, app-wide **Cyberpunk 2077 HUD aesthetic** across *every module* (not just Control Room): dark charcoal base (not pure black), neon accents (cyan/magenta/yellow), monospace data typography, chamfered corners, scanlines, glow hovers, and subtle glitch/flicker where appropriate.

## 2) Implementation Steps

### Phase 1 — Core “Operational Loop” POC (Isolation) (WebSocket + eventing + derived machine state)
> Core = if this breaks, the system isn’t “live”: machine state aggregation + timeline/notifications + Digital Twin can’t be trusted.

**POC scope (no full UI, minimal pages/scripts):**
1. Backend skeleton: FastAPI + Motor + JWT scaffolding (JWT can be stubbed for POC routes if needed), WebSocket hub (single-worker constraint).
2. Minimal data model + seed subset: 1 dept/line/process group + 3 machines + default users.
3. Event pipeline: create a breakdown → emits timeline event + notification → updates machine “derived state” (status/health placeholders) → WebSocket broadcasts.
4. A minimal React page that:
   - lists the 3 machines
   - opens WS connection
   - shows live notifications and machine state changes

**Web search (best practices) before coding:**
- FastAPI WebSocket patterns with Motor and single-process broadcast hub; JWT over WS; avoiding blocking calls.

**Exit criteria:**
- From a script or minimal UI: create breakdown for a machine and see (a) timeline event persisted, (b) notification persisted, (c) WS push received, (d) machine card reflects updated indicator.

**User stories (Phase 1):**
1. As an Operator, I can see a minimal live machine list that updates without refresh when events occur.
2. As a Technician, I receive a real-time notification when a breakdown is created for my machine.
3. As an Admin, I can seed the system and confirm it never starts empty.
4. As an Admin, I can verify every significant action creates a timeline event.
5. As a user, I can refresh the page and still see the persisted events (not just in-memory WS messages).

---

### Phase 2 — V1 App Development (MVP, end-to-end usable)
**2.1 Data model + foundations**
- Implement Mongo collections per spec + counters for ticket numbers.
- Implement seed on first startup:
  - Full hierarchy (Appendix A) + machine layout positions
  - failure modes + report error codes
  - PM templates + runtime templates
  - reliability rules/settings + notification templates
  - default users + realistic spares + spare locations
- Implement RBAC (3 roles) + route guards (frontend) + API enforcement (backend).

**2.2 Control Room / Digital Twin (primary landing)**
- Dynamic layout renderer from hierarchy + machine positions (no hardcoded cards).
- Pan/zoom, search, filters; machine cards show Dept/Line/PG/Name/Status/Health/Runtime/Reliability.
- Machine Detail Drawer with tabs (MVP content per tab, but all tabs present): Overview, Reports, Breakdowns, Work Orders, PM Tasks, Analytics, Timeline, Notes, Documents (metadata only), Reliability, Spares.

**2.3 Maintenance modules (machine-centric flows)**
- Machine Reports + review/convert-to-breakdown flow.
- Machine Notes (timestamped).
- Breakdowns:
  - lifecycle OPEN→ASSIGNED→IN_PROGRESS→COMPLETED→CLOSED
  - downtime calc; enforce root-cause rule >30 min + auto follow-up task
  - consumed spares capture on close
- Work Orders:
  - types + lifecycle
  - completion triggers inventory transaction + usage log
- PM:
  - task definitions + scheduler to generate PM work orders
  - completion with checklist + spares consumption

**2.4 Timeline + Notifications (full)**
- Persist timeline events for all major actions; filter by type.
- WebSocket notifications for: reports, breakdowns, critical failures, WOs, PM due/overdue, reliability alerts, inspection recommendations.

**2.5 Runtime (manual + CSV import)**
- Admin UI for manual runtime log entry and CSV import with validation/preview.
- Runtime KPIs stored permanently; availability computed.

**2.6 One round of end-to-end testing (testing agent)**
- Validate core flows: seed → Control Room → drawer → report → convert → breakdown lifecycle → spares consumption → notifications → timeline → PM generation/completion → runtime log.

**User stories (Phase 2):**
1. As an Operator, I can start from the Control Room, search a machine, open its drawer, and submit a report in under 30 seconds.
2. As a Technician, I can take an assigned breakdown through all lifecycle stages and close it with action taken + spares used.
3. As an Admin, I can adjust machine layout positions and immediately see the Digital Twin re-render.
4. As a Technician, I can complete a PM task with checklist and see it logged on the machine timeline.
5. As an Admin, I can import runtime logs via CSV preview and see availability update in analytics.

---

### Phase 3 — Reliability/AWS + Predictive + Analytics (multi-level)
**3.1 Reliability metrics engine (non-ML)**
- MTBF/MTTR calculations start after first breakdown.
- Maturity levels:
  - L1: MTBF + operating hours since failure
  - L2: rolling/weighted MTBF + failure trend
  - L3 (5+): Weibull fit + hazard + reliability curve + failure probability
- Store reliability_metrics and weibull_models; incremental recompute on new events.

**3.2 Predictive engine**
- Prediction tiers: MTBF → weighted MTBF → Weibull.
- Health state bands (0–70/70–80/80–100/100%+).
- At ≥80%: create inspection flag + notification + suggested PM task (auto suggestions list).

**3.3 Analytics module**
- Hierarchy-level rollups: Machine/PG/Line/Dept/Plant.
- KPI dashboards + charts (Recharts): downtime/failure trends, PM compliance, availability.
- Add required indexes + pagination; cached rollups where needed.

**3.4 One round of end-to-end testing (testing agent)**
- Simulate breakdown history + runtime logs; verify level transitions, Weibull activation, predictive alerts, analytics correctness.

**User stories (Phase 3):**
1. As a Reliability user (Admin), after the first breakdown I can immediately see MTBF populated for the machine.
2. As a Technician, I can see a machine enter Watch/Inspection Due based on runtime vs predicted life.
3. As an Admin, I get an automatic inspection recommendation notification at ≥80% predicted life.
4. As a Plant user (Admin), I can view MTBF/MTTR/Availability rollups at line/department levels.
5. As a user, I can open a machine’s Reliability tab and see Weibull outputs once it reaches 5+ failures.

---

### Phase 4 — Spares/Inventory + Administration hardening + scale readiness
**4.1 Inventory module (SAP-centric)**
- spares_inventory master + spare_locations.
- Transaction ledger only (no direct edits): imports, adjustments, consumptions.
- CSV import modes Replace/Add/Subtract + simplified quantity_change with validation + preview.
- Machine recommended spares + Machine drawer Spares tab (recent usage, most consumed, history).
- Spare analytics dashboards (top 10, breakdown by month/machine/area/source).

**4.2 Administration module**
- Full CRUD for hierarchy + layout, users, templates, reliability settings, spare locations, branding/system settings.
- Audit logs for admin changes.

**4.3 Performance work**
- Add/verify indexes, cursor pagination, aggregation pipelines for rollups.
- WS backpressure/basic rate limiting; avoid N+1 queries in Control Room.

**4.4 One round of end-to-end testing (testing agent)**
- Validate consumption auto-decrements stock + transactions, CSV import preview correctness, admin CRUD integrity, large-list pagination.

**User stories (Phase 4):**
1. As an Admin, I can import a CSV stock adjustment and see a preview of all changes before applying.
2. As a Technician, when I record used spares on a breakdown close, inventory updates automatically and creates a transaction.
3. As an Admin, I can search inventory instantly by SAP code/name/location.
4. As an Admin, I can create/edit/retire spare locations without technicians changing the location list.
5. As a user, I can open a machine and see its most-consumed spares and recent usage history.

---

## 3) Next Actions
> Updated to reflect current status + the latest user requests.

### Phase A — Control Room fixes (P0)
1. **Remove infinite zoom** in the Control Room Digital Twin:
   - Constrain zoom to a sensible min/max (or disable zoom entirely if required).
   - Prevent “zoom till infinity” behavior.
2. **Fix the Control Room canvas sizing** so users can **scroll vertically** to see all machines:
   - Ensure the Digital Twin container uses a bounded height (viewport-based) and `overflow-y: auto`.
   - Ensure layout does not expand infinitely in a way that forces awkward scaling.
3. **Replace Plant Runtime display with current wall-clock time**:
   - Update the PlantClock component to show the current actual time (local plant time) and refresh every second.
   - Keep breakdown/report timestamps consistent and easy to cross-reference.

### Phase B — Cyberpunk 2077 UI audit & application across ALL modules (P0)
4. Screenshot & audit secondary modules:
   - `/work-orders`, `/pm`, `/runtime`, `/analytics`, `/aws`, `/inventory`, `/administration`.
5. Update all non-compliant tables/cards/forms:
   - dark charcoal base (avoid pure black)
   - neon cyan/magenta/yellow accents (avoid traffic-light status colors)
   - monospace/tabular numbers for KPI/table data
   - chamfered corners, scanlines, glow hover states, consistent HUD framing
   - consistent button/input styling (replace lingering default Shadcn styling where needed)

### Phase C — E2E test: Breakdown → auto-create Work Order (P1)
6. Create a Breakdown in UI with **auto-create work order** checked.
7. Verify:
   - Backend creates Corrective Work Order instantly
   - Status is **ASSIGNED** (and appears in Work Orders UI)
   - Breakdown record links to WO (and WO links back to Breakdown)

### Phase D — Full testing pass + fixes (P1)
8. Run testing agent pass (frontend screenshots + backend API checks).
9. Fix any regressions found (UI consistency, routing, schema mismatches, time display).
10. Produce updated test report.

## 4) Success Criteria
- First boot: system is fully seeded (hierarchy, users, templates, spares) and **not empty**.
- Control Room renders Digital Twin dynamically from hierarchy + layout positions.
- Control Room UX is bounded:
  - **No infinite zoom**.
  - Users can **scroll vertically** to reach all machines without uncontrolled scaling.
- App displays **current actual wall-clock time** prominently for cross-referencing timestamps.
- Real-time WS notifications and timeline eventing work end-to-end for key actions.
- Maintenance flows function: reports→review→convert, breakdown lifecycle, WO creation/assignment, PM generation/completion.
- **Breakdown auto-create WO flow** is verified end-to-end.
- Cyberpunk HUD aesthetic is consistent across **every** module (Control Room, Breakdowns, Work Orders, PM, Runtime, Analytics, AWS, Inventory, Admin).
- App remains responsive with pagination/indexes and avoids obvious degradation patterns.

---

## STATUS UPDATE (Current)
- Phase 1 POC: **COMPLETE** (WS hub + event pipeline + persistence)
- Phase 2 (Core app): **COMPLETE** — 194 machines seeded, Control Room Digital Twin, Machine Drawer (11 tabs), Reports/Breakdowns/WOs/PM, Timeline+WS Notifications
- Phase 3 (Reliability/Predictive/Analytics): **COMPLETE**
- Phase 4 (Spares/Admin): **COMPLETE**
- Recent completed work (latest iteration):
  - Seed script refactored to be idempotent with summary logging (`/app/backend/seed.py`) — **DONE**
  - Plant clock backend ticker integration — **DONE (but to be replaced in UI with wall-clock time display per latest request)**
  - Breakdown schema updated + backend auto-create work order logic — **DONE (E2E verification pending)**
  - New `ReportBreakdownDialog.jsx` built to spec — **DONE**
  - Control Room sorting/grouping + dynamic zoom limits attempted — **IN PROGRESS (must remove “infinite zoom” and enable vertical scroll per latest request)**
  - Cyberpunk global CSS + primary screens partially updated — **IN PROGRESS (needs audit across secondary modules)**
- Testing:
  - Prior testing_agent iteration_1 passed; **new targeted testing pending** for: Control Room scroll/zoom behavior, wall-clock time display, and Breakdown → auto-create WO flow.
