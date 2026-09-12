# Testing architecture

The suite is organized by **test level** and **product module**, not by delivery stage.

## Layout

```
tests/
  conftest.py              # root fixtures (e.g. tui_fx), interpreter guards
  fixtures/                # shared YAML repos, fake providers
  helpers/                 # CliRunner wrappers and other utilities
  unit/                    # fast, isolated, no full CLI/TUI workflows
  integration/             # service + CLI + fixture-repo workflows
  smoke/                   # thin production-readonly / CLI surface checks
```

Each of `unit/`, `integration/`, and `smoke/` has a `conftest.py` that applies
`pytest.mark.unit`, `pytest.mark.integration`, or `pytest.mark.smoke` to every
test in that tree via `pytest_collection_modifyitems` (directory-scoped
auto-marking).

Subdirectories under those roots mirror product areas (`agent/`, `reconciliation/`,
`tui/`, `question_lifecycle/`, etc.).

## Markers

Registered in `pyproject.toml`:

| Marker        | Meaning                                      |
|---------------|----------------------------------------------|
| `unit`        | Pure logic / models / registries             |
| `integration` | Fixture repos, services, CLI, TUI pilots     |
| `smoke`       | Read-only prod baseline or CLI surface       |

Filter examples:

```bash
uv run pytest -m unit -n0 --cov-fail-under=0
uv run pytest -m 'integration or smoke' -q
```

## CLI helpers

Prefer `tests.helpers.cli` over ad-hoc `CliRunner` usage:

- `invoke_rig_human(*args)` — human actor (default)
- `invoke_rig_bot(*args)` — prepends `--am-bot`

## Fixtures

Stage-era isolated repos (`fx15`, `fx17`, `fx19`, `fx20`, `fx21`, `iso`, …) live in
`tests/fixtures/` (notably `repo_fixtures.py`) so split modules share one definition.

Root `tui_fx` remains in `tests/conftest.py` for TUI mutation isolation.

**Never mutate production `data/` from tests.** Smoke tests that read production
YAML must be read-only.

## Coverage gate

Full suite (CI / local validation) enforces **80%** via `pyproject.toml`
`addopts` (`--cov-fail-under=80`):

```bash
uv run pytest -q
```

Subset / debug without the gate:

```bash
uv run pytest -m unit --cov-fail-under=0
uv run pytest -m integration --cov-fail-under=0
uv run pytest -m smoke --cov-fail-under=0
uv run pytest path/to/tests -n0 --cov-fail-under=0
```

CLI (`music_rig.cli`) and TUI packages are omitted from coverage; domain and
service modules are the gate.

## Lint gates

Ruff (Python) and ryl (YAML) are configured in `pyproject.toml`. Pre-commit
runs them via local `uv run` system hooks (no duplicated rule config):

```bash
uv run pre-commit run --all-files
# or directly:
uv run ruff check --fix .
uv run ruff format .
uv run ryl check .
```

Docs build (CI + local quality gate):

```bash
uv run mkdocs build --strict
```

## Reconciliation

See [reconciliation.md](reconciliation.md) for module ownership, authority flow,
and where CLI suggestions are rendered. Manual load benchmarks:

```bash
uv run python scripts/bench_reconciliation.py
```

