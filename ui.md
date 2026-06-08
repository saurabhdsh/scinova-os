# UI replication prompt (dark glass enterprise shell)

Use this document as a **single prompt or brief** to apply this **look, feel, and shell behavior** to **any** product—greenfield or redesign: SaaS dashboards, internal tools, creative apps, e‑commerce admin, devtools, mobile-web shells, etc. Adapt framework and copy; keep **visual language, spacing rhythm, and layout structure** faithful.

**Purpose:** Redesign an existing application or design a new one using this system—the guidance is **not** tied to any single industry or use case.

---

## Role & context

You are designing a **dark, glassy, information-dense product shell**: readable data, low visual noise, high perceived quality. The UI should feel **precision-engineered** and **calm**—not playful, not loud consumer pastel. Think **professional tool** or **observability-style console**: clear hierarchy, subtle depth, restrained accents.

The final result must **not** look like a default/template React application. It must look **production-ready**: polished visual hierarchy, deliberate spacing, strong typography, consistent tokens, and high-quality interaction states across hover/focus/active/loading/empty/error views.

---

## Color system (mandatory)

Implement a semantic palette named **cx** (or map 1:1):

| Token | Hex / value | Usage |
|--------|----------------|--------|
| `cx-void` | `#040508` | Deepest background, overlays |
| `cx-deep` | `#080a10` | App chrome, nav, top bar, footer |
| `cx-surface` | `#0c0f16` | Secondary surfaces |
| `cx-panel` | `#10141d` | Cards, panels, inputs |
| `cx-raised` | `#151a24` | Elevated chips, hover surfaces |
| `cx-line` | `rgba(148,163,184,0.09)` | Hairline dividers |
| `cx-border` | `rgba(148,163,184,0.11)` | Default borders |
| `cx-borderStrong` | `rgba(148,163,184,0.2)` | Emphasized borders, hover |
| `cx-fg` | `#e8edf4` | Primary text |
| `cx-fgMuted` | `#cbd5e1` | Secondary text |
| `cx-fgDim` | `#8b9cb0` | Tertiary / labels |
| `cx-accent` | `#5ec8f2` | Primary accent (cyan) |
| `cx-accent2` | `#9b8bd4` | Secondary accent (violet) |
| `cx-success` | `#3ecf9b` | Positive / safe states |
| `cx-warn` | `#e8b84a` | Warning |
| `cx-danger` | `#f08984` | Error / destructive |

**Rules**

- Default theme is **dark**; avoid bright white chrome for the shell.
- Use **subtle borders** and **inset highlights** (`inset 0 1px 0 rgba(255,255,255,0.04–0.06)`) on glass surfaces—not heavy strokes.
- Accents are **restrained**: cyan for primary actions and wayfinding; violet as secondary emphasis.
- Avoid pure black `#000` for large areas; use `cx-void` / `cx-deep`.

---

## Typography

- **UI / body:** Inter (or system-ui stack), weights 400–600.
- **Display / titles:** Outfit (or a geometric sans), semibold, tight tracking.
- **Micro labels:** Uppercase, **~0.18–0.22em** letter-spacing, size ~10px (call it `2xs` if using Tailwind-style scale).
- **Mono:** Version strings, IDs, codes, technical strings—small (`9–10px`), uppercase optional.

Hierarchy: page title (display) → section eyebrow (2xs caps) → body (13–14px) → helper (11–12px, `fgDim`).

---

## Global shell layout (three-band vertical stack)

Structure the app as:

```
┌──────────┬──────────────────────────────────────────────┐
│          │  TOP BAR (fixed height ~3.25rem)              │
│  NAV     ├──────────────────────────┬───────────────────┤
│  RAIL    │  MAIN SCROLL REGION       │  RIGHT DOCK       │
│          │  (page content)           │  (optional panel) │
│          ├──────────────────────────┴───────────────────┤
│          │  STATUS STRIP (fixed height ~2.25rem)         │
└──────────┴──────────────────────────────────────────────┘
```

- **Root:** `h-full min-h-0 flex`; avoid double scroll on the window except inside main.
- **Nav rail:** `shrink-0`, animated width **collapsed ~76px / expanded ~248px**, spring motion.
- **Main column:** `flex-1 flex flex-col min-h-0`.
- **Content:** `flex-1 min-h-0 overflow-y-auto` with a subtle **scrollbar** (thin, muted thumb).
- **Right dock:** optional `shrink-0` panel with left border and **dock shadow** (shadow cast inward from the left edge).
- **Bottom status strip:** full width, **not** overlapping content—sits under the main+dock row.

**Focus mode:** Optional: hide nav + dock + status strip for immersive views; restore chrome when exiting.

---

## Left sidebar (navigation rail)

**Exact behavior requirement (must match this spec exactly)**

