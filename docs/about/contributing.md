# Contributing

How to contribute to Kiso the project.

This page covers contributing to Kiso itself (bug reports, features, code). For extending Kiso with new plugins, see [How Kiso extensions work](../extending/how-extensions-work.md).

## Reporting bugs

File bug reports on [GitHub Issues](https://github.com/pegasus-isi/kiso/issues).

A good bug report includes:

- Kiso version (`kiso version`)
- Python version (`python --version`)
- Operating system
- The experiment config file (or a minimal reproduction)
- The full error output (run with `kiso --debug` for verbose output)
- What you expected to happen vs what actually happened

## Proposing features

Open a [GitHub Issue](https://github.com/pegasus-isi/kiso/issues) with the label `enhancement`. Describe:

- The use case you are trying to address
- Your proposed solution (optional, but helpful)
- Alternatives you considered

Large or breaking changes should be discussed in an issue before submitting a PR.

## Development setup

```bash
# Clone the repo
git clone https://github.com/pegasus-isi/kiso.git
cd kiso

# Install in development mode with all dependencies
pip install -e ".[all]"

# Install pre-commit hooks
pre-commit install
```

## Running the test suite

```bash
# Full test suite with coverage (recommended)
tox -e py311

# Direct pytest
pytest --cov=src --no-cov-on-fail tests/

# Single test file
pytest tests/test__main__.py

# Single test function
pytest tests/test__main__.py::test_check
```

All tests must pass before submitting a PR.

## Code style

| Tool         | Purpose                                                 |
| ------------ | ------------------------------------------------------- |
| `ruff`       | Linter and formatter (black-compatible, line length 88) |
| `mypy`       | Type checking                                           |
| `pre-commit` | Runs all checks automatically on commit                 |

Run all checks manually:

```bash
pre-commit run --all-files
```

Run individual tools:

```bash
# Lint and format
ruff check --fix src/ tests/
ruff format src/ tests/

# Type check
mypy src/
```

**Code style conventions:**

- Google-style docstrings
- Type annotations required for all public functions and methods
- No `print()` — use `logging` instead

## Commit conventions

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/). The pre-commit hook (commitizen) enforces this.

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `build`, `chore`.

Examples:

```
feat(fabric): add floating IP support
fix(htcondor): correctly configure IPv6 trust domain
docs: add multi-testbed tutorial
```

## Pull request process

1. Fork the repository and create a branch from `main`
1. Make your changes with tests
1. Ensure `pre-commit run --all-files` and `tox -e py311` pass
1. Submit a PR against `main`
1. A maintainer will review and either approve, request changes, or close with explanation

PRs should be focused — one feature or bug fix per PR. Do not mix unrelated changes.

## How decisions are made

Kiso is developed at USC Information Sciences Institute. Maintainers review and merge PRs. For significant design decisions, open a GitHub Issue first to discuss before investing time in an implementation.

## See also

- [How Kiso extensions work](../extending/how-extensions-work.md) — adding new plugins
- [Contact](contact.md) — reaching the team
- [GitHub Issues](https://github.com/pegasus-isi/kiso/issues)
