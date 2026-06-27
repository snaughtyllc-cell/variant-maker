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
@click.option("--rotate", default="never", type=click.Choice(["never", "safe"]), show_default=True)
@click.option("--flip", default="never", type=click.Choice(["never", "always"]), show_default=True)
@click.option("--jobs", default=1, show_default=True)
@click.option("--dry-run", is_flag=True, help="print plan + commands, render nothing")
@click.option("-v", "--verbose", is_flag=True)
@click.version_option(version=__version__)
def main(**config):
    """Generate N look-good variants of INPUT plus a manifest."""
    from . import pipeline
    pipeline.run(config)


if __name__ == "__main__":
    main()
