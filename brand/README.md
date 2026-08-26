# varimo brand assets

**Product name:** varimo (always lowercase, never "Varimo" or "VARIMO")
**Tagline:** Many originals from one master
**Direction:** *Echo* — the final "o" of the wordmark repeats and fades outward.

The repo, the Python package (`variant_maker/`), the CLI (`variant-maker`, `variant-farm`,
`variant-server`) and the GitHub repo name are unchanged. `varimo` is the product name only.

## Files

Canonical artwork (brand colours):

| File | Use |
|---|---|
| `logo.svg` | Full lockup — wordmark + tagline. Decks, docs, anywhere with room. |
| `wordmark.svg` | Wordmark only, four-echo. |
| `logo-mark.svg` | Three-echo icon, transparent background. |
| `source/` | Everything as delivered by the designer — PNG lockups, icon tiles, mono and favicon SVGs. |

Studio exports (generated, aqua-tinted — see *Colour* below):

| File | Use |
|---|---|
| `../web/app/icon.svg` | Browser tab icon. Two-ring simplification. |
| `../web/app/favicon.ico` | Legacy tab icon, 16/32/48/64. |
| `../web/app/apple-icon.png` | 180×180 iOS home-screen icon. |
| `../web/components/brand/VarimoMark.tsx` | The in-app mark. Takes its colour from `currentColor`. |

Regenerate the raster exports after any geometry change:

```bash
python3 brand/render-app-icons.py
```

## Colour

The kit ships in brand violet. **Studio tints the mark to the app's existing aqua** so the
nav matches the surrounding chrome — the palette in `web/app/globals.css` is unchanged.

| Name | Hex | Use |
|---|---|---|
| Ink | `#14131A` | Brand primary surface |
| Violet | `#A473F5` | Brand accent, echoes |
| Violet deep | `#7C4FCC` | Brand accent on light backgrounds |
| Mint | `#5FDCB2` | Reserved: "verified original" |
| Paper | `#FBFAFC` | Brand light surface |
| **Studio aqua** | **`#16c8d3`** | **What the mark actually renders as in-app** |
| **Studio ink** | **`#172124`** | **Icon tile in-app** |

## Type

- Wordmark & headings: Sora 700 / 600, tracking −4% (Google Fonts)
- Body & UI: Space Grotesk 400 / 500 — Studio uses Geist for UI copy; Sora is loaded for
  the wordmark only, via `--font-brand` in `web/app/globals.css`.
- Eyebrows & tagline: Space Grotesk 500, uppercase, +30–38% tracking

The SVGs use live text. Outline the type before sending anything to print.

## Construction

- `x` = x-height of the "o"
- Clear space on all sides = 1x
- Echo offset = 0.885x per copy (letters overlap; never letterspaced)
- Opacity ramp = 100 / 50 / 24 / 10%
- Tagline sits 0.5x below the baseline

## Minimum sizes

- **120px wide** — full four-echo lockup
- **80px wide** — reduce to two echoes
- **Below 80px** — icon only; **below 32px** use the two-ring favicon

`VarimoMark` applies the last rule itself: it renders three echoes at 32px and up, two
below that.

## Don't

- Letterspace the wordmark
- Colour echoes individually — one accent, fading
- Substitute the typeface or use a lighter weight
- Place violet echoes on a violet background — use the one-colour knockout
  (`source/varimo-icon-mono.svg`)
- Capitalise the name
