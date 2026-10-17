"""Farm config: global defaults + per-client overrides (preset/count/platform/quality).

Pure `from_dict` core (no I/O, no deps) + a thin `load()` that parses the YAML contract.
Validation is fail-fast: a typo'd preset/platform/quality is caught here, not 15 minutes
into a sweep when a hands-off worker would otherwise mark every video failed.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..platforms import PLATFORMS
from ..presets import PRESETS

QUALITIES = ("fast", "hq")
_DEFAULT_DEFAULTS = {"preset": "medium", "count": 10, "platform": "reels", "quality": "fast"}


class ConfigError(ValueError):
    """Raised on a malformed or invalid farm config."""


@dataclass(frozen=True)
class AuthConfig:
    """Exactly one auth method: a service-account JSON key, or an OAuth user token (the
    no-downloadable-key path for orgs that block service-account keys)."""
    service_account_json: str | None = None
    oauth_token: str | None = None


@dataclass(frozen=True)
class Recipe:
    preset: str
    count: int
    platform: str
    quality: str  # "fast" | "hq"


@dataclass(frozen=True)
class ClientConfig:
    name: str
    input_folder_id: str
    output_folder_id: str
    recipe: Recipe


@dataclass(frozen=True)
class FarmConfig:
    auth: AuthConfig
    defaults: Recipe
    poll_minutes: int
    clients: dict[str, ClientConfig]


def _validate_recipe(r: Recipe, where: str) -> None:
    if r.preset not in PRESETS:
        raise ConfigError(f"{where}: unknown preset {r.preset!r}; choose from {sorted(PRESETS)}")
    if r.platform not in PLATFORMS:
        raise ConfigError(f"{where}: unknown platform {r.platform!r}; choose from {sorted(PLATFORMS)}")
    if r.quality not in QUALITIES:
        raise ConfigError(f"{where}: unknown quality {r.quality!r}; choose from {list(QUALITIES)}")
    if not isinstance(r.count, int) or r.count < 1:
        raise ConfigError(f"{where}: count must be a positive integer, got {r.count!r}")


def from_dict(raw: dict) -> FarmConfig:
    auth_raw = raw.get("auth") or {}
    sa = auth_raw.get("service_account_json")
    oauth = auth_raw.get("oauth_token")
    if sa and oauth:
        raise ConfigError("auth: set exactly one of service_account_json / oauth_token, not both")
    if not sa and not oauth:
        raise ConfigError("auth requires service_account_json or oauth_token")

    defaults_raw = {**_DEFAULT_DEFAULTS, **(raw.get("defaults") or {})}
    defaults = Recipe(
        preset=defaults_raw["preset"], count=defaults_raw["count"],
        platform=defaults_raw["platform"], quality=defaults_raw["quality"],
    )
    _validate_recipe(defaults, "defaults")

    clients_raw = raw.get("clients") or {}
    if not clients_raw:
        raise ConfigError("at least one client is required")

    clients: dict[str, ClientConfig] = {}
    for name, c in clients_raw.items():
        c = c or {}
        in_id = c.get("input_folder_id")
        out_id = c.get("output_folder_id")
        if not in_id:
            raise ConfigError(f"client {name!r}: input_folder_id is required")
        if not out_id:
            raise ConfigError(f"client {name!r}: output_folder_id is required")
        if in_id == out_id:
            raise ConfigError(
                f"client {name!r}: input_folder_id and output_folder_id must be different"
            )
        recipe = Recipe(
            preset=c.get("preset", defaults.preset),
            count=c.get("count", defaults.count),
            platform=c.get("platform", defaults.platform),
            quality=c.get("quality", defaults.quality),
        )
        _validate_recipe(recipe, f"client {name!r}")
        clients[name] = ClientConfig(name=name, input_folder_id=in_id,
                                     output_folder_id=out_id, recipe=recipe)

    return FarmConfig(
        auth=AuthConfig(service_account_json=sa, oauth_token=oauth),
        defaults=defaults,
        poll_minutes=int(raw.get("poll_minutes", 15)),
        clients=clients,
    )


def load(path: str) -> FarmConfig:
    """Parse the YAML farm config at `path`. Requires the [farm] extra (PyYAML)."""
    try:
        import yaml
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ConfigError("PyYAML is required to load a config file; install the [farm] extra") from e
    with open(path) as f:
        return from_dict(yaml.safe_load(f) or {})
