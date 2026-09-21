# hook-variants — spec v1

Local CLI. One source clip + one seed string → **3–5** overlay-only MP4s whose
on-screen type resembles common TikTok boxed captions or Instagram Edits–style
outline captions.

Implementation contract (signatures): `docs/CONTRACT.md`. Shared types:
`hook_variants/types.py`. If this file and the contract disagree on a function
name or argument, **the contract wins**. If they disagree on numbers for slots
or style ids, **`types.py` wins**.

This package is standalone. It does not import a uniqueness engine, a detector,
or an app-provenance faker.

---

## 0. What this is not

- Not a uniqueness pack (no SSIM bits, no peer distance, no VMAF floor).
- Not a detector or “would the platform catch this” model.
- Not Edits / TikTok provenance spoofing (no project JSON, no app watermark
  clone, no signing).
- Not a duplicate-bypass tool. **Native-looking text does not mean Instagram
  (or anyone) will treat the file as a different original.**

---

## 1. Product flow

```
probe(video) -> VideoInfo
plan_hooks(seed, count, master_seed, locked, source_text, allow_mid) -> OverlayPlan
optional: apply --preset override and/or placement.json
for each HookParams:
    wrap_text + build_ass
    render_variant  ->  .ass + .mp4 + .jpg (still)
write overlay_plan.json
optional: handoff(run_dir, dest) -> mp4 copies + HANDOFF.md
```

`expand_hooks`, `plan_hooks`, `build_ass`, `wrap_text`, `load_styles` are **pure**
(aside from `load_styles` reading disk). Same inputs → same outputs. They must
be unit-tested without ffmpeg.

ffmpeg is used only in `probe`, `render`, and (for a still preview) `place`.

Default count is **5**. Product use is **3–5**. CLI accepts **1–8**.

---

## 2. Public API

From `docs/CONTRACT.md`:

| Module | Function | Pure? | Result |
|---|---|---|---|
| `styles.load_styles(root)` | id → `StylePreset` | yes (disk) | all `STYLE_IDS` |
| `expand.expand_hooks(seed, n, *, locked, rng)` | list[str] | yes | length `n` |
| `plan.plan_hooks(seed, count, master_seed, *, locked, source_text, allow_mid)` | `OverlayPlan` | yes | |
| `ass.build_ass(hook, style, width, height, duration_s)` | ASS string | yes | |
| `ass.wrap_text(text, style, width, height)` | wrapped text | yes | ASS `\N` breaks |
| `probe.probe(path)` | `VideoInfo` | no (ffprobe) | |
| `render.render_variant(...)` | writes mp4 + still + ass | no | |
| `handoff.export_for_lab(run_dir, dest)` | copy mp4s + `HANDOFF.md` | no | |

CLI:

```
hook-variants <video> --text "…" [-n 5] [--preset auto] [--lock-text] [--source-text none] [--out DIR]
hook-variants place [--port]
hook-variants handoff RUN DEST
```

Also accepted on render (not all printed in the one-line contract): `--seed`,
`--allow-mid`, `--placement PATH`.

---

## 3. Types (`hook_variants/types.py`)

### Slots

```
Slot = "top" | "mid" | "low"
SLOTS      = ("top", "mid", "low")
SAFE_SLOTS = ("top", "low")

SLOT_Y = {
    "top": 0.16,
    "mid": 0.45,
    "low": 0.62,
}
```

`SLOT_Y` is a **fraction of frame height** for ASS **Alignment=8** (top-center).

```
MarginV = round(SLOT_Y[slot] * PlayResY)
```

Example, 1080×1920:

| slot | y | MarginV |
|---|---|---|
| `top` | 0.16 | 307 |
| `mid` | 0.45 | 864 |
| `low` | 0.62 | 1190 |

**Default plan never uses `mid`.** `mid` is allowed only when:

1. CLI `--allow-mid` is set, so `plan_hooks(..., allow_mid=True)`, or
2. `hook-variants place` wrote `placement.json` with `slot: "mid"` (see §8).

