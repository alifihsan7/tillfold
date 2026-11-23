# Tillfold design direction: Fold 2

Tillfold is a personal-finance dashboard for daily spending decisions. Fold 2 is the live design language. It replaced the earlier Ink & Silver direction (glass inset, 20 px panels, no entrance motion). The legacy tokens in `globals.css` still exist as a compatibility layer, but Fold 2 values win inside `.tillfold-fold`.

Source of truth: `frontend/src/app/fold2.css` for tokens and Fold components, `frontend/src/app/globals.css` for legacy tokens, type roles and motion tokens. If this document and the CSS disagree, fix the CSS or this document in the same change.

## Principles

- Neutral surfaces; semantic color only for money direction and status.
- Pill-shaped actions, large soft containers, flat panels. Elevation belongs to overlays and the stacked wallet.
- Missing data must never look like a real zero balance or a safe spending recommendation. Guest, loading, failure and unset-budget states stay explicit.
- Motion confirms a change or orients the reader. It never moves financial figures while they are being read.

## Color

All Fold colors are `--fold-*` tokens defined on `:root` (dark) and `.light`. Components use the tokens, or the legacy aliases that Fold 2 remaps (`--luma-*`, `--obsidian-*`, `--slate-*`). Do not hardcode hex values in components.

| Role | Dark | Light |
| --- | --- | --- |
| Canvas `--fold-canvas` | #171a1f | #e4e7eb |
| Surface `--fold-surface` (panels, dialogs) | #23272e | #ffffff |
| Panel `--fold-panel` (insets, rows on hover, chips) | #2d323a | #f2f4f6 |
| Edge `--fold-edge` (dividers) | #3b424d | #d6dbe1 |
| Selected `--fold-selected` | #3b414a | #eceff2 |
| Text `--fold-overview-text` | #f3f5f7 | #111419 |
| Secondary / muted text | #d5dae1 / #aab2bd | #48505b / #5a626d |
| Positive (income) | #b9dfc9 | #147a46 |
| Negative (expense) | #ff9e96 | #b3352e |
| Primary action `--fold-primary` / text | #eef1f4 / #15181d | #15181d / #ffffff |
| Secondary control fill / hover | #2d323a / #3b414a | #e4e7eb / #dce0e5 |
| Field fill / edge | #2c323a / #858d99 | #f0f2f5 / #818c9a |
| Focus ring `--fold-focus` | #a8c0ff | #2d5ad6 |

