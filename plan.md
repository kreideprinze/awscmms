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
- **NEW (Phase E)**: Upgrade Control Room “at-a-glance” intelligence + deep customization:
  1) Replace the top KPI ribbon primary content with **Availability + Downtime** at **Line** and **Section/Process Group** levels (expandable), with plant-wide aggregates demoted to a collapsible secondary strip.
  2) Sidebar navigation supports **user-assigned icon colors** + **drag-and-drop reorder**, persisted per user.
  3) Admin-configurable **custom branding**: uploadable logo + hex brand accent color applied platform-wide.
  4) Standardize all buttons/icons to **outlined style**: thin-line borders, transparent interiors.
  5) Move the background theme to **pure black** base (remove deep-blue undertone), while preserving contrast.

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
  - **Availability per Line**: PC21, PC32, PC36, KKR, TWZ, BCP, Packaging, Utilities.
  - **Total downtime per Line** for selected window (shift/day/custom window).
- Each Line entry is expandable to show:
  - **Availability per Section/Process Group** within the line.
  - **Total downtime per Section/Process Group** for same window.
- Keep plant-wide aggregate counts (Machines/Running/Failed/Open BD/Open WO/etc.) as a **secondary collapsible strip**.
- Time window is **configurable** (default = current shift or current day). Must be consistent across Control Room and Breakdown timestamps.

**Backend**
- Add a new endpoint, e.g.:
  - `GET /api/control-room/health-kpis?window=shift|day|hours&hours=8&tz=...`
- Computations:
  - **Downtime** = sum of breakdown downtime/repair time in window.
  - **Availability** (practical v1):
    - If runtime logs exist for window: availability = run_hours / calendar_hours.
    - Else fallback: availability approximation from breakdown minutes within window (calendar - downtime) / calendar.
- Grouping:
  - by `line` and by `process_group` (aka section).
- Add indexes if needed:
  - `breakdowns(line, process_group, start_time)`
  - `runtime_logs(line, machine_id, date)` (if used)

**Frontend**
- Replace the current top KPI strip in `ControlRoom.jsx`:
  - New ribbon component: `LineAvailabilityRibbon` (expand/collapse lines; show mini cards)
  - Time window selector: `Shift / Day / Last N hours`.
  - Secondary collapsible strip for old plant aggregates.
- UX details:
  - Show availability as % with mono tabular numerals.
  - Show downtime next to it (e.g. `92.4% · 1h 24m down`).
  - Clicking a section optionally filters the twin to that line/section.

**Exit Criteria**
- Ribbon shows correct per-line and per-section figures for chosen window.
- Expanding a line reveals process-group breakdown.
- Secondary strip contains plant-wide totals and can be collapsed.

#### E2) Sidebar Icon Customization (Per-user) (P0)
**Requirements**
- Sidebar icons support **user-assigned color** per icon.
- Sidebar supports **drag-and-drop reorder**.
- Persist these settings **per user**.

**Backend**
- Extend user document/preferences:
  - `ui_prefs: { sidebar: { order: ["control_room", "breakdowns", ...], colors: { moduleKey: "#RRGGBB" } } }`
- Endpoints:
  - `GET /api/users/me/ui-prefs`
  - `PUT /api/users/me/ui-prefs` (validate hex colors + module keys)

**Frontend**
- Update `Layout.jsx` sidebar:
  - Add DnD (e.g., dnd-kit) for ordering.
  - Add icon color picker (simple hex input or palette) per item.
  - Load/save prefs on login.

**Exit Criteria**
- User reorders modules and chooses colors; refresh preserves order/colors.

#### E3) Custom Branding: Admin Uploadable Logo + Hex Brand Color (P0)
**Requirements**
- Replace top-left hardcoded mark with admin-uploaded logo/icon.
- Admin-configurable **brand accent color** via **hex input** (not preset).
- Accent color drives:
  - icons, buttons, borders, highlights, focus rings, charts where applicable.
