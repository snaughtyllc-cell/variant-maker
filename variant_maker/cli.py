"""CLI entry point. Options are fully wired so `variant-maker --help` works today;
the run body is filled in Phase 7."""
from __future__ import annotations

import click

from . import __version__


@click.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False))
@click.option("-n", "--count", default=5, show_default=True, help="number of variants")
@click.option("--preset", default="medium", type=click.Choice(["subtle", "medium", "strong"]),
              show_default=True)
@click.option("--platform", default="none",
              type=click.Choice(["reels", "tiktok", "shorts", "none"]), show_default=True)
@click.option("--quality", "quality_mode", default="fast",
              type=click.Choice(["fast", "hq"]), show_default=True,
              help="fast = Tier-1 CPU only; hq = Tier-2 neural")
@click.option("--seed", default=None, type=int, help="master seed (random if omitted)")
@click.option("-o", "--out", default="./output", show_default=True, type=click.Path())
@click.option("--quality-floor", default=90.0, show_default=True, help="VMAF floor")
@click.option("--max-regen", default=3, show_default=True)
@click.option("--rotate", default="safe", type=click.Choice(["never", "safe"]), show_default=True)
@click.option("--flip", default="never", type=click.Choice(["never", "always"]), show_default=True)
@click.option(
    "--us-metadata", is_flag=True,
    help="strip source tags, then write Apple / US location / creation_time",
)
@click.option("--jobs", default=1, show_default=True)
@click.option("--dry-run", is_flag=True, help="print plan + commands, render nothing")
@click.option(
    "--look-first", is_flag=True,
    help="one medium encode + source/variant stills; look gate, no uniqueness hunt",
)
@click.option(
    "--ssim-align-diag", is_flag=True,
    help="Lab diagnostic: compare fractional vs trim-aligned SSIM. "
         "Does not change the 24-bit uniqueness gate. "
         "Env VARIANT_SSIM_ALIGN_DIAG=1 also enables. Off by default.",
)
@click.option(
    "--auto-tune/--no-auto-tune", default=None,
    help="bisect strength to the uniqueness target (default: on for Fast, off for HQ)",
)
@click.option(
    "--copyid", default=None,
    type=click.Choice(["off", "record", "gate"]),
    help="off=SSIM only (default); record=log visual/audio heads; gate=fuse min uniqueness. "
         "Env VARIANT_MAKER_COPYID when omitted.",
)
@click.option("-v", "--verbose", is_flag=True)
@click.version_option(version=__version__)
def main(**config):
    """Generate N look-good variants of INPUT plus a manifest."""
    from . import pipeline, uniqueness
    m = pipeline.run(config)
    if config.get("look_first") and m.variants:
        v = m.variants[0]
        click.echo(
            f"look {v.look_status} mae={v.look_mae} max={getattr(v, 'look_mae_max', None)} "
            f"stills={v.look_src or '-'} {v.look_var or '-'}"
        )
    if uniqueness.ssim_align_diag_wanted(config):
        for v in m.variants:
            diag = (v.quality or {}).get("ssim_align_diag") or {}
            if diag.get("error"):
                click.echo(f"v{v.index:02d} ssim-align-diag error={diag['error']}")
                continue
            frac = (diag.get("fractional") or {}).get("bits")
            aligned = (diag.get("aligned") or {}).get("bits")
            delta = diag.get("bits_delta")
            if frac is None and aligned is None:
                continue
            click.echo(
                f"v{v.index:02d} ssim-align-diag fractional={frac} aligned={aligned} "
                f"bits_delta={delta} (24-bit gate unchanged)"
            )


if __name__ == "__main__":
    main()
