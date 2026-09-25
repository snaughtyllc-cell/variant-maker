# hook-variants

Local CLI. One clip + one seed hook → **3–5** on-screen text variants that read like common TikTok / Instagram Edits captions.

The tool plans hook copy, writes an ASS subtitle, and **burns it in last** with ffmpeg `libass`. It does not rewrite the clip’s pixels beyond that overlay.

This folder is a **standalone package**. It has its own `pyproject.toml`, tests, and CLI. It does not import another video pipeline.

## What this is not

- **Not Lab uniqueness.** No SSIM bits, no VMAF, no uniqueness gate, no look-MAE pass/fail. A still is for your eyes, not a score.
- **Not a detector.** It does not predict whether a platform will flag, suppress, or accept the file.
- **Not Edits provenance spoofing.** It does not fake Instagram Edits, TikTok, or any app’s project file, metadata, watermark, or signing. OFL fonts + ASS styling only.

**Honest caveat:** native-looking on-screen text is not an Instagram duplicate bypass. A caption that resembles in-app type does not make the video a new original and does not change how a platform matches media.

## Requirements

- Python 3.11+
- ffmpeg built with **libass** (the `ass` filter)

```bash
ffmpeg -filters | grep ass
```

You need a line that includes `ass`. If that command prints nothing, this tool cannot burn text.

## Install

From this folder (`hook-variants/`):

```bash
pip install -e ".[dev]"
```

That installs the `hook-variants` console script. Dev extra is pytest.

## Usage

Default pack (auto style mix, expanded copy, 5 outputs):

```bash
hook-variants clip.mp4 --text "this is why it hits" -n 5
```

Same words on every copy, one style (Instrument Sans outline):

```bash
hook-variants clip.mp4 --text "this is why it hits" --lock-text --preset edits-classic-outline
```

Local placer (pick `top` / `low`; `mid` only here or with `--allow-mid`):

```bash
hook-variants place
```

Copy finished MP4s plus a `HANDOFF.md` into an inbox directory:

```bash
hook-variants handoff out/clip-hooks ./lab-inbox
```

### CLI (render)

```
hook-variants <video> --text "…" [-n 5] [--preset auto] [--lock-text] [--source-text none] [--out DIR]
```

| Flag | Default | Meaning |
|---|---|---|
| `--text` | required | Seed hook. The only copy input in v1. |
| `-n` / `--count` | `5` | How many variants. Product range is 3–5; CLI allows 1–8. |
| `--preset` | `auto` | `auto` or one of the three style ids. `auto` assigns styles from the seeded plan. A named preset overwrites every hook’s `style_id` after planning. |
| `--lock-text` | off | Every variant uses the normalized seed string. No expansion. |
| `--source-text` | `none` | Avoid stacking on an existing band: `none` \| `bottom` (only top/mid) \| `top` (only low/mid). No OCR. |
| `--out` | `out/<stem>-hooks` | Run directory (plan JSON, ASS, MP4, stills). |
| `--seed` | hash of `--text` | `master_seed` for the plan RNG. Same seed + same flags → same plan. |
| `--allow-mid` | off | Let the default plan use the mid slot. Off: only `top` and `low`. |
| `--placement` | `./placement.json` if present | Force every hook to the file’s slot. A placer-written mid slot is valid without `--allow-mid`. |

Subcommands: `place [--port]`, `handoff RUN DEST`.

## Presets

| id | Look | Font (OFL) | ASS notes |
|---|---|---|---|
| `tiktok-classic-box` | TikTok-style boxed caption | **TikTok Sans** (OFL) | White fill, `BorderStyle=3` black bar |
| `edits-classic-outline` | Instagram Classic–like outline | **Instrument Sans** (OFL lookalike of IG Classic) | White fill, heavy black outline, no box |
| `edits-strong` | Heavy display wordmark | **Anton** (OFL) | One short line, light outline |

`--preset auto` rotates these. It does not invent a fourth style.

## Slots

| slot | `y` (fraction of frame height) | When |
|---|---|---|
| `top` | `0.16` | Default plan may use |
| `low` | `0.62` | Default plan may use |
| `mid` | `0.45` | Only `hook-variants place` or `--allow-mid` |

`y` is **Alignment=8** (top-center) `MarginV` = `round(y * height)`. v1 does not take a free-form y.

## Legal (fonts)

- **OFL only.** Ship the license text next to each family under `fonts/`.
- **Never rip app fonts** from Instagram, Edits, TikTok, or any APK / IPA / app bundle / web asset pack.
- Instrument Sans is a **lookalike** of IG Classic, not the app font and not a substitute for a license you do not have.

## Output of one run

Example: `out/clip-hooks/`

- `overlay_plan.json` — `OverlayPlan.to_dict()` (reproduction of copy, style, slot)
- `<stem>_h00.ass` … — the burned-in script (also kept as a sidecar)
- `<stem>_h00.mp4` … — overlay-only encode
- `<stem>_h00.jpg` … — one look still per variant (review; not a score)

Handoff copies **MP4s + `HANDOFF.md` only**. Stills and ASS stay in the run dir.

## Split this folder into its own git repo later

This tree is already a complete package root (`pyproject.toml` at `hook-variants/`). To make it a separate repository later, do **not** merge it into another app repo. Copy or split **this directory**.

**Simplest (copy, no parent history):**

```bash
cp -a hook-variants /tmp/hook-variants-repo
cd /tmp/hook-variants-repo
git init
git add .
git commit -m "Initial commit: hook-variants"
git remote add origin <new-empty-remote-url>
git branch -M main
git push -u origin main
```

**If you want history for this folder only** (from whatever parent currently tracks it):

```bash
# run from the parent repo root
git subtree split --prefix=hook-variants -b hook-variants-export

mkdir -p /tmp/hook-variants-repo
cd /tmp/hook-variants-repo
git init
git pull <path-to-parent-repo> hook-variants-export
git remote add origin <new-empty-remote-url>
git push -u origin main
```

After the split, keep implementing **only** in that new repo. Do not add imports the other way.

## Docs

- `docs/CONTRACT.md` — function signatures Codex must implement (do not rewrite)
- `docs/spec.md` — product + architecture
- `PLAN.md` — execution order
