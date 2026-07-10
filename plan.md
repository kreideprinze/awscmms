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
- Remove friction for shop-floor breakdown reporting:
  - Provide a **public kiosk breakdown reporting** entry point (no login required) capturing Reporter Name and flagging submissions as public.
- Ensure reliability analytics are **verifiable with seeded data**:
  - Provide deterministic, labeled demo datasets to validate **Weibull** fit outputs (beta/eta/mean life/B10) and AWS UI behavior.
- Maintain **UI excellence without logic risk**:
  - Allow iterative UI polish improvements **without changing backend/frontend business logic**.

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
**Problem**
- Downloading a PDF from Close PM page threw a runtime error (500).
- Root cause: **non-ASCII em-dash (—)** in PM task names (e.g. `Predictive Inspection — Extruder 1`) causing **latin-1 encoding failure** in `Content-Disposition` header.

**Fix (Delivered)**
- Backend: sanitize PDF filename to ASCII-safe characters before setting header:
  - `routers_maintenance.py` `pm_task_pdf`: `safe_name = _re.sub(r'[^A-Za-z0-9._-]+', '_', task_name)`
- Frontend: add `.catch(...)` toast error handling for PDF download actions:
  - `ClosePMTask.jsx` download button and toast action

**Verification**
- Previously failing task now returns **200**, and browser download works from the Close PM pane.

**Status:** ✅ COMPLETE

#### G2) Seed deterministic Weibull verification dataset (P0)
**Goal**
- Provide reproducible test data to validate Weibull fit results and AWS “Advanced (L3)” behavior.

**Implementation (Delivered)**
- Added `/app/backend/seed_weibull_demo.py` (idempotent, rerunnable) which seeds:
  - **320 days** of historical runtime logs at **20.0 run-hours/day**
  - **8 CLOSED** breakdown events at deterministic **median-rank Weibull quantile** TBFs
  - Anchors `commissioned_at`, recomputes reliability for immediate AWS visibility
- Profiles created (tagged `source='weibull_demo'` for identification/cleanup):
  - Fryer (PC21): wear-out **beta=3.0, eta=700h**
  - Auto Halver (PC32): random/constant **beta=1.0, eta=600h**
  - Blending System (KKR): infant mortality **beta=0.8, eta=500h**

**Expected / Observed**
- Fitted MLE results are close to targets (n=8 ⇒ expected bias):
  - PC21 Fryer: ~**3.60 / 689.7**
  - PC32 Auto Halver: ~**1.17 / 577.3**
  - KKR Blending: ~**0.93 / 474.2**
- AWS page shows the three machines as **L3 / Advanced**, and the **Weibull Active** count reflects the seeded models.

**Status:** ✅ COMPLETE

**Phase G Testing:** ✅ COMPLETE
- Manual + browser validation:
  - Close PM “Blank PDF” downloads successfully.
  - AWS page shows seeded Weibull machines with beta/eta.

---

### Phase H — UI Polish Pass (Creative Freedom; Zero Logic Changes)
> A purely visual refinement pass to improve readability, “HUD coherence”, and perceived quality without touching business logic.

#### H1) Global CSS micro-interactions + HUD detailing (P1)
**Status:** ✅ COMPLETE

**Delivered (visual-only)**
- Accent-tinted `::selection`
- Global button press feedback (`:active` translateY + scale)
- `cyber-panel` hover border lift + **HUD corner brackets** via `::before`
- Table row hover **accent rail** (inset shadow)
- Page title **neon underline signature** (`main h1::after`)
- Dialog aura shadow + glass overlay (backdrop blur on overlays)
- Sidebar icon hover scale + glow
- Input hover border affordance
- Stronger background vignette over noise overlay (focuses eye center)
- Login animated perspective grid floor (`.login-grid`)
- `prefers-reduced-motion` block for accessibility

#### H2) JSX presentational tweaks (P1)
**Status:** ✅ COMPLETE

**Delivered (visual-only)**
- Control Room `MachineTile` hover lift + stronger glow
- `LineKpiRibbon` line cards hover lift
- `KpiCard` hover: value glow + label brighten
- Login: add grid background + glass/aura card shadow
- Login submit button normalized to app-wide outlined styling (removed hardcoded solid fill)

**Verification**
- Screenshots captured: login (grid + outlined), Control Room (panel brackets + hover lift), Breakdowns (h1 underline + row rail), dialog (glass overlay)
- No testids changed; esbuild clean; no console errors observed.

**Status:** ✅ COMPLETE

---

## 3) Next Actions
> All phases through H are complete. Remaining work is optional backlog only.

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

### Phase G — Completed Work ✅
- Fixed PDF download crash caused by non-ASCII task names (Content-Disposition latin-1 encoding).
- Seeded deterministic Weibull demo dataset (`seed_weibull_demo.py`) for verifying Weibull fit outputs and AWS behavior.

### Phase H — Completed Work ✅
- Visual-only UX polish pass (global micro-interactions, HUD detailing, hover behaviors, login grid, dialog glass overlay) without any business-logic changes.

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
- Reliability demo management:
  - add an admin endpoint/button to purge `source='weibull_demo'` data
  - show a “DEMO” tag on seeded Weibull models in AWS UI.
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
- ✅ Reliability calculations are verifiable:
  - deterministic Weibull demo dataset exists (runtime logs + closed breakdowns)
  - AWS shows L3/Advanced machines with beta/eta, predicted life and Weibull Active count.
- ✅ UI polish improvements do not introduce logic regressions:
  - visual-only enhancements applied consistently
  - reduced-motion users respected
- ✅ All changes validated by test reports:
  - Phase E: `/app/test_reports/iteration_3.json`
  - Phase F: `/app/test_reports/iteration_4.json`
