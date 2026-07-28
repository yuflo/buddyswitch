# S1.1 Package Contract

## Outcome

> A clean checkout builds and installs one BuddySwitch distribution with exact
> runtime assets, package entrypoints and content exclusions before any
> production launcher is cut over.

## Files

- Create: `pyproject.toml`
- Create: `src/buddyswitch/__init__.py`
- Create: `src/buddyswitch/application/__init__.py`
- Create: `src/buddyswitch/application/entrypoints/__init__.py`
- Create: package activation/runtime-identity owner below
  `src/buddyswitch/foundation/process_runtime/`
- Create: static package-contract proof at
  `tests/unit/architecture/test_package_contract.py`
- Create: process-owning build/install proof at
  `tests/process/package/test_distribution_install.py`
- Create: process-owning activation proof at
  `tests/process/package/test_runtime_activation.py`
- Create at runtime: `.buddyswitch-runtime/venv/`
- Create at runtime: `.buddyswitch-runtime/activation.json`
- Modify: `.gitignore` to exclude `.buddyswitch-runtime/`
- Modify: `requirements-test.txt` to declare the build/test tools used by the
  public test environment
- Modify: test support needed to build/install into an isolated test runtime

No public launcher changes in this checkpoint.

The test-tier split is mandatory. Unit architecture proof may parse
configuration and inspect source topology but cannot build a wheel, create a
venv or install a distribution. Those operations own child processes and
therefore belong to `tests/process/package/**`.

## Frozen package rules

`pyproject.toml` alone owns:

- `src` package discovery;
- package name `buddyswitch`, initial internal package version `0.1.0`, and
  Python requirement `>=3.11`;
- runtime module entrypoints;
- package data;
- `setuptools.build_meta` as the only build backend, with `setuptools>=58`
  and `wheel` as build requirements;
- distribution exclusions.

`requirements-test.txt` remains the test-environment dependency owner and is
exactly:

```text
pytest==9.0.3
setuptools==78.1.1
wheel==0.45.1
```

These are test/build tools, not product runtime dependencies.

S1 does not add a second console-script interface. The stable root launcher
delegates to `python -m buddyswitch.application.entrypoints.cli`.

Required package data classes:

```text
*.toml
*.json
*.md
*.html
*.css
*.js
*.sh
```

only under explicit package-owned asset roots.

Required exclusions:

```text
**/tests/**
**/__pycache__/**
*.pyc
root wrappers
repository-root docs/**
repository-root projects/**
source-control/cache files
```

Repository-root `docs/**`, `projects/**` and wrappers are already outside
`src/buddyswitch/**`; their names are not package-internal exclusion rules. A
package-owned runtime asset such as `launcher/assets/docs/help.md` is a
required runtime input.

The activation owner builds one source package manifest from every regular
non-test file below `src/buddyswitch/**`, excluding only co-located `tests`
subtrees, `__pycache__` and `.pyc`. It rejects every file or directory symlink
below the package source before exclusions are applied.

The installed package manifest uses the distribution `RECORD` plus an actual
installed package-root scan. Every recorded package file must exist, no
unrecorded package file or installed symlink may exist, and source and
installed manifests must have exactly equal package-relative path sets and
bytes. This comparison runs at both `activate` and `verify`.

`pyproject.toml` remains part of the recorded source/build attribution digest
in addition to the source package manifest. Runtime state and repository
wrappers are not activation inputs. Installed-content validation never trusts
an editable-install pointer.

## RED

Add direct tests that initially fail because:

- no `pyproject.toml` exists;
- package cannot build/install from clean source;
- no package entrypoints exist;
- distribution allowlist cannot be inspected.

The unit test proves the static declaration/topology contract. The process
tests inspect an actually built artifact and installed runtime, not only
configuration text.

## GREEN

Build/install into an isolated temporary environment and prove:

- `import buddyswitch` resolves only from the installation;
- package metadata exposes one version and entrypoint set;
- no repository root is on import path;
- artifact contains only explicitly allowed current package files;
- every source package runtime file and installed package file corresponds by
  exact relative path and bytes;
- explicit package-owned assets remain included while co-located tests and
  caches remain excluded;
- all package-source symlinks fail closed;
- installation is non-editable;
- the exact installed interpreter/package root/distribution digest are bound
  by an atomically written activation record;
- source or installed-content drift, including drift before first activation,
  fails activation validation;
- cleanup removes the temporary environment/build output.

The package activation module exposes only:

```text
activate --source-root <absolute checkout>
verify
status
```

`activate` runs after non-editable installation and atomically writes the
record. `verify` is the pre-mutation gate used by the CLI. `status` is
read-only diagnostics.

The local production/development runtime is
`.buddyswitch-runtime/venv/bin/python`. An explicit
`BUDDYSWITCH_RUNTIME_DIR` may select another directory with the same
`venv/`/`activation.json` contract. The launcher derives
`BUDDYSWITCH_PYTHON`; no independent interpreter override is valid. Actor
start never creates, repairs or upgrades this environment.

Initial provisioning and replacement are explicit repository setup
operations, not product launch behavior:

1. an operator-selected Python satisfying `requires-python` builds one wheel
   through the declared PEP 517 backend;
2. that interpreter creates the target venv;
3. the wheel is installed non-editably into that venv;
4. the installed runtime runs `runtime_activation activate --source-root ...`;
5. only a successfully verified activation record makes the runtime usable.

No BuddySwitch launcher, Actor lifecycle command or package import installs
the runtime. S1 updates developer setup guidance with the exact commands. A
missing or drifted runtime fails closed and tells the operator to repeat the
explicit setup operation.

The canonical setup sequence is:

```text
<bootstrap-python> -m pip wheel --no-deps --wheel-dir <temporary-wheel-dir> <source-root>
<bootstrap-python> -m venv <runtime-dir>/venv
<runtime-dir>/venv/bin/python -m pip install --no-deps --no-index \
  --find-links <temporary-wheel-dir> buddyswitch==0.1.0
<runtime-dir>/venv/bin/python -m \
  buddyswitch.application.entrypoints.runtime_activation \
  activate --source-root <source-root>
```

For the repository development runtime, `<runtime-dir>` is
`<source-root>/.buddyswitch-runtime`. The bootstrap interpreter is used only
to build the wheel and create the venv; it is never a runtime fallback.
Developer test dependencies are installed into that same venv from
`requirements-test.txt` before invoking `./buddyswitch-test`.

## Stop

- more than one build declaration is required;
- package content relies on arbitrary recursive data inclusion;
- runtime requires an external protected installation contract not yet
  classified;
- tests can pass only with editable install or source `PYTHONPATH`.
