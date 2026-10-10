---
name: Clinical Verification Engine
colors:
  surface: '#f9faf8'
  surface-dim: '#d9dad8'
  surface-bright: '#f9faf8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f2'
  surface-container: '#edeeec'
  surface-container-high: '#e7e8e6'
  surface-container-highest: '#e1e3e1'
  on-surface: '#191c1b'
  on-surface-variant: '#404942'
  inverse-surface: '#2e3130'
  inverse-on-surface: '#f0f1ef'
  outline: '#717972'
  outline-variant: '#c0c9c0'
  surface-tint: '#326949'
  primary: '#003e23'
  on-primary: '#ffffff'
  primary-container: '#1e5638'
  on-primary-container: '#90caa3'
  inverse-primary: '#99d4ad'
  secondary: '#5a605d'
  on-secondary: '#ffffff'
  secondary-container: '#dee4e0'
  on-secondary-container: '#606663'
  tertiary: '#5c2600'
  on-tertiary: '#ffffff'
  tertiary-container: '#7f3700'
  on-tertiary-container: '#ffa877'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b5f0c8'
  primary-fixed-dim: '#99d4ad'
  on-primary-fixed: '#002110'
  on-primary-fixed-variant: '#185033'
  secondary-fixed: '#dee4e0'
  secondary-fixed-dim: '#c2c8c4'
  on-secondary-fixed: '#171d1b'
  on-secondary-fixed-variant: '#424845'
  tertiary-fixed: '#ffdbca'
  tertiary-fixed-dim: '#ffb68e'
  on-tertiary-fixed: '#331200'
  on-tertiary-fixed-variant: '#763300'
  background: '#f9faf8'
  on-background: '#191c1b'
  surface-variant: '#e1e3e1'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.005em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  mono-data:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-compact: 0.5rem
  margin: 1.25rem
  margin-compact: 0.75rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

The design system embodies an uncompromisingly pragmatic, information-dense, and utilitarian workspace tailored for intelligence analysts, field researchers, and verification operations teams. The operational mandate requires absolute clarity over decoration, sustained reading comfort during eight-hour investigative shifts, and razor-sharp structural delineation of clinical truth versus discrepancy.

The design movement is **Restrained Functionalist Minimal / Modern Data Surface**, synthesized from the precision architectures of technical command consoles and structured documentation workspaces. It rejects decorative glassmorphism, floating drop-shadow layers, visual novelty, and hyper-saturated alert paradigms. Visual hierarchy is established strictly through 1px structural dividing lines, calibrated micro-typography, muted background tinting, and purposeful data density. The emotional tone is authoritative, quiet, forensic, and dependable—evoking the rigor of an archival medical ledger translated into high-performance software.

## Colors

The palette relies on organic, pigment-inspired minerals instead of synthetic digital primitives. Surfaces and backgrounds reflect warm stone and bleached parchment to alleviate ocular fatigue during long analytical sessions.

### Core Canvas & Structural Hues
- **Canvas Base:** `#F8F9F7` (warm off-white foundation for application scaffolding and shell panels).
- **Surface Elevation 01 (Pure):** `#FFFFFF` (isolated active panes, table bodies, modal viewports, input fields).
- **Surface Elevation 02 (Subtle Tint):** `#F1F2ED` (table headers, sidebars, pinned audit rails, muted secondary ribbons).
- **Surface Border Default:** `#E4E6E1` (structural divider for panels, rows, and grid lines).
- **Surface Border Emphasized:** `#D8DBD4` (active input borders, selected table cell outlines, pinned state dividers).

### Typography Tones
- **Primary Text:** `#1A1F1C` (headings, active verification metrics, operational readouts).
- **Secondary Text:** `#2D312E` (body narrative, field labels, metadata keys).
- **Muted/Caption Text:** `#626865` (table column headers, secondary timestamps, helper copy).
- **Tertiary/Disabled Text:** `#8A908D` (breadcrumbs, non-active affordances, empty-state placeholders).

