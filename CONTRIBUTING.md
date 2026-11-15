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

The suite must not hang either. Each block announces itself on stderr and has a 120-second
watchdog: past it, the run ends with every thread's stack (file, line, function) and the
block's name. A child started on a pseudo-terminal is reaped through `finish()`, which keeps
reading its terminal while it waits and kills its process group past a bound: a wait that stops
reading can block forever on macOS, where an exiting session leader first waits for its
terminal's output to drain.

CI runs the suite on Ubuntu and macOS with Python 3.9 and the newest stable Python, plus
`make lint` and a gitleaks scan of the whole history. `make check` runs the same targets
locally; ruff and gitleaks are skipped with a message when they are not installed.

## Code rules

- **One file, standard library only.** No third-party imports, no vendored packages.
- **Python 3.9 syntax.** No `match`, no `X | Y` in annotations that are evaluated (use
  `Optional[X]` or `Union[X, Y]`), no parenthesised context managers, no `from __future__`.
  ruff (`make lint`) and the 3.9 CI jobs catch most of it.
- **Every child process states its stdin**: `subprocess.DEVNULL`, or a pipe the program writes
  to. The popup owns the terminal; a child that reads from it swallows keystrokes, and fzf
  closes as if Esc had been pressed. The tests check that every `subprocess` call says it.
- **Anything started outside fzf gets `env=child_env()`**: no `FZF_*` variable and nothing that
  holds the run directory's path. Block 51 checks every `subprocess` call in the program; the
  only ones without it are fzf itself (in `popup`), `fzf_rejects` (it runs before the run
  directory exists) and the `--focus` worker in `enter`, whose `env` starts from
  `child_env(run_dir)`.
- **Every wait has a bound**. Block 50 checks, with the AST, in the program and in the tests:
  every `subprocess.run`, `check_output`, `call` and `check_call` (also through an attribute,
  such as `sb.subprocess.run`) passes `timeout=`; every `communicate()` passes a timeout; every
  `wait()` and `join()` passes an argument or `timeout=`; every `select()` passes its timeout;
  and nothing calls `os.wait()`, or `os.waitpid`, `os.wait3` or `os.wait4` with options `0`. The
  one exemption, pinned to its site, is the popup's `proc.communicate(first)`, its wait for
  fzf, which the user ends with a key or a signal.
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

The README images are made from the demo data, never from a real session: after a change to
what the popup draws, run `docs/render.sh` and commit the new `docs/assets/` files with it.

## Commits and pull requests

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `docs:`, `test:`, `ci:`, `chore:`, `refactor:`. Say in the body why the change is needed.
- Keep pull requests small and focused, and fill in the template.
- `make check` must pass before you ask for a review.
- A change users will notice gets a line in `CHANGELOG.md`: under `## [Unreleased]`, except
  before the first tag (see [Releases](#releases)).

## Releases

Versioning is manual and nothing runs on a tag: no workflow builds or publishes anything. A
release of version `X.Y.Z` is these steps, in this order:

1. Open a pull request against `main` that:
   - sets `version = "X.Y.Z"` in `herdr-plugin.toml` and `VERSION = "X.Y.Z"` in
     `bin/switchboard` (the tests check that they match);
   - in `SECURITY.md`, makes the new `X.Y.x` row the only supported one when the minor or
     major version changes;
   - in `CHANGELOG.md`, renames `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`, dated the day
     you will tag, and adds a new, empty `## [Unreleased]` above it;
   - updates the links at the bottom of `CHANGELOG.md`: `[Unreleased]` compares
     `vX.Y.Z...HEAD`, and a new `[X.Y.Z]` line points to `releases/tag/vX.Y.Z`.
2. Merge it and wait for CI on `main` to pass.
3. Tag that merge commit and push the tag:

   ```sh
   git switch main && git pull --ff-only
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. Create the GitHub release from the tag (`gh release create vX.Y.Z --verify-tag --title vX.Y.Z`)
   and paste that version's `CHANGELOG.md` section as its notes.

Every change goes under `## [Unreleased]` when it is merged, so the release pull request only
renames that section.

The tools CI downloads are pinned by hand: fzf and gitleaks in
`.github/scripts/install-pinned.sh` (version and SHA-256 of each archive), uv in
`.github/workflows/ci.yml`, ruff in the `Makefile` and `.pre-commit-config.yaml`. Dependabot
keeps the GitHub Actions current.

## Security

Do not report vulnerabilities in public issues. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE), the same as the rest of the project. There is no CLA.
