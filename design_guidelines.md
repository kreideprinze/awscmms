{
  "design_system_name": "ForgeOps SCADA Mission Control",
  "product_intent": {
    "app_type": "industrial operations platform (SCADA/HMI + Digital Twin + CMMS + Reliability)",
    "primary_user_modes": [
      "Control Room (glanceable, always-on, large screens)",
      "Technician (fast triage + work execution)",
      "Reliability Engineer (analysis + predictive)",
      "Admin (configuration)",
      "Mobile floor terminal (touch-first, quick actions)"
    ],
    "north_star_actions": [
      "Find a machine fast → open Machine Detail Drawer → take action (create WO / log breakdown / start repair)",
      "See plant exceptions at a glance (alarms, overdue PM, health degradation)",
      "Drill from Plant → Dept → Line → Machine without losing context",
      "Acknowledge notifications and route work"
    ],
    "brand_attributes": [
      "engineered",
      "high-contrast",
      "glanceable",
      "mission-control",
      "calm under pressure",
      "machine-centric"
    ]
  },

  "visual_personality": {
    "style_fusion": [
      "ISA-101 High Performance HMI (muted neutrals + color only for abnormal)",
      "Mission-control dashboards (dense, modular panels, KPI strip)",
      "Industrial CMMS (tables, lifecycle states, auditability)",
      "Digital twin canvas (pan/zoom, minimap, selection outlines)"
    ],
    "do_not": [
      "No consumer gradients, no playful illustrations",
      "No purple (explicitly avoid)",
      "No glossy neon overload—electric blue is an accent, not a wash",
      "No center-aligned app container"
    ]
  },

  "typography": {
    "google_fonts": {
      "heading": {
        "family": "Space Grotesk",
        "weights": ["500", "600", "700"],
        "usage": "H1/H2, module titles, KPI labels"
      },
      "body": {
        "family": "IBM Plex Sans",
        "weights": ["400", "500", "600"],
        "usage": "tables, forms, long reading"
      },
      "mono": {
        "family": "IBM Plex Mono",
        "weights": ["400", "500"],
        "usage": "ticket numbers, SAP codes, machine IDs, timestamps"
      }
    },
    "tailwind_text_hierarchy": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg text-muted-foreground",
      "section_title": "text-sm font-semibold tracking-wide uppercase text-muted-foreground",
      "body": "text-sm md:text-base leading-6",
      "small": "text-xs text-muted-foreground",
      "kpi_value": "text-xl md:text-2xl font-semibold tabular-nums",
      "table": "text-sm tabular-nums",
      "mono_meta": "font-mono text-xs text-muted-foreground"
    },
    "number_rendering": {
      "rule": "Use tabular numbers for KPIs/tables",
      "tailwind": "[font-variant-numeric:tabular-nums]"
    }
  },

  "color_system": {
    "notes": [
      "Client-mandated: near-black background, dark grey panels, white text, electric blue accent.",
      "Use off-white for most text to reduce glare; reserve pure white for critical labels.",
      "Status colors are semantically critical and must be consistent across the app."
    ],
    "tokens_css": {
      "where": "/app/frontend/src/index.css (override :root and .dark tokens)",
      "css": ":root {\n  /* ForgeOps SCADA tokens (dark-first) */\n  --background: 220 18% 6%;        /* near-black */\n  --foreground: 210 20% 96%;       /* off-white */\n\n  --card: 220 16% 10%;             /* panel */\n  --card-foreground: 210 20% 96%;\n\n  --popover: 220 16% 10%;\n  --popover-foreground: 210 20% 96%;\n\n  --primary: 205 100% 58%;         /* electric blue */\n  --primary-foreground: 220 18% 6%;\n\n  --secondary: 220 14% 14%;        /* raised panel */\n  --secondary-foreground: 210 20% 96%;\n\n  --muted: 220 12% 16%;\n  --muted-foreground: 215 14% 70%;\n\n  --accent: 205 100% 58%;\n  --accent-foreground: 220 18% 6%;\n\n  --destructive: 0 84% 58%;\n  --destructive-foreground: 210 20% 96%;\n\n  --border: 220 12% 18%;\n  --input: 220 12% 18%;\n  --ring: 205 100% 58%;\n\n  /* Charts (muted, readable on dark) */\n  --chart-1: 205 100% 58%;\n  --chart-2: 142 70% 45%;\n  --chart-3: 45 95% 55%;\n  --chart-4: 24 95% 55%;\n  --chart-5: 0 84% 58%;\n\n  --radius: 0.6rem;\n}\n\n.dark {\n  /* keep same values; app is dark-first */\n}\n\n:root {\n  /* semantic status */\n  --status-running: 142 70% 45%;\n  --status-watch: 45 95% 55%;\n  --status-inspection: 24 95% 55%;\n  --status-failed: 0 84% 58%;\n  --status-idle: 215 10% 55%;\n\n  --focus-ring: 205 100% 58%;\n  --panel-1: 220 16% 10%;\n  --panel-2: 220 14% 14%;\n  --panel-3: 220 12% 18%;\n}\n"
    },
    "status_colors": {
      "running": {"label": "Running", "hsl": "hsl(var(--status-running))", "hex_approx": "#22c55e"},
      "watch": {"label": "Watch", "hsl": "hsl(var(--status-watch))", "hex_approx": "#facc15"},
      "inspection_due": {"label": "Inspection Due", "hsl": "hsl(var(--status-inspection))", "hex_approx": "#fb923c"},
      "failed": {"label": "Failed", "hsl": "hsl(var(--status-failed))", "hex_approx": "#ef4444"},
      "idle": {"label": "Idle", "hsl": "hsl(var(--status-idle))", "hex_approx": "#94a3b8"}
    },
    "electric_blue_accent": {
      "usage": [
        "primary buttons",
        "selected machine outline",
        "active nav item",
        "focus rings",
        "links",
        "chart highlight series"
      ],
      "hsl": "205 100% 58%",
      "hex_approx": "#2ea8ff"
    },
    "gradients_and_texture": {
      "rule": "Use gradients only as subtle section background overlays (<=20% viewport).",
      "allowed_background_overlay": {
        "css": "background-image: radial-gradient(900px 500px at 20% 10%, rgba(46,168,255,0.10), transparent 60%), radial-gradient(700px 420px at 80% 0%, rgba(34,197,94,0.06), transparent 55%);",
        "where": "Control Room header strip only (top band)"
      },
      "noise": {
        "css": "background-image: url('data:image/svg+xml,%3Csvg xmlns=\"http://www.w3.org/2000/svg\" width=\"120\" height=\"120\"%3E%3Cfilter id=\"n\"%3E%3CfeTurbulence type=\"fractalNoise\" baseFrequency=\"0.8\" numOctaves=\"3\" stitchTiles=\"stitch\"/%3E%3C/filter%3E%3Crect width=\"120\" height=\"120\" filter=\"url(%23n)\" opacity=\"0.08\"/%3E%3C/svg%3E');",
        "usage": "Apply as subtle overlay on app background via pseudo-element"
      }
    }
  },

  "layout_and_grid": {
    "global_shell": {
      "pattern": "Mission-control shell: thin collapsible sidebar + top KPI strip + main canvas/panel area",
      "grid": "Use CSS grid: sidebar (auto) + main (1fr). Main uses nested grid for header strip + content.",
      "max_width": "No max-width container; full-bleed for control room screens",
      "spacing": {
        "base": "Use 8px grid: gap-2/gap-3/gap-4; padding p-3/p-4",
        "rule": "2–3x more spacing than feels comfortable; avoid cramped tables by using row padding"
      }
    },
    "control_room_layout": {
      "top_strip": "Sticky KPI strip (height ~64px) with plant selector, search, filters, KPIs, notification bell",
      "main": "Pan/zoom digital twin canvas takes 70–85% width; right rail optional for live feed (collapsible)",
      "right_rail": "Live events feed + quick actions; collapsible to maximize canvas"
    },
    "responsive": {
      "mobile": "Sidebar becomes bottom sheet / drawer; canvas becomes scrollable with minimap; KPI strip becomes 2-row",
      "tablet": "Sidebar collapsible; right rail hidden by default",
      "desktop": "Full shell with optional right rail"
    }
  },

  "components": {
    "component_path": {
      "shadcn_primary": "/app/frontend/src/components/ui",
      "use_these": [
        {"name": "Button", "path": "components/ui/button.jsx"},
        {"name": "Badge", "path": "components/ui/badge.jsx"},
        {"name": "Card", "path": "components/ui/card.jsx"},
        {"name": "Tabs", "path": "components/ui/tabs.jsx"},
        {"name": "Table", "path": "components/ui/table.jsx"},
        {"name": "Drawer", "path": "components/ui/drawer.jsx"},
        {"name": "Sheet", "path": "components/ui/sheet.jsx"},
        {"name": "ScrollArea", "path": "components/ui/scroll-area.jsx"},
        {"name": "Resizable", "path": "components/ui/resizable.jsx"},
        {"name": "Command", "path": "components/ui/command.jsx"},
        {"name": "Tooltip", "path": "components/ui/tooltip.jsx"},
        {"name": "DropdownMenu", "path": "components/ui/dropdown-menu.jsx"},
        {"name": "Select", "path": "components/ui/select.jsx"},
        {"name": "Dialog", "path": "components/ui/dialog.jsx"},
        {"name": "Calendar", "path": "components/ui/calendar.jsx"},
        {"name": "Sonner", "path": "components/ui/sonner.jsx"}
      ]
    },

    "navigation": {
      "sidebar": {
        "behavior": {
          "default": "thin icon-rail (56–64px)",
          "expanded": "240–280px",
          "interaction": "Client requires expand-on-hover; implement ALSO click-pin toggle for touch screens (important).",
          "accessibility": "Keyboard: focus on rail expands; Esc collapses; aria-expanded on nav"
        },
        "modules": [
          "Control Room",
          "Breakdowns",
          "Work Orders",
          "Preventive Maintenance",
          "Analytics",
          "Runtime",
          "Inventory (Spares)",
          "Administration",
          "AWS (Advance Warning System)"
        ],
        "active_state": "Electric blue left border + subtle blue glow background (opacity 8–10%)",
        "tailwind": {
          "rail": "bg-[hsl(var(--panel-1))] border-r border-[hsl(var(--border))]",
          "item": "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-white/5",
          "item_active": "text-[hsl(var(--foreground))] bg-[rgba(46,168,255,0.10)] border-l-2 border-[hsl(var(--primary))]"
        },
        "data_testids": {
          "sidebar": "app-sidebar",
          "toggle": "sidebar-collapse-toggle",
          "nav_item": "sidebar-nav-item-<module-key>"
        }
      },
      "breadcrumbs": {
        "component": "Breadcrumb",
        "path": "components/ui/breadcrumb.jsx",
        "rule": "Always show Plant → Dept → Line → Machine context in header when drilled down"
      }
    },

    "control_room_digital_twin": {
      "canvas": {
        "pattern": "Pan/zoom canvas with machine nodes grouped by Dept/Line/Process Group",
        "performance": [
          "Virtualize machine rendering when zoomed out (render clusters)",
          "Use memoized MachineCard; avoid heavy shadows",
          "Use requestAnimationFrame for pan/zoom updates"
        ],
        "must_have_ui": [
          "Search (Command palette style)",
          "Filters (status, dept, line)",
          "Minimap",
          "Legend for status colors",
          "Selection outline + details drawer"
        ],
        "machine_card": {
          "size": "compact tile 180–220px wide; height 92–120px",
          "visual": "dark panel with status bar on left + top-right health chip",
          "states": {
            "default": "border subtle",
            "hover": "border brightens + slight lift",
            "selected": "electric blue outline + glow",
            "alarm": "failed state adds red pulse dot (subtle)"
          },
          "tailwind": {
            "base": "rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--panel-1))] p-3",
            "hover": "hover:border-white/20 hover:bg-white/[0.04]",
            "selected": "ring-2 ring-[hsl(var(--primary))] ring-offset-0",
            "status_bar": "absolute left-0 top-0 h-full w-1 rounded-l-lg",
            "meta": "text-xs text-[hsl(var(--muted-foreground))]",
            "title": "text-sm font-semibold leading-5"
          },
          "data_testids": {
            "tile": "machine-tile-<machine-id>",
            "status": "machine-tile-status-<machine-id>",
            "open_drawer": "machine-tile-open-drawer-<machine-id>"
          }
        }
      },
      "machine_detail_drawer": {
        "component": "Drawer or Sheet (right side)",
        "paths": ["components/ui/drawer.jsx", "components/ui/sheet.jsx"],
        "tabs": [
          "Overview",
          "Reports",
          "Breakdowns",
          "Work Orders",
          "PM Tasks",
          "Analytics",
          "Timeline",
          "Notes",
          "Documents",
          "Reliability",
          "Spares"
        ],
        "layout": "Header: machine name + status + quick actions; Body: Tabs; Footer: primary action row",
        "data_testids": {
          "drawer": "machine-detail-drawer",
          "tab": "machine-detail-tab-<tab-key>",
          "close": "machine-detail-close"
        }
      }
    },

    "tables_and_kanban": {
      "breakdowns": {
        "component": "Table + filters + row detail Sheet",
        "lifecycle_badges": {
          "OPEN": "bg-red-500/15 text-red-200 border-red-500/30",
          "ASSIGNED": "bg-blue-500/15 text-blue-200 border-blue-500/30",
          "IN_PROGRESS": "bg-yellow-500/15 text-yellow-100 border-yellow-500/30",
          "COMPLETED": "bg-green-500/15 text-green-200 border-green-500/30",
          "CLOSED": "bg-slate-500/15 text-slate-200 border-slate-500/30"
        },
        "ticket_number": "Render in mono; copy-to-clipboard icon button",
        "data_testids": {
          "table": "breakdowns-table",
          "row": "breakdowns-row-<ticket-id>",
          "create": "breakdowns-create-button"
        }
      },
      "work_orders": {
        "views": ["Table", "Kanban"],
        "components": ["Tabs", "Table", "Card"],
        "kanban": "Use columns with ScrollArea; cards show priority, due date, machine, type",
        "data_testids": {
          "table": "work-orders-table",
          "kanban": "work-orders-kanban",
          "toggle": "work-orders-view-toggle"
        }
      }
    },

    "analytics": {
      "charts": {
        "library": "Recharts",
        "style": {
          "grid": "stroke: rgba(255,255,255,0.08)",
          "axis": "tick fill rgba(229,231,235,0.75)",
          "tooltip": "use shadcn Card styling; no default recharts tooltip"
        },
        "dashboards": [
          "MTBF",
          "MTTR",
          "Availability",
          "Failure Rate",
          "PM Compliance",
          "Downtime trends"
        ],
        "drilldown": "Plant → Dept → Line → Machine; keep breadcrumb + filter chips visible"
      }
    },

    "aws_reliability_module": {
      "weibull": {
        "visual": "Weibull curve panel with beta/eta summary chips + confidence band",
        "health_states": {
          "Healthy": "0–70%",
          "Watch": "70–80%",
          "Inspection Due": "80–100%",
          "Overdue": "100%+"
        },
        "alert_cards": "Use Card with left status bar + action buttons (Create WO, Schedule Inspection)",
        "data_testids": {
          "aws-page": "aws-page",
          "alert": "aws-alert-<alert-id>",
          "create-wo": "aws-create-wo-<alert-id>"
        }
      }
    },

    "notifications": {
      "toast": {
        "library": "sonner",
        "pattern": "Real-time WebSocket events → toast + notification center",
        "severity": "info (blue), warning (yellow), critical (red)",
        "data_testids": {
          "bell": "notification-center-bell",
          "panel": "notification-center-panel"
        }
      }
    },

    "forms": {
      "inputs": {
        "components": ["Input", "Select", "Textarea", "Checkbox", "Switch"],
        "style": "Dark inputs with clear focus ring; labels always visible",
        "tailwind": "bg-[hsl(var(--panel-2))] border-[hsl(var(--border))] focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
      },
      "date": {
        "component": "Calendar",
        "path": "components/ui/calendar.jsx",
        "usage": "PM scheduling, due dates"
      }
    }
  },

  "buttons": {
    "shape": "Professional / action-first: squircle-ish radius (10px) with crisp borders",
    "variants": {
      "primary": {
        "usage": "Acknowledge, Create Work Order, Start Repair",
        "tailwind": "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:bg-[rgba(46,168,255,0.90)] focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
        "data_testid": "primary-action-button"
      },
      "secondary": {
        "usage": "Filters, secondary actions",
        "tailwind": "bg-[hsl(var(--panel-2))] text-[hsl(var(--foreground))] border border-[hsl(var(--border))] hover:bg-white/[0.06]",
        "data_testid": "secondary-action-button"
      },
      "ghost": {
        "usage": "Icon buttons in dense toolbars",
        "tailwind": "hover:bg-white/[0.06] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]",
        "data_testid": "ghost-action-button"
      },
      "destructive": {
        "usage": "Close breakdown, delete template",
        "tailwind": "bg-red-500/15 text-red-200 border border-red-500/30 hover:bg-red-500/20",
        "data_testid": "destructive-action-button"
      }
    },
    "micro_interaction": {
      "press": "active:scale-[0.98]",
      "hover": "hover:translate-y-[-1px] (only on pointer devices)",
      "rule": "Do not use transition: all; use transition-colors and/or transition-shadow"
    }
  },

  "motion": {
    "library": "Framer Motion",
    "principles": [
      "Fast, subtle, functional motion (no bouncy easing)",
      "Use motion to indicate state changes: selection, alarm, drawer open",
      "Respect prefers-reduced-motion"
    ],
    "tokens": {
      "duration_fast": 0.12,
      "duration": 0.18,
      "ease": "[0.2, 0.8, 0.2, 1]"
    },
    "patterns": {
      "drawer": "slide-in from right + fade scrim",
      "sidebar": "width transition (transition-[width] duration-200) + label fade",
      "machine_alarm": "subtle pulse on failed dot (opacity)"
    }
  },

  "accessibility": {
    "contrast": "Aim WCAG AA; for critical alarms target ~7:1 contrast",
    "focus": "Always visible focus ring in electric blue; never remove outline",
    "touch_targets": ">=44px; for control-room touch panels prefer 56–60px",
    "color_redundancy": "Status must be encoded by color + label + icon/shape (e.g., dot + text)"
  },

  "image_urls": {
    "policy": "This is an industrial ops product; avoid stock photos in core UI. Use subtle abstract textures only.",
    "background_textures": [
      {
        "category": "noise",
        "description": "Inline SVG noise overlay (no external asset)",
        "url": "INLINE_DATA_URI (see color_system.gradients_and_texture.noise.css)"
      }
    ],
    "login": [
      {
        "category": "login-background",
        "description": "Abstract dark industrial texture (optional, low opacity) behind login card",
        "url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=2400&q=70"
      }
    ]
  },

  "extra_libraries": {
    "recommended": [
      {
        "name": "react-zoom-pan-pinch",
        "why": "Reliable pan/zoom for digital twin canvas with minimap support",
        "install": "npm i react-zoom-pan-pinch",
        "usage_note": "Wrap canvas; throttle onTransform; keep machine tiles memoized"
      },
      {
        "name": "react-virtual",
        "why": "Virtualize lists/tables and potentially machine tiles when zoomed out",
        "install": "npm i @tanstack/react-virtual",
        "usage_note": "Use for Breakdowns/Work Orders tables and event feed"
      }
    ]
  },

  "instructions_to_main_agent": {
    "global": [
      "Update /app/frontend/src/index.css tokens to the dark-first ForgeOps palette above.",
      "Add Google Fonts (Space Grotesk, IBM Plex Sans, IBM Plex Mono) in index.html or via CSS import.",
      "Ensure body background uses --background and apply subtle noise overlay via a fixed pseudo-element on body or #root.",
      "Every interactive element and key info element MUST include data-testid (kebab-case).",
      "Use shadcn components from /src/components/ui (JS files). Do not hand-roll dropdowns/calendars/toasts.",
      "Avoid heavy shadows; use surface steps (panel-1/panel-2/panel-3) and borders for separation.",
      "Implement sidebar expand-on-hover per client, but ALSO provide a pin toggle for touch devices (important for real factories)."
    ],
    "page_specific": {
      "login": [
        "Dark background with subtle texture; centered login card but content left-aligned.",
        "Role selector (Select) + username/password; primary CTA electric blue.",
        "Add data-testid: login-username-input, login-password-input, login-submit-button"
      ],
      "control_room": [
        "Top KPI strip: Plant selector, global search (Command), status filter chips, KPIs (Availability, Open Breakdowns, Overdue PM, Watchlist), notification bell.",
        "Main: pan/zoom canvas with grouped lanes; minimap bottom-right; legend bottom-left.",
        "Machine click opens Machine Detail Drawer with 11 tabs."
      ],
      "analytics": [
        "Use Recharts with muted gridlines; highlight selected series in electric blue.",
        "Provide drill-down chips and breadcrumb always visible."
      ]
    }
  }
}

---

<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>