- Sidebar must be **expandable/collapsible exactly as specified here**.
- Width states: **collapsed `~76px`** and **expanded `~248px`**.
- Transition: spring animation (around `stiffness: 400`, `damping: 40–42`, `mass: ~0.7`).
- In collapsed state: show **icons only** with centered alignment.
- In expanded state: show **icon + primary label + secondary sublabel** with fade/slide reveal.
- Keep the same chrome behavior: fixed left rail, border-right hairline, brand block at top, nav groups in the middle, utility/actions at bottom.

**Visual**

- Background: `bg-cx-deep/80` + **backdrop-blur-2xl**.
- Right edge: `border-r border-cx-line`; optional **vertical gradient hairline** (accent → transparent) for subtle edge emphasis.
- Top: **brand lockup**—rounded square icon container with **gradient border**, inner icon (stroke ~1.75) in `cx-accent`.
- When expanded: **product name** (display font) + **short tagline** in 2xs caps `fgDim` (e.g. product subtitle—adapt to your app).

**Nav items**

- Stacked links; each row: **icon** + (when expanded) **two lines**: primary label + smaller **group** (e.g. “Overview”, “Settings”—adapt to your IA).
- Active route: left border or pill with `accent` glow; text `cx-fg`; inactive `cx-fgDim` → hover `cx-fgMuted`.
- Icons: **Lucide** style (24px grid, 1.75 stroke)—consistent weight.

**Motion**

- Width animates with **spring** (stiffness ~400, damping ~40–42); label fades/slides on expand.

---

## Top bar

**Visual**

- Height **3.25rem**; `border-b border-cx-line`; `bg-cx-deep/75` + **backdrop-blur-2xl**.
- Top **hairline highlight:** `h-px` gradient left-to-right `transparent → white/7% → transparent`.

**Zones (left → right)** — adapt labels to your product

1. **Nav toggle** (lg+): small bordered button, 2xs uppercase “Collapse / Expand.”
2. **Breadcrumb / context:** optional pill with scope (`font-mono`, `accent` text, subtle border) + `/` + muted label (e.g. environment, org, or section).
3. **Global search:** wide pill, `border-cx-border`, `bg-cx-panel/50`, **inner shadow** (`shadow-inner-soft`), search icon `accent`, placeholder `fgDim`; hover brightens panel; **⌘K** hint in mono chip.
4. **Context selector:** bordered select, `rounded-xl`, compact text (e.g. project, account, workspace—whatever your app uses).
5. **Actions:** create / notifications / **focus mode** / **right dock toggle**—icon buttons with border, hover `accent` border tint.

**Behavior**

- **⌘/Ctrl+K** opens command palette (modal).
- Search and context selector should stay **visually dominant** in the center band when present.

---

## Right dock (secondary panel)

- Fixed width panel (~320–360px); `border-l border-cx-line`; `bg` slightly above `cx-deep` with blur.
- Title + subtitle in 2xs caps; content cards with **glass** treatment.
- **Shadow:** `dock` style—soft shadow to the left so the panel floats above content.

Use for help, notifications, AI chat, filters, or inspector—**your** content, same chrome.

---

## Bottom status strip (“system / progress bar”)

**Not a fat progress bar**—a **thin system status footer**:

- Height **~2.25rem** (`h-9`); `border-t border-cx-line`; `bg-cx-deep/85`; backdrop blur.
- Top hairline gradient (mirror of top bar).
- **Left cluster:** icon + primary status in `fg` + dim suffix (e.g. connection state).
- **Middle (optional, sm+):** secondary status.
- **Right cluster:** optional compliance/security hint; **version** in mono (`v0.1.0`).

Use **small icons** (14–16px), `text-2xs`, relaxed tracking. Reads as **ambient status**, not a loading bar.

---

## Loading / progress patterns

**Full-page or section overlay (long tasks)**

- **Modal glass:** `border-cx-accent/35`, `bg-cx-deep/92`, `backdrop-blur-md`.
- **Radial + diagonal gradients** using `accent` / `accent2` at low opacity (~6–14%).
- **Step list** with icons and short labels—swap icons/labels to match your flow (upload, sync, build, etc.).
- **Framer Motion:** `AnimatePresence`, opacity ~0.22s.

**Inline progress**

- Prefer a **thin bar** (`h-1`–`h-1.5`) with `rounded-full`, track `cx-border`, fill **gradient** `accent → accent2` or solid `accent`.
- Label above in 2xs caps; never rely on color alone—add text state.

---

## Surfaces: cards & panels (glass pattern)

- Outer: `rounded-2xl`, `border border-cx-border`, `bg-cx-panel/75`, **backdrop-blur-xl**.
- **Inset ring:** subtle inner top highlight.
- Optional **gradient wash** diagonal `from-white/[0.045]` for depth.
- **Hero** variant: slightly larger radius, stronger border (`borderStrong`), `bg-cx-raised/50`.