### Verification & State Indicators
- **Primary Brand / Verified Active:** `#1E5638` (deep forest green) paired with surface wash `#E8F2EC` and structural border `#C3DEC8`.
- **Supported / Provenance Confirmed:** `#166534` (restrained olive green) on background fill `#DCFCE7` with crisp boundary `#BBF7D0`.
- **Under Review / Unresolved Field:** `#B45309` (amber mineral) on tint `#FEF3C7` with line boundary `#FDE68A`.
- **Contradiction / Facility Discrepancy:** `#991B1B` (restrained oxblood crimson) on tint `#FEE2E2` with line boundary `#FECACA`.

## Typography

The type scale is deliberately restrained and compressed, prioritizing high spatial density and scannability. Inter is applied uniformly across all roles, relying on disciplined line heights and weights rather than large shifts in font sizes.

### Application Rules
- **No Dramatic Scale Jumps:** The maximum heading for operational records stops at `24px` (`headline-xl`). Internal tool views demand data-per-square-inch over monumental titles.
- **Tabular Figures & Numeric Alignment:** All operational tables, hospital license numbers, GPS coordinates, bed capacity counts, and audit logs must enforce OpenType tabular figures (`tnum`) to maintain vertical parity down analytical columns.
- **Micro Labels (`label-sm`):** Rendered at 11px uppercase with positive letter spacing (`0.04em`) and medium/semibold weight for column definitions, verification badges, and statutory state badges (e.g., NABH, PMJAY, ROHINI).
- **Line Heights:** Compact and strictly locked to 2px or 4px grid intervals to prevent row bloating in dense tabular data.

## Layout & Spacing

The layout is built around a compact, split-pane workspace model:
- **Primary Shell:** Fixed left rail (navigational filters and query history, 240px fixed width), primary workbench fluid viewport, and an optional collapsible inspection drawer (420px fixed width) for record provenance.
- **Grid Structure:** Strict fluid multi-column arrangement inside analytical sections with a standard `1rem` (16px) gutter. For micro-data grids and verification diff-matrices, the `gutter-compact` (`0.5rem` / 8px) system is enforced.
- **Margin Rules:** Outer application canvas margins are set to `1.25rem` (20px) on desktop viewports and compress to `0.75rem` (12px) on auxiliary tablet interfaces. Full responsive reflow collapses inspector drawers into tabbed overlays below 1024px.
- **Density Principle:** Vertical row height for data grids is standardized at 36px (compact) or 44px (default with badges), keeping scrolling to a minimum while maintaining clear target areas for keyboard and pointer navigation.

## Elevation & Depth

Visual separation relies on explicit border geometry and surface contrast rather than ambient shadows.

### Elevation Principles
- **No Drop Shadows:** Heavy blur radii, glowing colored halos, and ambient drop shadows are completely absent. All panels, inspector rails, and cards sit flush.
- **Surface Contrast and 1px Reticules:** Depth is achieved by placing pure white (`#FFFFFF`) working surfaces directly on warm stone (`#F8F9F7` / `#F1F2ED`) background grounds, bounded by crisp 1px borders (`#E4E6E1`).
- **Active State Demarcation:** Selected rows, active inputs, and currently viewed healthcare facilities replace the boundary stroke with `#1E5638` or `#D8DBD4` without raising the element off the base coordinate plane.
- **Overlay & Popover Architecture:** Contextual dropdowns, date selectors, and command palettes use a subtle boundary definition: `1px solid #D8DBD4` with an ultra-fine structural shadow: `0 1px 3px rgba(26, 31, 28, 0.06), 0 1px 2px rgba(26, 31, 28, 0.04)`.

## Shapes

The geometric vocabulary prioritizes straight edges and low radii to reinforce the tool's ledger-like, clinical utility.