v1 has **no free-form y**. If a file has `slot` and `y` that disagree with
`SLOT_Y`, reject the file.

### Style ids

```
tiktok-classic-box
edits-classic-outline
edits-strong
```

No other ids in v1.

### StylePreset

| field | role |
|---|---|
| `id` | one of `STYLE_IDS` |
| `font_file` | path relative to `fonts/` (basename ok) |
| `font_name` | ASS `Fontname` (must match the file’s name table) |
| `size_frac` | font size as a fraction of **frame height** → `Fontsize = round(size_frac * height)` |
| `primary_ass` | ASS PrimaryColour `&HAABBGGRR` |
| `outline_ass` | OutlineColour |
| `back_ass` | BackColour (box fill when `BorderStyle=3`) |
| `outline` | ASS `Outline` |
| `shadow` | ASS `Shadow` |
| `box` | `True` → `BorderStyle=3`, else `1` |
| `max_lines` | wrap cap |
| `max_width_frac` | wrap width as a fraction of frame width |
| `bold` | ASS `Bold` -1/0 |

### HookParams

| field | meaning |
|---|---|
| `index` | `0 .. count-1` |
| `text` | final on-screen string (**before** wrap; wrap happens in `ass`) |
| `style_id` | preset id |
| `slot` | `top` / `mid` / `low` |
| `source` | `"expand"` or `"lock"` (default in the dataclass is `"expand"`) |

`to_dict()` is `dataclasses.asdict`.

### OverlayPlan

| field | meaning |
|---|---|
| `seed_text` | normalized seed |
| `count` | `len(hooks)` |
| `master_seed` | string used to seed the plan RNG |
| `hooks` | `list[HookParams]` |
| `locked` | `--lock-text` |
| `source_text` | v1: always `"none"` |

`to_dict()`:

```json
{
  "seed_text": "this is why it hits",
  "count": 5,
  "master_seed": "…",
  "locked": false,
  "source_text": "none",
  "hooks": [
    {
      "index": 0,
      "text": "this is why it hits",
      "style_id": "tiktok-classic-box",
      "slot": "low",
      "source": "expand"
    }
  ]
}
```

Write this as `overlay_plan.json` in the run directory.

### VideoInfo

`path`, `width`, `height`, `duration_s`, `fps`, `has_audio`. Probe only; no hash.

---

## 4. Presets (v1)

Loaded by `styles.load_styles(root)` from `root/styles/presets.json`.
`root` is the `hook-variants/` directory (the folder that contains `fonts/`
and `styles/`). Fonts are **already vendored** under `fonts/` with OFL
license files. Do not fetch. Do not use APK fonts.

Canonical records (keep `styles/presets.json` in sync; do not invent a fourth id):

| id | font_file | font_name | size_frac | outline | shadow | box | max_lines | max_width_frac | bold | back_ass |
|---|---|---|---|---|---|---|---|---|---|---|
| `tiktok-classic-box` | `TikTokSans-Regular.ttf` | TikTok Sans | 0.048 | 8 | 0 | true | 3 | 0.80 | false | `&H90000000` |
| `edits-classic-outline` | `InstrumentSans-Regular.ttf` | Instrument Sans | 0.052 | 6 | 0 | false | 3 | 0.80 | true | `&H00000000` |
| `edits-strong` | `Anton-Regular.ttf` | Anton | 0.062 | 3 | 0 | false | 1 | 0.88 | false | `&H00000000` |

All three: `primary_ass` `&H00FFFFFF`, `outline_ass` `&H00000000`.

Look summary:

- `tiktok-classic-box` — white on a `BorderStyle=3` black bar (TikTok Sans OFL)
- `edits-classic-outline` — white + heavy outline (Instrument Sans OFL; lookalike of IG Classic, not the app font)
- `edits-strong` — one short line, light outline (Anton OFL)

`--preset auto` (default): leave `plan_hooks` style assignments.
`--preset <id>`: after planning, set every `hook.style_id` to that id.

---

## 5. Seed expansion

`expand.expand_hooks(seed, n, *, locked, rng) -> list[str]`

### Normalize

