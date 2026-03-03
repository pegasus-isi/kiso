# Kiso

Kiso is an experiment management platform that executes experiments defined as Pegasus workflows on various computing infrastructures (Chameleon Cloud, FABRIC, Vagrant). Built on top of EnOSlib for infrastructure provisioning.

# Common Commands

## Development Setup

```sh
pip install -e ".[all]"
pre-commit install
```

## Running Tests

```sh
# Full test suite with coverage (via tox, recommended)
tox -e py311

# Direct pytest
pytest --cov=src --no-cov-on-fail tests/

# Single test file
pytest tests/test__main__.py

# Single test function
pytest tests/test__main__.py::test_check
```

## Linting and Formatting

```sh
# Run all pre-commit checks
pre-commit run --all-files

# Ruff only
ruff check --fix src/ tests/
ruff format src/ tests/
```

## Type Checking

```sh
mypy src/
```

## Documentation

```sh
tox -e docs
# Or manually: cd docs && make html
```

# Architecture

## Plugin System (Entry Points)

Kiso uses Python entry points (`pyproject.toml`) for plugin discovery. Three plugin groups exist:

- **`kiso.software`** — Software installers (Docker, Apptainer, Ollama)
- **`kiso.deployment`** — Deployment systems (HTCondor)
- **`kiso.experiment`** — Experiment runners (Pegasus, Shell)

Plugins are loaded at runtime via `utils.get_runner()`, `utils.get_software()`, and `utils.get_deployment()` in `src/kiso/utils.py`. Configuration and JSON schemas are built dynamically by querying all registered entry points (`src/kiso/configuration.py`, `src/kiso/schema.py`).

## Plugin Interface

Each plugin subpackage (e.g., `src/kiso/docker/`, `src/kiso/pegasus/`) follows the same structure:

- `installer.py` or `runner.py` — Main class with `__init__()`, `check()`, and `__call__()` methods
- `configuration.py` — Dataclass for typed config
- `schema.py` — JSON schema dict for validation

Software/deployment installers use Ansible playbooks (`main.yml`) for remote execution via EnOSlib.

## CLI Commands

Entry point: `kiso = "kiso.__main__:kiso"` (Click-based via rich-click)

Four commands map to functions in `src/kiso/task.py`:

- `kiso check` — Validate experiment YAML against composed JSON schema
- `kiso up` — Provision infrastructure, install software/deployments
- `kiso run` — Execute experiments on provisioned resources
- `kiso down` — Tear down resources

## Task Decorators

Functions in `task.py` use stacked decorators:

- `@validate_config` — Parses and validates YAML config
- `@enostask` — EnOSlib task/environment framework
- `@check_provisioned` — Ensures resources exist before run/down

## Configuration Flow

YAML config → JSON schema validation → `dacite.from_dict()` into dynamically-constructed dataclasses. The dataclass types are assembled at import time from all registered plugins.

# Code Style

- Formatter/linter: ruff (black-compatible, line length 88)
- Docstrings: Google style
- Type annotations required
- Conventional commits enforced by commitizen pre-commit hook
