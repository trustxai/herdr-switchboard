# Contributing

Thanks for helping. Switchboard is deliberately small: one Python script, standard library
only, no build step. Most of the rules below exist to keep it that way.

## Setup

You need:

- Python 3.9 or newer. 3.9 is the floor because it is the `/usr/bin/python3` that macOS ships.
- [fzf](https://github.com/junegunn/fzf) 0.71 or newer, to run the plugin (Ubuntu's apt package
  is older; install a release from the fzf repository or use Homebrew).
- `make`, `git` and a POSIX shell.

Optional, and only for the checks:

- [uv](https://docs.astral.sh/uv/), so `make lint` can run the pinned ruff without installing
  anything into the project (a `ruff` on your `PATH` works too);
- [gitleaks](https://github.com/gitleaks/gitleaks), for `make secrets`;
- [pre-commit](https://pre-commit.com), for the hooks in `.pre-commit-config.yaml`
  (`pre-commit install`).

There is nothing to install for the plugin itself. Clone the repository and run the tests.

## Running the tests

```sh
make test                      # python3 tests/test_switchboard.py
PYTHON=python3.9 make test     # the same suite with another interpreter
make lint                      # byte-compile, ruff, shell syntax, no bytecode left behind
make check                     # test + lint + secrets: everything CI runs
```

The suite is a single file that you can also run directly with
`python3 tests/test_switchboard.py`; it prints `ok` when everything passes. It never talks to a
real herdr, never opens an ssh connection and never touches your clipboard: it runs the program
against a fake `herdr` and fake fixtures. Keep it that way. A test that focuses or renames
panes in your real herdr session would move you around while you work.

CI runs the suite on Ubuntu and macOS with Python 3.9 and the newest stable Python, plus
`make lint` and a gitleaks scan of the whole history. `make check` runs the same targets
locally; ruff and gitleaks are skipped with a message when they are not installed.

## Code rules

- **One file, standard library only.** No third-party imports, no vendored packages.
- **Python 3.9 syntax.** No `match`, no `X | Y` in annotations that are evaluated (use
  `Optional[X]` or `Union[X, Y]`), no parenthesised context managers, no `from __future__`.
  ruff (`make lint`) and the 3.9 CI jobs catch most of it.
- **Every child process gets `stdin=subprocess.DEVNULL`.** The popup owns the terminal; a child
  that reads from it swallows keystrokes, and fzf closes as if Esc had been pressed.
- **Every user-visible string goes through the translation table**, in English and Spanish.
- **No bytecode in the tree.** The tests must not write `__pycache__`; `make lint` fails if they
  do.

When you add a behaviour, add the test that covers it, then break the code on purpose and check
that the test goes red. A test that cannot fail does not protect anything.

## The fixture rule

Tests, fixtures, demo data, screenshots, recordings and examples never contain:

- a real hostname;
- a company or client name, real or invented;
- an IP address;
- an e-mail address;
- a path under a real home directory.

Use the names the demo uses. Machines are `laptop`, `workstation` and `server`; workspaces are
`api`, `web`, `infra` and `docs`. The same rule applies to commit messages, pull request text and
issue reports: describe your setup with those names, not your own.

## Commits and pull requests

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `docs:`, `test:`, `ci:`, `chore:`, `refactor:`. Say in the body why the change is needed.
- Keep pull requests small and focused, and fill in the template.
- `make check` must pass before you ask for a review.
- A change users will notice gets a line under `## [Unreleased]` in `CHANGELOG.md`.

## Releases

Versioning is manual. A release bumps `version` in `herdr-plugin.toml`, moves the `Unreleased`
entries of `CHANGELOG.md` under the new version with its date, and is tagged `vX.Y.Z` on `main`.

The tools CI downloads are pinned by hand: fzf and gitleaks in
`.github/scripts/install-pinned.sh` (version and SHA-256 of each archive), uv in
`.github/workflows/ci.yml`, ruff in the `Makefile` and `.pre-commit-config.yaml`. Dependabot
keeps the GitHub Actions current.

## Security

Do not report vulnerabilities in public issues. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE), the same as the rest of the project. There is no CLA.