1. `seed.strip()`
2. Collapse any internal whitespace (including newlines) to a single space
3. If the result is empty → `ValueError`
4. `n` must be in `1..5` → else `ValueError`

The normalized string is what `OverlayPlan.seed_text` stores.

### Locked (`locked=True`)

Return `[normalized] * n`. Every string is **exactly** the normalized seed.
`plan_hooks` then tags each `HookParams.source = "lock"`.

### Unlocked (`locked=False`)

Return a list of length `n`.

1. Index `0` is always the normalized seed.
2. Later indices are **surface variants** of that same seed, chosen with `rng`
   from a **closed transform list**. A transform that equals the seed or a
   already-chosen string is skipped. If the list runs out, repeat the
   normalized seed (do not invent filler words to pad uniqueness).
3. `plan_hooks` tags `source = "expand"`.

**Allowed transforms (closed set):**

| id | behavior |
|---|---|
| `identity` | normalized seed (always index 0; do not draw again) |
| `lower` | `.lower()` |
| `upper` | `.upper()` only if `len(normalized) <= 24` |
| `strip_punct` | strip trailing `.!?…` |
| `end_period` | if no terminal `.!?` then add `.` |
| `two_line` | insert one ASS-destined break: replace the last space before the midpoint with `\n` (stored as a real newline in the Python string; `wrap_text` / `build_ass` turn newlines into `\N`). Only if there is a space |

**Forbidden:**

- LLM / HTTP
- synonym lists
- adding words that are not in the seed (`wait`, `POV`, emoji, hashtags)
- changing meaning (no negation, no inserted numbers)

`rng` is a `random.Random` instance provided by `plan_hooks`. Tests pass
`random.Random(0)`.

---

## 6. Planning

`plan.plan_hooks(seed, count, master_seed, *, locked, source_text, allow_mid) -> OverlayPlan`

1. `source_text` must be `none`, `bottom`, or `top`. `bottom` keeps text off the
   lower band (`top`, plus `mid` if allowed). `top` keeps text off the upper
   band (`low`, plus `mid` if allowed). No OCR.
2. Normalize seed (same rules as expand). Empty → `ValueError`.
3. `rng = random.Random(int(hashlib.sha256(master_seed.encode()).hexdigest()[:16], 16))`
4. `texts = expand_hooks(normalized, count, locked=locked, rng=rng)`
5. For `i, text` in `enumerate(texts)`:
   - `style_id = STYLE_IDS[i % 3]` then optionally swap with a later id using
     `rng` so a 5-pack is not a fixed ABCAB every seed. **Must be deterministic.**
     Simplest legal rule: `style_id = STYLE_IDS[(i + rng.randrange(3)) % 3]`
     computed **once per index in order** (do not reshuffle the whole list
     after the fact in a way tests cannot replay).
   - Recommended deterministic assignment (use this):
     `style_id = STYLE_IDS[(start + i) % 3]` where
     `start = rng.randrange(3)` is drawn **once** before the loop.
   - `slot`: if `allow_mid`: `slots = SLOTS` else `slots = SAFE_SLOTS`.
     `slot = slots[(i + slot_start) % len(slots)]` with
     `slot_start = rng.randrange(len(slots))` drawn once.
6. Build `HookParams(index=i, text=text, style_id=style_id, slot=slot, source=…)`.

CLI `--seed` is `master_seed`. If omitted: `master_seed = sha256(normalized_seed)[:16]`
(hex).

`--allow-mid` is the only way the **plan** can contain `mid`. A later placement
file can still override slots (including to `mid`) without this flag.

---

## 7. ASS and last-stage burn-in

### wrap_text

`wrap_text(text, style, width, height) -> str`

- Input may contain `\n` from the `two_line` expand transform.
- Measure with a simple **character budget**:
  `max_chars = max(4, int(style.max_width_frac * width / (style.size_frac * height * 0.55)))`
  (0.55 is a crude glyph-width guess. Keep it as a named constant.)