- Integrate under existing Administration Branding settings.

**Backend**
- Add settings collection fields:
  - `branding.logo_url` (or stored file id)
  - `branding.brand_hex` (validated)
- Add upload endpoint:
  - `POST /api/admin/branding/logo` (multipart upload)
  - Store file under `/app/backend/uploads/` (or similar) and serve via static route.
- Add settings endpoints if not present:
  - `GET /api/admin/settings/branding`
  - `PUT /api/admin/settings/branding`

**Frontend**
- Administration → Branding tab:
  - Logo upload control + preview
  - Brand hex input + live preview
- App-wide theming:
  - Set CSS variable `--primary` (or equivalent) from fetched branding settings.
  - Ensure it applies to existing cyber classes.

**Exit Criteria**
- Uploading logo updates top-left immediately.
- Changing brand hex updates accent across app without redeploy.

#### E4) Outlined Buttons / Icon Border Styling Standardization (P1)
**Requirements**
- All buttons/icons become outlined (1px border, transparent interior) consistently across:
  - nav icons
  - filter pills
  - action buttons

**Implementation**
- Add/adjust global utility classes:
  - `.cyber-outline-btn`, `.cyber-outline-icon`
- Update instances still using filled styles (including `cyber-primary` if needed) to outlined variants.
- Ensure hover glow remains neon but fill stays transparent.

**Exit Criteria**
- Visual consistency across all modules; no “solid fill” outliers.

#### E5) Theme Background: Pure Black Base (P1)
**Requirements**
- Replace near-black/blue-tinted backgrounds with **pure black** (#000000 or close as contrast allows).

**Implementation**
- Update CSS variables in `index.css`:
  - base background and panel backgrounds to neutral black/near-black without blue undertone.
  - keep borders readable and text contrast acceptable.
- Re-screenshot key pages to confirm removal of blue tint.

**Exit Criteria**
- Base app background and panels read as true black.
- Text remains readable; charts and borders remain visible.

---

## 3) Next Actions
> All earlier phases are complete. Next work is Phase E.

### Completed (Prior Iteration) ✅
- Removed infinite zoom in Control Room; enabled vertical scroll.
- Replaced plant runtime clock display with wall-clock time.
- Applied Cyberpunk HUD styling across all modules.
- Verified Breakdown → auto-create WO end-to-end.
- Completed testing pass (`/app/test_reports/iteration_2.json`).

### Phase E — Next Actions (New Work)
**P0**
1) Implement backend KPI aggregation endpoint for line/section availability + downtime with configurable time window.
2) Build Control Room Ribbon v2 UI with expand/collapse per line + window selector; demote plant-wide counts into collapsible secondary strip.
3) Implement per-user sidebar customization: drag-and-drop reorder + per-icon color; persist in user prefs.
4) Implement admin branding: logo upload + brand hex accent; apply as dynamic CSS variables globally.

**P1**
5) Standardize outlined button/icon styling across the entire app.
6) Update theme to pure black base; verify across all pages via screenshots.

**Testing (after Phase E)**
- Frontend: screenshot audit of Control Room ribbon expanded/collapsed states; sidebar reorder persistence; icon color persistence; logo and brand color propagation.
- Backend: API tests for KPI endpoint correctness on known seeded data; prefs endpoints; branding endpoints.

## 4) Success Criteria
- Control Room ribbon is **line-first**:
  - Availability + downtime per line always visible.
  - Expandable to section/process-group breakdown.
  - Plant-wide totals available but demoted.
- Sidebar supports per-user:
  - icon colors
  - drag-and-drop ordering
  - persistence across refresh/login.
- Branding supports admin:
  - uploadable logo
  - hex brand accent
  - immediate visual propagation.
- Buttons/icons are consistently outlined across the app.
- Theme background is true black without blue undertone.
- All changes validated by updated test report (Phase E test report).