- **Base Corner Radius (0.25rem / 4px):** Applied across all interactive buttons, text input fields, status chips, segmented controls, and floating verification flags.
- **Container Radius (0.375rem / 6px):** Applied to top-level workbench containers, inspector cards, and comparison split-views.
- **Tables and Data Grids (0px):** Internal rows, table borders, header bands, and audit log columns strictly maintain orthogonal 90-degree square junctions to prevent visual gaps across continuous data cells.

## Components

### Buttons
- **Primary Action:** Solid muted forest green (`#1E5638`) background, white (`#FFFFFF`) label, crisp 4px radius, no drop shadow. Hover state shifts to `#2E7D52`. Active state compresses slightly without scaling. Focus state renders a sharp 2px outline in `#1E5638` with 2px offset.
- **Secondary / Standard:** Clean pure white (`#FFFFFF`) surface, 1px border in `#E4E6E1`, primary text (`#1A1F1C`). Hover triggers subtle stone background tint `#F1F2ED` with border darkening to `#D8DBD4`.
- **Tertiary / Utility:** Transparent fill, muted text (`#626865`), hover background `#E8F2EC` with text tinting to `#1E5638`.

### Chips & Verification Status Badges
- **General Construction:** Height 20px, horizontal padding `6px`, font size `11px` (`label-sm`), uppercase, tracking `0.04em`, 4px radius, 1px perimeter border.
- **Verified / Supported:** Fill `#DCFCE7`, text `#166534`, border `#BBF7D0`.
- **Review Required / Discrepancy Flag:** Fill `#FEF3C7`, text `#B45309`, border `#FDE68A`.
- **Contradiction / Conflict Identified:** Fill `#FEE2E2`, text `#991B1B`, border `#FECACA`.
- **Neutral Audit / System Metadata:** Fill `#F1F2ED`, text `#626865`, border `#E4E6E1`.

### Data Tables & Row Items
- **Headers:** Surface `#F1F2ED`, height 32px, text `#626865`, 11px uppercase font weight 600, border-bottom `1px solid #D8DBD4`.
- **Rows:** Alternating clean white (`#FFFFFF`) and stone tints (`#FAFBF9`) disabled by default; all rows sit on white with a single horizontal boundary `1px solid #E4E6E1`. Hover initiates an instant background shift to `#F8F9F7`. Selected rows feature a 2px left border accent in `#1E5638` and a background wash of `#E8F2EC`.

### Input Fields & Search Bars
- **Base Style:** Height 34px, surface `#FFFFFF`, 1px border `#E4E6E1`, 4px radius, typography `13px` (`body-md`).
- **Focus State:** 1px stroke shift to `#1E5638` with an additional crisp 1px box shadow in `#E8F2EC`. No default browser rings.
- **Embedded Filter Inputs:** Flat integrated inputs within table headers using transparent background, shifting to white only on interaction.

### Checkboxes & Segmented Selectors
- **Checkbox:** Square box with 2px rounded corners, 14px dimension. Inactive: `1px solid #D8DBD4`. Active: Solid `#1E5638` with a precise 1.5px white checkmark icon.
- **Segmented Control:** Enclosed container in `#F1F2ED`, padding 2px, containing flush pill buttons. The selected state renders `#FFFFFF` with a subtle 1px border `#D8DBD4` and font weight 500.

### Specialized Verification Components
- **Audit Diff Matrix:** A dual-column split row that highlights discrepancies between submitted data (e.g., claimed ICU bed count) versus verified ground-truth registers. The field with the conflict displays a left border stroke of `2px solid #991B1B` and a subtle highlight of `#FEE2E2`.
- **Provenance Breadcrumb:** Pinned inline micro-tags indicating the source of clinical evidence (e.g., `REGISTRY_MCA`, `STATE_DHS_PORTAL`, `FIELD_AGENT_GPS`) using `#626865` text over `#F1F2ED` with square divider slashes.