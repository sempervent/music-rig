"""Optional machine-local path configuration (never committed)."""

from __future__ import annotations

from pathlib import Path

import yaml

from music_rig.models import LOCAL_PATH_KEYS, LocalConfig
from music_rig.store import ROOT, StoreError

LOCAL_CONFIG_NAME = ".rig.local.yaml"
LOCAL_CONFIG_EXAMPLE_NAME = ".rig.local.example.yaml"


def local_config_path(root: Path | None = None) -> Path:
    return (root or ROOT) / LOCAL_CONFIG_NAME


def local_config_example_path(root: Path | None = None) -> Path:
    return (root or ROOT) / LOCAL_CONFIG_EXAMPLE_NAME


def load_local_config(
    path: Path | None = None,
    *,
    root: Path | None = None,
) -> LocalConfig | None:
    """Load optional local config. Missing file returns None (not an error)."""
    target = path or local_config_path(root)
    if not target.exists():
        return None
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid YAML in {target.name}: {exc}") from exc
    if raw is None:
        return LocalConfig()
    if not isinstance(raw, dict):
        raise StoreError(f"{target.name} must contain a YAML mapping")
    paths = raw.get("paths")
    if paths is not None:
        if not isinstance(paths, dict):
            raise StoreError(f"{target.name}: paths must be a mapping")
        unknown = sorted(set(paths) - LOCAL_PATH_KEYS)
        if unknown:
            raise StoreError(
                f"{target.name}: unknown path locator key(s): {', '.join(unknown)}"
            )
    try:
        return LocalConfig.model_validate(raw)
    except Exception as exc:
        raise StoreError(f"Local config validation failed: {exc}") from exc


def resolve_path(
    locator_key: str,
    config: LocalConfig | None,
) -> Path | None:
    """Return configured path for a locator key, or None if unset."""
    if config is None:
        return None
    if locator_key not in LOCAL_PATH_KEYS:
        return None
    value = getattr(config.paths, locator_key, None)
    if value is None or not str(value).strip():
        return None
    return Path(str(value)).expanduser()


def has_any_configured_path(config: LocalConfig | None) -> bool:
    if config is None:
        return False
    return any(
        getattr(config.paths, key) not in (None, "")
        for key in sorted(LOCAL_PATH_KEYS)
    )


def save_local_config(
    config: LocalConfig,
    *,
    path: Path | None = None,
    root: Path | None = None,
) -> Path:
    """Write machine-local config (gitignored). Never touches canonical data/."""
    target = path or local_config_path(root)
    payload = config.model_dump(mode="json")
    # Drop empty nested defaults for readability
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    )
    target.write_text(text, encoding="utf-8")
    return target


def update_agent_config(
    *,
    provider: str | None = None,
    fallback: str | None = None,
    cursor_executable: str | None = None,
    cursor_model: str | None = None,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
    argv: list[str] | None = None,
    root: Path | None = None,
) -> LocalConfig:
    """Merge agent settings into local config and save."""
    existing = load_local_config(root=root) or LocalConfig()
    agent = existing.agent.model_copy(deep=True)
    if provider is not None:
        agent.provider = provider
    if fallback is not None:
        agent.fallback = fallback or None
    if cursor_executable is not None:
        agent.cursor.executable = cursor_executable or None
    if cursor_model is not None:
        agent.cursor.model = cursor_model or None
    if ollama_base_url is not None:
        agent.ollama.base_url = ollama_base_url
    if ollama_model is not None:
        agent.ollama.model = ollama_model or None
    if argv is not None:
        agent.argv = list(argv)
    updated = existing.model_copy(update={"agent": agent}, deep=True)
    save_local_config(updated, root=root)
    return updated
