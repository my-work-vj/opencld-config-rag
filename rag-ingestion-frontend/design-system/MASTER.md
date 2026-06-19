# OpenCLD RAG — Design System (Master)

Product: AI developer platform for building and managing multi-RAG pipelines.

## Pattern & Style
- **Pattern**: Sidebar + content area (SaaS dashboard)
- **Style**: Dark-first minimal SaaS with subtle glass surfaces and indigo accent
- **Mood**: Professional, technical, trustworthy — 2026 AI tooling standard

## Colors (semantic tokens)
| Token | Light | Dark (default) |
|-------|-------|----------------|
| background | slate-50 | slate-950 |
| surface | white | slate-900/80 |
| surface-elevated | slate-100 | slate-800/60 |
| border | slate-200 | slate-700/60 |
| primary | indigo-600 | indigo-500 |
| primary-hover | indigo-500 | indigo-400 |
| text | slate-900 | slate-100 |
| text-muted | slate-600 | slate-400 |
| success | emerald-600 | emerald-400 |
| warning | amber-600 | amber-400 |
| error | red-600 | red-400 |

## Typography
- **UI**: Inter (system fallback: ui-sans-serif)
- **Code / endpoints**: JetBrains Mono
- Base 16px, line-height 1.5, scale: 12 / 14 / 16 / 18 / 24 / 32

## Effects
- Border radius: 8px (inputs), 12px (cards), 16px (panels)
- Shadows: subtle elevation on cards in dark mode
- Motion: 150–200ms ease-out; respect `prefers-reduced-motion`

## Anti-patterns
- No emoji as icons (Lucide only)
- No placeholder-only form labels
- No horizontal scroll on mobile
- Touch targets ≥ 44px
