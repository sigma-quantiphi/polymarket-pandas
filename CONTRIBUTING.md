# Contributing to polymarket-pandas

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/sigma-quantiphi/polymarket-pandas.git
cd polymarket-pandas
uv pip install -e ".[dev]"
```

## Running Checks

```bash
uv run ruff check polymarket_pandas/   # lint
uv run ruff format polymarket_pandas/  # format
uv run mypy polymarket_pandas/         # type check
uv run pytest tests/test_unit.py -v    # tests (mocked, no API keys needed)
```

## Pull Requests

1. Fork the repo and create a feature branch from `main`.
2. Add tests for new functionality.
3. Ensure all checks pass (`ruff`, `mypy`, `pytest`).
4. Open a PR with a clear description of the change.

## Reporting Issues

Open an issue at https://github.com/sigma-quantiphi/polymarket-pandas/issues with:
- What you expected vs what happened
- Minimal reproduction steps
- Python version and `polymarket-pandas` version
