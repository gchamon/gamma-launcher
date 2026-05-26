# Repository Guidelines

## Project Structure & Module Organization

`launcher/` contains the Python package for the CLI. Command entrypoints live in
`launcher/commands/`, while mod metadata, installers, and downloaders live under
`launcher/mods/`. Shared archive, hash, bootstrap, and config helpers are in the
top-level `launcher/` modules. Tests are in `tests/`, with reusable fixtures and
sample archives in `tests/data/`. Container and packaging support lives in
`Dockerfile`, `easy-install/`, and `.github/workflows/`.

## Build, Test, and Development Commands

Build the project container:

```sh
podman build -t gamma-launcher .
```

Run the CLI from the container:

```sh
podman run -it --rm -p 127.0.0.1:6080:6080 -v ./:/app:Z gamma-launcher --help
```

Run tests only inside the container, not directly on the host:

```sh
podman run --rm -v ./:/app:Z --entrypoint="" gamma-launcher uv run pytest
```

The container includes runtime dependencies such as `libunrar` and Firefox
support that local environments may not have.

## Coding Style & Naming Conventions

Use Python 3.10+ syntax, 4-space indentation, and the existing naming style:
`snake_case` for functions and variables, `PascalCase` for classes, and concise
module-level constants where needed. Keep changes scoped to the command,
downloader, installer, or helper module that owns the behavior. Avoid broad
refactors when fixing a narrow issue.

## Testing Guidelines

Tests are run exclusively with `pytest`. Name test modules `tests/test_*.py` and
keep fixtures in `tests/data/`. Existing `unittest.TestCase` tests are still
collected by pytest, but new tests should prefer plain pytest style. Add focused
tests for downloader, installer, and command behavior when changing those areas.
Agents must always run tests through the container so results match the
supported runtime.

## Commit & Pull Request Guidelines

Recent commits use short imperative messages, sometimes with a scope such as
`tests: Adding test case for ...`. Keep commits focused and describe the user
visible behavior when applicable. Pull requests should include a concise
description, linked issues where relevant, and the exact container test command
that was run. Include screenshots only for browser or visible UI changes.
