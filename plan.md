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

### Phase E — Control Room Ribbon + Customization + Theming (NEW)
> This phase turns the Control Room into a true shift-lead “command center”: availability + downtime at the exact hierarchy level people manage (line/section), plus personalization (sidebar order/colors) and proper white-label branding.

#### E1) Control Room KPI Ribbon v2 (Line/Section Availability + Downtime) (P0)
**Requirements**
- Primary ribbon shows:
  - **Availability per Line** (PC21, PC32, PC36, KKR, TWZ, BCP; plus seeded lines as present).
  - **Total downtime per Line** for selected window.
- Each Line entry is expandable to show:
  - **Availability per Section/Process Group** within the line.
  - **Total downtime per Section/Process Group** for the same window.
- Plant-wide aggregate counts (Machines/Running/Failed/Open BD/Open WO/etc.) retained as a **secondary collapsible strip**.
- Time window is configurable via presets:
  - **Shift (8h)** / **Day (24h)** / **Week (7d)**.

**Backend (Delivered)**
- `GET /api/control-room/line-kpis?hours=8|24|168`.
- Computation method (v1 practical):
  - Downtime = **summed overlap** of breakdown open-time (start → end or now) with the selected window.
  - Availability = `1 - downtime / (machines_in_group * window)` expressed as a percent.
- Grouping:
  - by `line` and by `process_group` (section).

**Frontend (Delivered)**
- `LineKpiRibbon.jsx` renders:
  - Line cards (availability color-coded, downtime shown next to percent).
  - Expandable section panel for selected line.
  - Window selector buttons.
  - Action: **Filter twin to line**.
- `ControlRoom.jsx`:
  - Primary ribbon = Line/Section KPIs.
  - Secondary collapsible plant totals strip with inline summary when collapsed.

**Exit Criteria**
- ✅ Ribbon shows correct per-line and per-section figures for chosen window.
- ✅ Expanding a line reveals process-group breakdown.
- ✅ Secondary plant totals strip is collapsible.

**Status:** ✅ COMPLETE

#### E2) Sidebar Icon Customization (Per-user) (P0)
**Requirements**
- Sidebar icons support **user-assigned color** per icon.
- Sidebar supports **drag-and-drop reorder**.
- Persist these settings **per user**.

**Backend (Delivered)**
- User prefs stored on user document under `ui_prefs`.
- Endpoints:
  - `GET /api/users/me/ui-prefs`
  - `PUT /api/users/me/ui-prefs`
- Validation:
  - Module keys validated.
  - Hex colors validated (`#RRGGBB`).
  - Duplicate keys rejected.

**Frontend (Delivered)**
- `Layout.jsx`:
  - “Customize sidebar” mode (paintbrush toggle).
  - HTML5 drag-and-drop reorder.
  - Native color input per icon.
  - Per-user persistence via `saveUiPrefs`.

**Exit Criteria**
- ✅ User reorders modules and chooses colors; refresh preserves order/colors.

**Status:** ✅ COMPLETE

#### E3) Custom Branding: Admin Uploadable Logo + Hex Brand Color (P0)
**Requirements**
- Replace top-left hardcoded mark with admin-uploaded logo/icon.
- Admin-configurable **brand accent color** via **hex input**.
- Accent color drives:
  - icons, buttons, borders, highlights, focus rings, and other accent surfaces.
- Integrate under existing Administration System/Branding settings.

**Backend (Delivered)**
- Branding document supports:
  - `accent` (validated `#RRGGBB`)
  - `logo_data` (data-URI)
- Endpoints:
  - `GET /api/branding`
  - `PUT /api/branding` (validates `accent`)
  - `POST /api/branding/logo` (multipart upload; type validation; max 500KB; stored as base64 data-URI)
  - `DELETE /api/branding/logo`

**Frontend (Delivered)**
- `AppContext.js`:
  - `applyAccent(hex)` converts hex → HSL + RGB triple and sets runtime CSS vars:
    - `--primary`, `--accent`, `--ring`, `--accent-rgb`, etc.
- `Administration.jsx` System tab:
  - Accent hex input + color picker.
  - Logo upload/preview/remove.
- `Layout.jsx`:
  - Uses `branding.logo_data` to replace the default factory mark.

**Exit Criteria**
- ✅ Uploading logo updates top-left immediately.
- ✅ Changing brand hex updates accent across app without redeploy.

**Status:** ✅ COMPLETE

#### E4) Outlined Buttons / Icon Border Styling Standardization (P1)
**Requirements**
- All buttons/icons become outlined (1px border, transparent interior) consistently across:
  - nav icons
  - filter pills
  - action buttons

**Implementation (Delivered)**
- `button.jsx`: default/destructive/secondary are outlined; transparent interiors.
- `.cyber-primary`: switched from filled gradient sweep to outlined CTA.
- Per-page sweep: ~30 replacements converting filled pills/buttons to outlined equivalents.

**Exit Criteria**
- ✅ Visual consistency across all modules; no filled-background action button outliers.

**Status:** ✅ COMPLETE

#### E5) Theme Background: Pure Black Base (P1)
**Requirements**
- Replace near-black/blue-tinted backgrounds with **pure black** (#000000 or close as contrast allows).

**Implementation (Delivered)**
- `index.css` theme variables migrated to neutral black/greys:
  - `--background` = `0 0% 0%`.
  - Panels `--panel-1..3` in 3–9% neutral range.
  - Borders neutralized (no blue undertone).

**Exit Criteria**
- ✅ Base app background and panels read as true black.
- ✅ Text remains readable; charts/borders remain legible.

**Status:** ✅ COMPLETE

---

## 3) Next Actions
> All earlier phases are complete. Phase E is now complete and tested.

### Completed (Prior Iterations) ✅
- Removed infinite zoom in Control Room; enabled vertical scroll.
- Replaced plant runtime clock display with wall-clock time.
- Applied Cyberpunk HUD styling across all modules.
- Verified Breakdown → auto-create WO end-to-end.
- Completed testing pass (`/app/test_reports/iteration_2.json`).

### Phase E — Completed Work ✅
- Implemented `GET /api/control-room/line-kpis` (availability + downtime per line and per process-group section; configurable window).
- Implemented Control Room Ribbon v2 (LineKpiRibbon) with expand/collapse sections and “Filter twin to line”.
- Implemented per-user sidebar customization (order + icon colors) with persistence (`/api/users/me/ui-prefs`).
- Implemented admin branding:
  - accent hex applied instantly platform-wide via runtime CSS variables
  - logo upload/preview/remove (data-URI storage)
- Standardized outlined styling for buttons/pills/icons.
- Updated UI theme to pure black base (no blue undertone).

### Testing ✅
- Phase E fully regression-tested:
  - `/app/test_reports/iteration_3.json` — **backend 100% (43/43)**, **frontend 100%**.

### Optional Next Enhancements (Future / Backlog)
- Add a true “current shift” window mode using a configurable shift schedule (rather than fixed last-8h), including timezone support.
- Add a per-line breakdown list drilldown from the ribbon (click line → open filtered breakdown/work-order panel).
- Add section-level filtering directly (click section tile → filter twin to line+process_group).
- Add role-scoped admin controls for sidebar defaults (template for new users).
- Add a contrast review pass (WCAG-oriented) for pure black + neon accents.

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
- ✅ All changes validated by Phase E test report (`iteration_3.json`).
