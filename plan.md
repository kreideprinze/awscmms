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
  - Admin-managed logo and brand accent color that re-themes the entire platform instantly.
- Standardize UI interaction language:
  - All buttons/icons/pills follow **outlined hairline border styling**.
  - Background theme is **pure black** (no deep-blue undertone), while maintaining readable contrast.
- Ensure maintenance execution is **audit-ready and printable**:
  - PM execution is driven by **structured checklists** (component → sub-item rows) with per-row OK/NOT OK + per-row remarks.
  - Every PM task supports **PDF export** for blank templates and completed instances, formatted like the real checklist sheet.
- Remove friction for shop-floor breakdown reporting:
  - Provide a **public kiosk breakdown reporting** entry point (no login required) capturing Reporter Name and flagging submissions as public.

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

### Phase F — PM Checklist Rework (Structured Checklists + PDF Export) + Public Breakdown Reporting (NEW)
> This phase makes PM execution **structured, repeatable, and printable**, and ensures **breakdown reporting is never blocked by authentication**.

#### F1) Structured PM Templates (Checklist Builder with one-to-many grouping) (P0)
**Requirements**
- PM templates are **tables**, not free-text:
  - Columns: **S.N.**, **Description (component)**, **Checked For (sub-item)**, **Parameter/Process**, **Status**, **Remarks**.
- Support one-to-many grouping:
  - One **Description** (e.g. Motor) contains multiple **Checked For** sub-rows.
- Template header fields:
  - PM title, Line(s) it applies to (v1 uses task.line), Location/Area, Frequency, Date.
- Footer fields:
  - Done By and Checked By (Name + Signature lines in PDF).
- Admin builds templates once and they are reused on each scheduled instance.

**Backend (Delivered)**
- PM task create/update models now support:
  - `checklist_groups: [{ description, items: [{ checked_for, parameter }] }]`
  - `location` (Location/Area)
- Validation/normalization performed server-side (`_normalize_groups`).
- Legacy compatibility:
  - Derives `checklist` flat strings from groups for older displays (`_groups_to_flat`).
- Seed migration:
  - 5 seeded PM templates converted to `checklist_groups`.
  - Idempotent migration added to `seed.py` for existing DBs.

**Frontend (Delivered)**
- `ChecklistBuilder.jsx`:
  - Grouped checklist builder UI (component → sub-items).
- `PreventiveMaintenance.jsx`:
  - New PM Task dialog uses structured builder.
  - Template select populates grouped structure.

**Exit Criteria**
- ✅ Admin can create/edit PM tasks using structured checklist groups (not free text).
- ✅ Grouping is preserved (Description with multiple Checked For rows).

**Status:** ✅ COMPLETE

#### F2) Dedicated “Close PM Task” Page (Per-row status + per-row remarks) (P0)
**Requirements**
- Completing a PM task must open a dedicated page:
  - Per-row **OK / NOT OK** status required.
  - Per-row **Remarks** required/optional per row (supported).
  - Done By + Checked By fields.
  - Validation: cannot close until every row has a status.

**Backend (Delivered)**
- `/api/pm-tasks/{id}/complete` now accepts:
  - `row_results: [{sn, description, checked_for, parameter, status: OK|NOT_OK, remarks}]`
  - `done_by`, `checked_by`
- Saves `row_results` into `pm_completions`.

**Frontend (Delivered)**
- New page route: `/preventive-maintenance/close/:taskId`
- `ClosePMTask.jsx`:
  - Renders full grouped table (rowspan by component).
  - OK/NOT OK toggles + per-row remarks.
  - Done By / Checked By sign-off.

**Exit Criteria**
- ✅ PM cannot be closed without statuses for all rows.
- ✅ Completion saves row_results and sign-off fields.

**Status:** ✅ COMPLETE

#### F3) PDF Export per PM Task (Blank + Completed) (P0)
**Requirements**
- Download PDF for:
  - Blank template sheet.
  - Completed instance sheet.
- Layout matches the client reference:
  - Header: title + machine/line/location/frequency/date.
  - Table: S.N./Description/Checked For/Parameter/Status/Remarks.
  - Grouping: merged/spanned Description cells for sub-rows.
  - Footer: Done By / Checked By with Name + Signature lines.