The hero panel has a folded top-right corner (`--fold-corner`). In light mode it is an ink card (`--fold-ink` #15181d, text `--fold-on-ink`). In dark mode it is a white sheet (#f3f5f7) with ink text, a darker action button, and the light-theme mint and coral for contrast. The dark-mode values are scoped to `html:not(.light) .fold-hero` in `fold2.css`.

Account colors appear only as a small identifying dot. User-selected category colors keep their meaning. Both themes share the same semantic roles.

## Shape

| Element | Radius |
| --- | --- |
| Hero panel | 30 px (26 px on phones) |
| Panels, cards, data states | 28 px |
| Dialogs and bottom sheets | 32 px (sheets round the top corners only) |
| Menus, popups, calendar | 20 px |
| Inset readouts and legends | 14–20 px |
| Fields, selects, date and currency wrappers | 14 px |
| Buttons, chips, segments, icon buttons, badges, topbar | 999 px |
| Segmented and tab group frames | 22 px (inner tabs are pills) |
| Transaction rows | 18 px |
| Avatars, progress tracks | circular |

Borders are mostly absent: panels sit on the canvas with no border and no shadow. Form fields are the exception and always carry a visible `--fold-field-edge` border drawn on the outermost wrapper.

Shadows: `--fold-overlay-shadow` for menus, dialogs and toasts; `--fold-sheet-shadow` for the stacked wallet sheets. Nothing else casts a shadow.

## Typography

- Interface font: Plus Jakarta Sans (`--font-plus-jakarta`) through `--ai7-font-ui`. Geist stays as the fallback and as the `body` font outside `.tillfold-fold`. Geist Mono is used only for code-like values such as tokens and webhook strings.
- Money and metrics use tabular numerals. Never use a monospace face for amounts.
- Headings use weight 750 with negative tracking (`-.015em` to `-.05em`, tighter as the size grows).

| Role | Size | Weight |
| --- | --- | --- |
| Primary balance | `clamp(27px, 10.2cqi, 60px)` (26–42 px on phones) | 750 |
| Summary metric | 28 px (24 px on phones) | 750 |
| Page title | 30 px (24 px on phones) | 750 |
| Section title | 16–18 px | 750 |
| Card title | 16 px | 750 |
| Body and controls | 13–14 px | 400–700 |
| Metadata | 12 px | 400–650 |
| Inputs | 16 px (prevents iOS zoom) | 400 |

Nothing renders below 12 px. Metric lines use line-height 1.1–1.2, supporting text 1.4–1.5. Long amounts wrap (`overflow-wrap: anywhere`) instead of hiding digits.

Use sentence case for headings, labels, buttons and badges ("Total pemasukan", "Catat transaksi"). Preserve acronyms, product names and user-entered values. Capitalization is presentation only.

## Spacing

8 / 12 / 16 / 24 / 32 px scale. Related controls 8 px apart, cards and fields 16 px, page sections 24 px (16 px on phones), panel padding 20–28 px. The wallet stack overlaps pockets by 20 px on purpose.

## Controls

- Primary action: `--fold-primary` fill, pill, 42 px tall on desktop. Secondary actions use `--fold-control`. Inside the light-mode ink hero, secondary actions use a white 14 % tint.
- Icon buttons and links are 36 px on desktop and 44 px below 768 px. Form controls, dialog buttons and navigation are 44 px at every width. Primary pressed state darkens the fill; buttons never gain a border on press.
- Chips: selected state is the inverted primary fill with `aria-pressed`. Neutral selected tabs use a silver fill and bold text in light mode and a surface-colored pill in dark mode. Income and expense segments use semantic tints.
- Selected rows in menus use a silver fill with weight 700. The light-mode date picker uses the same silver fill for the selected day. In the transaction calendar, the selected day has a bottom inset line in `--fold-focus`.
- Focus: every interactive element shows a 2 px outline in `--fold-focus`. Elements that sit on ink or inside a clipped group use an inset bottom line instead.
- Status and category badges use the badge radius (pill) and weight 650. Hand-built icon and color pickers use the same silver selected fill as neutral tabs; selection never adds a persistent outline.
- Checkboxes: field fill unchecked, primary fill checked.

## Layout

- The app fills the viewport. The sidebar is a separate rounded panel inset 16 px from the screen edge, 244 px wide, collapsible to an icon rail with a 44 px toggle. The browser remembers the choice.
- The topbar is a pill containing the period selector, the theme toggle and other global actions. At 1130 px and wider the page title moves into the topbar and the in-page title becomes screen-reader-only.
- Below 768 px: bottom navigation, a drawer for secondary pages, bottom sheets by default for dialogs with safe-area padding.
- Overview grid is 1.62 fr main column plus 1 fr side column, stacking below 1024 px. Summary grids use one column on phones, two at medium widths, four from 1440 px.
- The period selector is a single popup with Siklus, Minggu, Bulan and Kustom tabs, a list of recent periods, and a history link. It keeps legible contrast on ink while expanded.

## Icons

- UI glyphs come from `frontend/src/components/icons.tsx`: a local SVG line set with a 24-unit grid, 1.7-unit strokes, square terminals and slightly rounded joins. Navigation uses 20 px glyphs (1.9-unit strokes for the selected item); action icons use 14–16 px and supporting marks 20–24 px.
- Shapes distinguish functions: a ledger for the overview, receipt for transactions, divided wallet for budget, milestone flag for goals and a simple chart for reports. Settings uses sliders, and the wishlist uses a bookmark instead of sparkle decoration.
- Interface and decorative icons are neutral. Semantic money/error colors remain on financial/status controls, and user-selected category/goal colors remain on dots, badges and progress bars. Dialog, goal, category and pocket marks have no colored icon tile.
- Category marks identify their subject (food, shopping, transport, utilities, health, education, income); unknown names use a tag. Incoming money consistently points down-left, outgoing money up-right, and paired transfers use two opposing arrows.
- Built-in goal keys stay compatible with saved data. Custom user-selected emoji remain user content. The Google sign-in mark and Tillfold logo are brand assets, separate from this UI set.
- Glyphs are hidden from assistive technology by default; meaningful standalone glyphs require `aria-label`, while icon buttons retain their text or accessible button name. Glyphs never receive keyboard focus.

## Motion

Tokens: `--luma-motion-quick` 140 ms, `--luma-motion-panel` 220 ms, `--luma-motion-meter` 360 ms, easing `--luma-motion-out` `cubic-bezier(.22, 1, .36, 1)`.

- Page heading slides up 8 px (240 ms); content fades in over 180 ms. Overview groups and account/category/goal cards fade in over 360 ms with a 45 ms stagger, capped at 180 ms. No translation or counting animation of financial figures.
- Button color, border and shadow changes use the quick duration; pressed state has no scale or translation. Selected navigation icons briefly settle from 85 % scale (260 ms), without moving the button or label.
- Shared segments, plan/settings tabs and profile tabs use `SelectionRail`: a pill background follows the selected button over 260 ms. Labels and focus stay stationary. ResizeObserver keeps the pill aligned when tabs wrap, fonts load, or labels change. Without measurement, the native selected background remains visible.
- Gauges, ratio bars, cycle bars and chart bars grow from their baseline (460–640 ms) and animate again when the period or amount changes.
- A newly added transaction highlights in positive color and fades out (640 ms).
- Dialogs fade; bottom sheets slide up 24 px on phones; the mobile drawer slides in from the left.
- Everything is wrapped in `prefers-reduced-motion: no-preference`.

## Components

- **Hero balance**: ink panel, balance, income/expense ratio bar with legend, then actions. The eye toggle hides amounts (`HiddenAmount`).
- **Budget gauge**: ring gauge with daily allowance; switches to negative color when the pace is `warning`.
- **Cash wallet**: stacked pocket sheets that darken with depth; the selected account comes to the front and shows chips and actions (reconcile, transfer).
- **Overview lists**: transaction and cash-account headings sit outside their cards on the same baseline. The transaction panel stretches to the wallet height and shows extra recent entries on desktop according to the number of accounts (up to ten); stacked layouts keep five.
- **Transactions**: 38 px round icon, two-line copy, amount, row actions. Phones drop actions to a second row.
- **Ledger and calendar**: table header on `--fold-panel`, row hover `--fold-row-hover`, calendar days tinted by expense level.
- **Goals**: category palette colors also drive goal dots, badges and progress fills, preserving Emerald, Cyan, Amber, Purple and Rose. Mobile color pickers use two columns so names remain readable.
- **Categories**: filters and management dialogs use the shared neutral segmented control. Category cards sit on `--fold-panel`, with progress tracks on `--fold-edge`; user-selected accent colors remain intact. Transaction types read “Pengeluaran” and “Pemasukan”.
- **Nested tab frames**: inner pill tabs sit in a 4 px inset frame with a 22 px radius.

## Scope and known deviations

This document describes the target. Resolved on 2026-11-22:

- Radius tokens live only in `globals.css` (28 / 14 / 999 px). Tailwind `rounded-xl` maps to the control radius and `rounded-2xl` / `rounded-3xl` to the panel radius, so raw classes land on the Fold scale.
- The Fold color remap applies at `:root` as well as `.tillfold-fold`, so `body`, scrollbars and portaled menus share the Fold palette. The legacy Ink & Silver and bluish light values were removed from `globals.css`; only `--luma-ember`, gold, transfer and a few accent tokens remain there.
- `text-zinc-*` classes were replaced with `text-luma-ivory`, `text-luma-secondary` and `text-luma-smoke`.
- One button voice: weight 600, 44 px for touch and 36 px for a fine pointer on desktop. `.fold-action`, `.ui-btn` and `.luma-action-*` share this geometry.
- Nothing renders below 12 px except the allocation bar labels, which scale with their segment. Amounts no longer use `font-mono`.
- Browser, PWA and Telegram chrome colors follow `--fold-canvas` through `CHROME_COLOR` in `ThemeProvider.tsx`.
- The unused legacy hero (`LumaHeroGrid`, `LumaHeroCard`, `.luma-balance-*`, `.luma-guest-panel` and related CSS) was deleted.

Still diverging and worth fixing rather than copying:

- `bg-white/[...]` tints are used for subtle fills; light mode remaps them to the Fold text color at 4–7 % opacity.
- `rounded-md` and `rounded-lg` remain on small icon boxes and skeletons.
- `font-mono` remains only for identifiers and code (loan number, spreadsheet ID, webhook strings).
- Category and account color pickers use raw Tailwind palette classes by design, since users choose those colors.

No change to financial calculations or production hosting is implied by this document.
