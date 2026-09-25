# hook-variants — implementation contract

Standalone package. **Forbidden:** `import variant_maker`, Studio routes, Lab uniqueness/VMAF/look.

## Public API

| Module | Function | Pure? |
|---|---|---|
| `styles.load_styles(root)` | id → `StylePreset` | yes (disk) |
| `expand.expand_hooks(seed, n, *, locked, rng)` | list[str] | yes |
| `plan.plan_hooks(seed, count, master_seed, *, locked, source_text, allow_mid)` | `OverlayPlan` | yes |
| `ass.build_ass(hook, style, width, height, duration_s)` | ASS string | yes |
| `ass.wrap_text(text, style, width, height)` | wrapped text | yes |
| `probe.probe(path)` | `VideoInfo` | no (ffprobe) |
| `render.render_variant(...)` | writes mp4 + still + ass | no |
| `handoff.export_for_lab(run_dir, dest)` | copy mp4s + HANDOFF.md | no |

CLI: `hook-variants <video> --text "…" [-n 5] [--preset auto] [--lock-text] [--source-text none] [--out DIR]`

Subcommands: `hook-variants place [--port]`, `hook-variants handoff RUN DEST`

## Presets (v1)

1. `tiktok-classic-box` — TikTok Sans, white, BorderStyle=3 black bar
2. `edits-classic-outline` — Instrument Sans, white, heavy black outline
3. `edits-strong` — Anton, one short line, light outline

Slots: `top` y=0.16, `low` y=0.62. `mid` y=0.45 only if `--allow-mid` or placer. Default plan never uses mid.

Fonts live in `fonts/` with OFL licenses. Never extract from Instagram/Edits/TikTok APKs.
