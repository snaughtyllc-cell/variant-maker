# PLAN.md — hook-variants (Codex)

Phased, test-driven. Execute **in this folder only** (`hook-variants/`).
Write the failing test first, implement to green, then refactor.
**Stop at each checkpoint** before the next phase.

Status legend: done when the listed tests are green and the checkpoint is written.

---

## Constraints (do not violate)

Read before any code.

- **OFL only.** Fonts live in `fonts/` and are **already vendored** (plus their OFL
  text). Wire `styles.load_styles` to those files. Do not download fonts. Do not
  add a font installer.
- **No APK fonts.** Never extract, copy, or “match by file hash” fonts from
  Instagram, Edits, TikTok, or any APK / IPA / app bundle / CDN asset pack.
- **No IG API.** No Graph API, no unofficial Instagram/TikTok clients, no login,
  no upload, no scrape.
- **No duplicate-bypass claims.** Docs, CLI help, `HANDOFF.md`, and comments must
  not say this evades, spoofs, or beats a platform duplicate check. Native-look
  text is a caption style, not a bypass.
- **No Lab imports.** Do not `import` any package outside `hook_variants` except
  stdlib / pytest. No uniqueness, VMAF, look-MAE, or quality-guard code. Handoff
  is a file copy + `HANDOFF.md`, not a score.

If a step would need any of the above, skip the step and stop.

---

## Phase 0 — Tree check (no new product code)

Already present:

- `pyproject.toml` — package `hook-variants`, script `hook-variants = hook_variants.cli:main`, pytest marker `integration`
- `hook_variants/types.py` — `Slot`, `SLOT_Y`, `StylePreset`, `HookParams`, `OverlayPlan`, `VideoInfo`
- `docs/CONTRACT.md` — public signatures (do not edit)
- `docs/spec.md` — behavior
- `styles/presets.json` — three `StylePreset` records
- `fonts/` — already vendored: `TikTokSans-Regular.ttf`, `InstrumentSans-Regular.ttf`, `Anton-Regular.ttf` plus `OFL-*.txt` (do not replace with app fonts)

Public loader is `styles.load_styles(root)` per CONTRACT (pass the `hook-variants/` directory). Do not drop the `root` argument.

**Acceptance:** `pip install -e ".[dev]"` from `hook-variants/` succeeds.
`hook_variants.types` imports. Do not implement `cli.py` yet if you only need the install.

---

## Phase 1 — Styles from disk

**Module:** `hook_variants/styles.py`  
**Contract:** `styles.load_styles(root) -> dict[str, StylePreset]` (pure; reads disk)

- `root` is the package root (the directory that contains `fonts/` and style JSON).
- Load the three ids in `STYLE_IDS`. Unknown extra files are ignored.
- Each preset’s `font_file` resolves under `fonts/` and the file exists.
- Numeric / ASS fields match `docs/spec.md` § Presets.

**Tests (`tests/test_styles.py`), no ffmpeg:**

- `load_styles(root)` returns exactly the three ids
- `font_file` paths exist
- `tiktok-classic-box.box is True`
- `edits-classic-outline.box is False` and `outline` is the heavy value
- `edits-strong.max_lines == 1`

**Checkpoint:** print the three `font_name` values. They must be TikTok Sans,
Instrument Sans, Anton — not an app-extracted name.

---

## Phase 2 — Seed expansion (pure)

**Module:** `hook_variants/expand.py`  
**Contract:** `expand.expand_hooks(seed, n, *, locked, rng) -> list[str]`

Rules are in `docs/spec.md` § Seed expansion. Summary:

- Normalize seed (strip, collapse whitespace). Empty seed → `ValueError`
- `n` in 1..5
- `locked=True` → `n` copies of the normalized seed, identical
- `locked=False` → length `n`; index 0 is the normalized seed; later items are
  **closed-set surface transforms** only (case / punctuation / line breaks).
  No synonyms, no LLM, no network
- Same `(seed, n, locked, rng state)` → same list

**Tests (`tests/test_expand.py`):**

- locked: all equal, length `n`
- unlocked: length `n`, `[0] == normalized seed`
- unlocked: deterministic with `random.Random(0)`
- unlocked: no transform adds words that are not in the seed (except `\N` line breaks)
- empty seed raises

**Checkpoint:** unit tests green. No ffmpeg.

---

## Phase 3 — Plan (pure)

**Module:** `hook_variants/plan.py`  
**Contract:** `plan.plan_hooks(seed, count, master_seed, *, locked, source_text, allow_mid) -> OverlayPlan`

- Derive `random.Random` from `master_seed` (see spec). Call `expand_hooks`.
- `HookParams.source` is `"lock"` if `locked` else `"expand"`.
- Assign `style_id` by seeded rotation through `STYLE_IDS` (auto).
- Assign `slot` from `SAFE_SLOTS` (`top`, `low`) unless `allow_mid`, then `SLOTS`.
- **Default (`allow_mid=False`) never sets `slot="mid"`.**
- `source_text` must be `"none"` in v1; anything else → `ValueError`.
- `OverlayPlan.to_dict()` matches spec.

**Tests (`tests/test_plan.py`):**

- same `master_seed` → same `to_dict()`
- `allow_mid=False` → every `slot` in `SAFE_SLOTS`
- `allow_mid=True` → mid **may** appear (seed a case that does, or inject)
- `locked=True` → every `text` equal, `source == "lock"`
- `source_text="ocr"` (or any non-`none`) raises
- `count` matches `len(hooks)` and `OverlayPlan.count`

**Checkpoint:** unit tests green.

---

## Phase 4 — ASS (pure)

**Module:** `hook_variants/ass.py`  
**Contract:**