- Greedy word wrap. Join lines with `\N` for ASS.
- If lines would exceed `style.max_lines`, keep the first `max_lines - 1` full
  lines and ellipsize the last (`…`) so the string still fits the budget.
- `edits-strong` (`max_lines=1`): never emit `\N`; ellipsize a long seed.

### build_ass

`build_ass(hook, style, width, height, duration_s) -> str`

Minimum script:

```
[Script Info]
ScriptType: v4.00+
PlayResX: <width>
PlayResY: <height>
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,<font_name>,<Fontsize>,<primary>,&H00000000,<outline>,<back>,<bold>,0,0,0,100,100,0,0,<border>,<outline_w>,<shadow>,8,<ml>,<mr>,<mv>,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,<end>,Hook,,0,0,0,,<wrapped>
```

- `Fontsize = round(style.size_frac * height)`
- `border = 3` if `style.box` else `1`
- `ml` / `mr` = `round((1 - style.max_width_frac) * width / 2)`
- `mv` = `round(SLOT_Y[hook.slot] * height)`
- `<end>` = `duration_s` formatted as ASS time `H:MM:SS.cc`
- `fontsdir` is **not** in the ASS; ffmpeg gets `-fontsdir`

Pass `fontsdir` to ffmpeg so `Fontname` resolves to the vendored file
(`-fontsdir <root>/fonts`).

### Last-stage burn-in

`render.render_variant` must apply the overlay as the **last** video filter.

```
ffmpeg -y -i <video> -vf ass=<ass_path> -fontsdir <fonts> ... <out.mp4>
```

If any other `-vf` is ever added (none in v1), `ass=` stays last.

v1 does **not**:

- crop, scale, pad, fps-convert, or grade
- change duration or speed
- strip or rewrite color as a product feature (whatever ffmpeg needs to encode
  a playable MP4 is fine; do not add a second color library)

Audio: keep duration aligned with video. Stream-copy audio if the container
allows; otherwise AAC at source-ish rate. Do not time-stretch.

### render_variant signature (contract is `...`; use this)

```python
def render_variant(
    video: Path,
    hook: HookParams,
    style: StylePreset,
    info: VideoInfo,
    out_dir: Path,
    *,
    fonts_dir: Path,
) -> RenderResult: ...
```

`RenderResult` (local dataclass, not in `types.py` unless you add it) has
`mp4`, `ass`, `still`, `cmd` (the argv list or a joined string).

Filenames:

```
{stem}_h{index:02d}.ass
{stem}_h{index:02d}.mp4
{stem}_h{index:02d}.jpg
```

`stem` is the source video stem (`clip.mp4` → `clip`).

Still: after the MP4 exists, extract one frame at
`t = min(1.0, info.duration_s / 2.0)` from the **output** MP4 (text must be
visible). JPEG is fine. This is a **look still** for a human. It is not a
quality score and must not be fed into a uniqueness metric.

### Default `--out`

`out/{stem}-hooks`  
Example: `clip.mp4` → `out/clip-hooks/`.

---

## 8. placement.json

Written by `hook-variants place`. Optionally read by the render CLI.

### Schema (`hook-variants.placement.v1`)

```json
{
  "schema": "hook-variants.placement.v1",
  "written_by": "place",
  "slot": "low",
  "y": 0.62,
  "allow_mid": false,
  "width": 1080,
  "height": 1920,
  "source_video": "clip.mp4"
}
```

| field | rule |
|---|---|
| `schema` | must be `hook-variants.placement.v1` |
| `written_by` | `place` when the placer wrote it; `manual` if someone edited it |
| `slot` | `top` \| `mid` \| `low` |
| `y` | must equal `SLOT_Y[slot]` (float compare with 1e-6) |
| `allow_mid` | `true` if `slot == "mid"`; otherwise `false` unless the operator enabled mid and then picked top/low |
| `width`, `height` | frame used in the placer still; informational |
| `source_video` | basename or path; informational |

Reject:

- unknown `schema`
- `y` not matching `SLOT_Y[slot]`
- `slot == "mid"` AND `allow_mid` is false AND `written_by != "place"`