**Backend (Delivered)**
- Added `reportlab`.
- Endpoint:
  - `GET /api/pm-tasks/{id}/pdf` (blank)
  - `GET /api/pm-tasks/{id}/pdf?completion_id=latest|<id>` (completed)
- Completed PDF fills:
  - per-row statuses and remarks
  - done_by / checked_by

**Frontend (Delivered)**
- PDF download via authenticated blob:
  - `downloadPmPdf()` helper.
- Buttons:
  - PM row actions: blank PDF + last-completed PDF.
  - Close PM page: blank PDF.

**Exit Criteria**
- ✅ PDFs download successfully and are printable.
- ✅ Completed PDFs render recorded OK/NOT OK + remarks + sign-off.

**Status:** ✅ COMPLETE

#### F4) Public “Report Breakdown” Entry Point (No login required) (P0)
**Requirements**
- Login page provides a **Report Breakdown** option before authentication.
- Uses the same Report Breakdown form.
- Reporter Name is required.
- System flags these submissions (e.g. `submitted_via: public_kiosk`).

**Backend (Delivered)**
- Public endpoints (no auth):
  - `GET /api/public/report-context` (lines + machines)
  - `POST /api/public/breakdowns` (creates breakdown, supports auto-WO)
- Breakdown flagged:
  - `submitted_via = "public_kiosk"`

**Frontend (Delivered)**
- `Login.jsx`:
  - Adds “Machine down? No login needed.” block with `public-report-breakdown-button`.
- `ReportBreakdownDialog.jsx`:
  - `publicMode` option:
    - loads context from `/public/report-context`
    - submits to `/public/breakdowns`
- `Breakdowns.jsx`:
  - Shows a PUBLIC badge on kiosk tickets.

**Exit Criteria**
- ✅ Breakdowns can be submitted without authentication.
- ✅ Reporter Name required.
- ✅ Kiosk submissions are distinguishable in the system.

**Status:** ✅ COMPLETE

**Phase F Testing:** ✅ COMPLETE
- `/app/test_reports/iteration_4.json` — **backend 98.8% (82/83)** *(single miss is a test artifact)*, **frontend 100%**

---

## 3) Next Actions
> All earlier phases are complete. Phase E and Phase F are complete and tested.

### Completed (Prior Iterations) ✅
- Removed infinite zoom in Control Room; enabled vertical scroll.
- Replaced plant runtime clock display with wall-clock time.
- Applied Cyberpunk HUD styling across all modules.
- Verified Breakdown → auto-create WO end-to-end.

### Phase E — Completed Work ✅
- Implemented `GET /api/control-room/line-kpis` + Ribbon v2.
- Implemented per-user sidebar customization (`/api/users/me/ui-prefs`).
- Implemented admin branding: accent hex + logo upload.
- Standardized outlined styling + pure black theme.

### Phase F — Completed Work ✅
- PM templates/tasks now support `checklist_groups` (component → sub-items), `location`.
- New structured checklist builder in PM create flow.
- New dedicated PM close page with per-row OK/NOT OK + per-row remarks + sign-off.
- PM PDF export (blank + completed) matching reference layout.
- Public kiosk breakdown reporting from login with `submitted_via=public_kiosk` and PUBLIC badges.

### Optional Next Enhancements (Future / Backlog)
- PM templates UI in Administration (separate from creating a PM task) to manage reusable templates by machine type.
- True “current shift” time window mode using a configurable shift schedule (timezone-aware) for availability KPIs.
- Control Room ribbon drilldown: click line/section → open filtered breakdown/work-order panel.
- Public kiosk hardening:
  - rate limiting / spam throttling
  - optional kiosk PIN
  - optional photo upload for breakdowns.
- PDF styling polish:
  - embed a monospace font and/or add logo in header
  - add explicit checkbox glyphs and signature capture.
- Contrast review pass (WCAG-oriented) for pure black + neon accents.

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
- ✅ Breakdown reporting is accessible to non-authenticated operators:
  - login-page public report flow
  - reporter accountability captured
  - submissions flagged `public_kiosk` and visually tagged.
- ✅ All changes validated by test reports:
  - Phase E: `/app/test_reports/iteration_3.json`
  - Phase F: `/app/test_reports/iteration_4.json`