**Density**

- Default padding `p-6`; dense areas `p-4`.

---

## Buttons & chips

- **Ghost / secondary:** `border-cx-border`, `bg-white/[0.03]`, hover `borderStrong`, `bg-white/[0.05]`.
- **Primary emphasis:** border `accent/25–40`, text `accent` or `fg` on dark fill.
- **Filter chips:** small rounded-md, count in parentheses, muted; active = `borderStrong` + `panel` bg; disabled/hidden = strikethrough + reduced opacity.

---

## Icons

- **Library:** Lucide (or match stroke weight 1.75–2).
- **Accent icons:** `text-cx-accent` or `accent/90`.
- Avoid filled emoji-style icons for primary chrome.

---

## Motion

- **Page/shell:** spring layouts for nav width and main (`stiffness ~420`, `damping ~38`).
- **Micro:** 0.2–0.35s ease `[0.22, 1, 0.36, 1]` (smooth deceleration).
- Avoid bouncy overshoot on navigation; keep springs **tight and professional**.

---

## Background texture (optional)

- Main content area: **very subtle** gradient `from-white/[0.02]` diagonal.
- Hero / landing: optional **mesh-radial** stack (cyan / violet / mint ellipses at low opacity).
- Optional faint **grid** (~56px) for technical or data-heavy pages.

---

## Accessibility & UX guardrails

- Maintain **4.5:1** contrast for body text on `cx-panel` / `cx-deep`.
- Focus rings: `accent` at ~20–40% opacity, 1px–2px.
- **Do not** stack semi-transparent panels over interactive canvases (graphs, maps, editors)—put **toolbars above** or **side inspectors** beside the canvas.

---

## One-paragraph “mega prompt” (paste into any AI or brief)

> Build a **dark enterprise-style web app shell** using a **cx** color system: void/deep/panel backgrounds (`#040508`–`#10141d`), **cyan** (`#5ec8f2`) and **violet** (`#9b8bd4`) accents, **Inter + Outfit** typography, **hairline borders** (`rgba(148,163,184,0.09–0.11)`) and **glass panels** (rounded-2xl, backdrop-blur, inset highlight). Layout: **collapsible left nav rail** (76↔248px spring), **fixed top bar** (3.25rem, blur, global search + context chips + optional workspace selector), **scrollable main**, optional **right dock** with left border + dock shadow, **thin bottom status strip** (connection/sync/version). Use **Lucide** icons (stroke ~1.75), **Framer Motion** for restrained springs, and **loading** as glass overlays or slim gradient progress bars—not chunky default bars. Mood: **precise, calm, trustworthy**—suitable for any professional product, not tied to a specific domain.

---

## If you do **not** have the original source code

**You do not need any original codebase.** This document is meant to stand alone:

1. **Tokens** — Copy the **Color system** table into your design tool (Figma variables), CSS custom properties, or Tailwind `theme.extend` (same hex/rgba values).
2. **Shell** — Implement the **Global shell layout** ASCII structure: nav rail + top bar + scrollable main + optional right dock + bottom strip. Heights and flex rules are spelled out in each section.
3. **Components** — **Surfaces**, **Buttons & chips**, **Loading**, and **Top bar** / **Nav** sections are enough to build equivalents in any framework (no dependency on our `GlassPanel` source).
4. **Motion** — Use the numeric spring/easing hints with Framer Motion, CSS, or your animation library of choice.
5. **AI workflow** — Paste the **mega prompt** plus the **Color system** + **Global shell layout** sections into your assistant; ask it to output tokens + component structure for your stack.

**Optional handoff:** Export a small `design-tokens.json` (or CSS variables file) from your implementation and share that with your team—same idea as this doc, machine-readable.

---

## Optional: reference implementation (if available)

If a reference repo is available, use its shell and token files to compare behavior or copy code. If no repo is available, skip this section and use only the specs above.

| Area | Typical location in a codebase |
|------|----------|
| Design tokens (`cx.*` colors, shadows, fonts) | `tokens/`, `theme/`, `styles/` (for example: `tailwind.config.*`, `theme.ts`, `variables.css`) |
| App shell layout | `src/shell/`, `src/layout/`, or root app scaffold files |
| Nav rail, top bar, status strip, right dock | `src/shell/*` or `src/components/layout/*` |
| Glass panel component | shared UI layer (for example `src/ui/GlassPanel.*`) |
| Loading/progress overlay | `src/components/*` near upload/index/sync flows |

If your team publishes tokens separately, point users to **this markdown + your tokens file** so the design can be recreated without private repository access.

---

*This prompt is **domain-agnostic** and **stack-agnostic**: reproduce the **visual and structural DNA** for a redesign or a new app; swap routing, state, and copy to match your product.*