The placer may write `slot: "mid"` with `allow_mid: true` and
`written_by: "place"`. That is enough to use mid **without** `--allow-mid`.

### Apply at render

1. If `--placement PATH` is given, load it.
2. Else if `./placement.json` exists, load it.
3. Else no override.
4. On load, set **every** `hook.slot` to `placement.slot` (v1 is one slot per run).
5. Do not change text or style.

`hook-variants place [--port]`

- Default port `8765`
- Localhost only
- Show one still of a user-selected or last-probed clip (file input on the page is enough)
- Three controls: Top, Low, Mid
- Save `placement.json` in cwd (or `--out` if you add it later; cwd is enough for v1)

---

## 9. Handoff contract

`handoff.export_for_lab(run_dir, dest)`

CLI: `hook-variants handoff RUN DEST`  
Example: `hook-variants handoff out/clip-hooks ./lab-inbox`

### Behavior

1. `run_dir` must exist and contain at least one `*.mp4`. Else raise.
2. Create `dest` (and parents) if needed.
3. Copy each `*.mp4` from `run_dir` onto `dest` (same basename). Overwrite
   same names. Do **not** copy `.ass`, `.jpg`, `.json`.
4. Write `dest/HANDOFF.md` (overwrite).

### HANDOFF.md template

```
# hook-variants handoff

These MP4s are overlay-only: source pixels plus a last-stage ASS burn-in.
They are not uniqueness-tested. They are not a detector result.
They do not fake Edits or any app provenance.
Native-looking text is not a duplicate bypass.

## Run
- run_dir: <abs or given path>
- seed_text: <from overlay_plan.json if present, else unknown>
- master_seed: <…>
- locked: <…>
- count: <n mp4s>

## Files
- clip_h00.mp4
- clip_h01.mp4
…
```

If `run_dir/overlay_plan.json` exists, fill Run from it. If it is missing,
still write the file; use `unknown` for plan fields.

Do not invent scores. Do not write `platform_result`. Do not call a Lab
package.

---

## 10. CLI details

| item | value |
|---|---|
| render entry | `hook-variants <video> --text "…"` |
| `--text` | required on render |
| `-n` / `--count` | default 5, min 1, max 8 |
| `--preset` | `auto` (default) or a `StyleId` |
| `--lock-text` | sets `locked=True` |
| `--source-text` | `none` (default), `bottom`, or `top` |
| `--out` | default `out/<stem>-hooks` |
| `--seed` | optional `master_seed` |
| `--allow-mid` | optional; plan only |
| `--placement` | optional path |
| `place` | `--port` default 8765 |
| `handoff` | two positional args: `RUN`, `DEST` |

Exit codes: `0` ok; `2` bad args; `3` missing ffmpeg `ass` filter; `4` missing
font; `1` other runtime error.

Before render, check `ffmpeg -filters` contains `ass`. Message: install ffmpeg
with libass; this tool will not proceed.

---

## 11. Layout

```
hook-variants/
  pyproject.toml
  README.md
  PLAN.md
  fonts/                 # vendored OFL + license text (already present)
  styles/                # preset JSON read by load_styles
  docs/
    CONTRACT.md
    spec.md
  hook_variants/
    __init__.py
    types.py
    cli.py
    styles.py
    expand.py
    plan.py
    ass.py
    probe.py
    render.py
    handoff.py
    place.py
  tests/
    test_styles.py
    test_expand.py
    test_plan.py
    test_ass.py
    test_handoff.py
    test_place.py
    test_cli.py
    test_render.py       # integration
    fixtures/
```

---

## 12. Legal

- Ship only **OFL** font files plus their license notices under `fonts/`.
- Never rip fonts from Instagram, Edits, TikTok, or any APK/IPA.
- Instrument Sans is documented as an OFL **lookalike** of IG Classic, not as
  the app font.
- Do not claim a platform partnership or an official caption engine.

---

## 13. Honest limit

A pack that *looks* like in-app type is still the same clip plus burned text.
Platforms match video many ways. This tool does not measure or defeat that.
`HANDOFF.md` and the README must keep saying so.
