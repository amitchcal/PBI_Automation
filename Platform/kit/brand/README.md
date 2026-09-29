# Brand kit (F-05)

One JSON file describes a client's brand. `build_brand.py` turns it into everything the platform needs, so swapping the file restyles the web app, the Power BI theme and the deck.

```
python build_brand.py kits/meridian.json     # dummy kit A (blue, sans-serif)
python build_brand.py kits/harbor.json       # dummy kit B (red, serif) to prove the swap
```

Outputs go to `out/<kit>/`:

| File | Used by |
|---|---|
| `web/tokens.css`, `web/tailwind.brand.json` | Web app (CSS variables, Tailwind theme extension) |
| `powerbi/theme.json` | Power BI report theme (checked against the official theme schema 2.156) |
| `deck/deck_theme.json`, `deck/brand_sample.pptx` | Deck builder (colours, fonts, sample slides) |
| `logo-mark.png/.svg`, `logo-full.png`, `logo-full-light.png` | Header, login, deck title slide (light version for dark backgrounds) |
| `preview.html` | One-page preview of the web look and the readability checks |

## Kit file fields
- `name`, `tagline`
- `logo`: `{ "generate": true, "mark": "bars" | "ring" }` for a dummy logo, or `{ "path": "...", "pathLight": "..." }` for the client's own files
- `palette`: primary, secondary, accent, positive, warning, negative, background, surface, border, text, muted (all `#RRGGBB`), plus `dataColors` (6 to 8 chart colours)
- `fonts`: `heading`, `body` (fonts installed on viewers' machines, for Power BI), `webStack` (CSS font stack for the web app)
- `shape.radius`

## Checks run on every build
- Kit fields present and valid colours.
- Readability (WCAG contrast): text, muted text, white on primary and on secondary must reach 4.5:1; primary on surface 3:1. A failure stops the build. Status colours are warnings only.
- Generated Power BI theme validated against the official schema.