- `ass.wrap_text(text, style, width, height) -> str`
- `ass.build_ass(hook, style, width, height, duration_s) -> str`

- `PlayResX/Y` = frame size
- Alignment **8**, `MarginV = round(SLOT_Y[slot] * height)`
- `BorderStyle=3` iff `style.box` else `1`
- Dialogue spans `0` .. `duration_s`
- Wrap respects `max_lines` and `max_width_frac` (character budget is fine; no HarfBuzz required)
- `edits-strong` stays one line (truncate with an ellipsis if needed, spec)

**Tests (`tests/test_ass.py`):**

- top / low / mid each produce the expected `MarginV` for 1080×1920
- box preset emits `BorderStyle=3`
- outline preset emits `BorderStyle=1` and the heavy `Outline`
- wrap of a long string has at most `max_lines` lines (`\N`)
- `PlayResX: 1080` / `PlayResY: 1920` present

**Checkpoint:** unit tests green. No ffmpeg.

---

## Phase 5 — Probe

**Module:** `hook_variants/probe.py`  
**Contract:** `probe.probe(path) -> VideoInfo`

ffprobe only. Fields: `path`, `width`, `height`, `duration_s`, `fps`, `has_audio`.
No sha256. No color-tag pipeline.

**Tests:** fixture clip if present; otherwise skip unless `ffmpeg` exists.
Geometry and `has_audio` match ffprobe.

---

## Phase 6 — Render + look stills

**Module:** `hook_variants/render.py`  
**Contract:** `render.render_variant(...)` writes **mp4 + still + ass** (see spec for the exact signature).

- Build ASS to disk first
- ffmpeg: **`ass=` is the last video filter** (last-stage burn-in)
- Do not crop, scale, retime, or grade
- Audio: re-encode or copy only as needed to keep A/V; do not change duration
- Still: one JPEG at `min(1.0, duration_s / 2)` **after** burn-in

**Tests (`tests/test_render.py`, `@pytest.mark.integration`):**

- skip if `ffmpeg -filters` has no `ass`
- output mp4 exists and duration is within 0.15s of source
- `.ass` sidecar exists and matches what was burned
- `.jpg` exists and size > 0
- the ffmpeg argv string contains `ass=` after any other `-vf` filters (or is the only `-vf`)

**Checkpoint — look stills (human):** open the three preset stills. Confirm: boxed
TikTok-like bar, heavy outline, Anton one-liner. If a still looks like a ripped
app font or a watermark clone, stop and revert styling — do not “fix” by
extracting an APK font.

---

## Phase 7 — CLI render

**Module:** `hook_variants/cli.py` — `main`

- `hook-variants <video> --text …` as in README / CONTRACT
- Probe → `plan_hooks` → optional `--preset` override → each `render_variant`
- Write `overlay_plan.json` in `--out`
- If `--placement` is set, or `placement.json` exists in cwd, apply it (spec)
- Exit nonzero on empty text, missing ffmpeg `ass`, missing font file

**Tests (`tests/test_cli.py`):** `--help` lists `place` and `handoff`; argv
parser accepts the README examples (can mock render).

**Checkpoint:**
`hook-variants --help` and one dry parse of
`hook-variants clip.mp4 --text "this is why it hits" -n 5`.

---

## Phase 8 — Placer

**Module:** `hook_variants/place.py` (or `cli` subcommand)

- `hook-variants place [--port]`
- Local HTTP server, default port **8765**
- Operator picks `top` / `low` / `mid`
- Writes `placement.json` (`hook-variants.placement.v1`, spec)
- Choosing `mid` is allowed here (this is the mid gate)

**Tests (`tests/test_place.py`):**

- writer produces valid schema
- `slot=mid` ⇒ `y == 0.45` and `allow_mid` true
- `slot=top` ⇒ `y == 0.16`
- reader rejects `slot=mid` if `allow_mid` is false **and** `written_by` is not `place`

Keep the page minimal (one still + three buttons). No accounts.

---

## Phase 9 — Handoff

**Module:** `hook_variants/handoff.py`  
**Contract:** `handoff.export_for_lab(run_dir, dest)`

- Create `dest` if needed
- Copy `*.mp4` from `run_dir` (not jpg, not ass, not json)
- Write `dest/HANDOFF.md` from the spec template
- `HANDOFF.md` must include the overlay-only sentence and must **not** include
  uniqueness numbers, detector language, or bypass language

**Tests (`tests/test_handoff.py`):** temp dirs; mp4s copied; extra files not
copied; `HANDOFF.md` exists; forbidden substrings absent (`bypass`, `vmaf`,
`uniqueness`).

**Checkpoint:**
`hook-variants handoff out/clip-hooks ./lab-inbox` on a fake run dir.

---

## Phase 10 — Pack smoke (integration)

With ffmpeg + fonts + a short fixture:

```bash
hook-variants tests/fixtures/clip.mp4 --text "this is why it hits" -n 3 --out out/clip-hooks
hook-variants clip.mp4 --text "this is why it hits" --lock-text --preset edits-classic-outline
hook-variants place   # optional; or unit-test the writer
hook-variants handoff out/clip-hooks ./lab-inbox
```

**Acceptance:** 3 mp4s + 3 stills + `overlay_plan.json`; inbox has mp4s + `HANDOFF.md`.
`pytest -q` green. `pytest -q -m integration` green when ffmpeg has `ass`.

---

## Done / do not add

Stop after Phase 10. Do not add:

- uniqueness / VMAF / look-MAE gates
- Instagram or TikTok upload
- a fourth preset
- free-form y (keep `SLOT_Y`)
- mid in the default plan
- any import from outside this package
