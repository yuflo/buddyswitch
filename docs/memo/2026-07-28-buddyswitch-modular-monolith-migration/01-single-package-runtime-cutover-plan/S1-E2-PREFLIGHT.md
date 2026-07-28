# S1 E2 Source/Distribution Correspondence Preflight

> Evidence authority: coordinating hub
> Decision: DESIGN FEASIBLE / this record alone authorizes no implementation
> Evidence ID: `E2P-1c5a001693442adc`
> Applicable decision: D-037

## 1. Claim

The selected E2 mechanism can use the current
`setuptools.build_meta`/wheel/non-editable-install toolchain to enforce:

> Every regular non-test file below `src/buddyswitch/**` corresponds by exact
> package-relative path and bytes to exactly one installed package file; every
> installed package file has that source counterpart; every package-source
> symlink fails closed; co-located tests and caches remain non-runtime.

This preflight proves design feasibility. It does not change or accept the
current activation implementation.

## 2. Evidence identity

```text
repository:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch SHA-256:
400730f42c705596458f4eaae174017ee7f7606a10b10b1232a507a04421de4e

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-ignored untracked paths:
70

untracked path-set SHA-256:
b039e951b715c2b0ae071c4f05416adcf036a26e4fc40068e40b4e7ffb8d92c0

untracked path/content manifest SHA-256:
40db562dc92efe475c85b22ba5a343d478e1611eaf8cd0a67db86d3d7a4c217d

Python:
3.13.5

setuptools:
78.1.1

wheel:
0.45.1
```

The tracked executable candidate is unchanged from the accepted E1 return.
The preflight uses no repository Python import or product runtime mutation.

## 3. Representative final topology

The isolated fixture used one `src/buddyswitch` distribution and included:

```text
buddyswitch/__init__.py
buddyswitch/launcher/__init__.py
buddyswitch/launcher/assets/docs/help.md
buddyswitch/modules/__init__.py
buddyswitch/modules/probe/__init__.py
buddyswitch/modules/probe/tests/__init__.py
buddyswitch/modules/probe/tests/test_probe.py
buddyswitch/modules/probe/__pycache__/probe.pyc
```

It used:

```text
build backend: setuptools.build_meta
build: pip wheel --no-deps --no-build-isolation
installation: fresh venv, non-editable wheel install, no index
installed truth: wheel RECORD plus actual package-root scan
```

The required `launcher/assets/docs/help.md` entered the wheel and installed
package. Co-located tests, `__pycache__` and `.pyc` did not.

## 4. Prototype boundary

Source manifest:

- walks every package-source entry without following symlinks;
- rejects file and directory symlinks before any exclusion;
- excludes only co-located `tests` subtrees, `__pycache__` and `.pyc`;
- maps package-relative path to exact bytes.

Installed manifest:

- reads recorded `buddyswitch/**` files from distribution `RECORD`;
- rejects missing recorded files and installed symlinks;
- scans the installed package root for unrecorded files;
- maps the same package-relative path to exact bytes.

Correspondence requires equal path sets and equal bytes for every path.
`pyproject.toml` remains an additional build-attribution input; it is not an
installed package counterpart.

## 5. Scenario result

```text
probe SHA-256:
908e638ba73fdc2a1725674b557ca5ff207ceed69cbf337020c316f3f010907b

canonical semantic result SHA-256:
1c5a001693442adc57cfd0691ef1ebc4ffcf7202a6cad43fa44b7f20538c0102

result:
ok=true
kind=s1.e2.preflight
scenario_count=11
```

The canonical digest covers `ok`, kind, build backend and the sorted
scenario/result map; it excludes location-dependent absolute wheel/package
paths and human-readable failure detail.

| Scenario | Result |
|---|---|
| legitimate `assets/docs/help.md` present and byte-identical | PASS |
| co-located tests/cache excluded | PASS |
| source-only regular file | EXPECTED FAIL |
| installed-only unrecorded file | EXPECTED FAIL |
| source file missing | EXPECTED FAIL |
| installed recorded file missing | EXPECTED FAIL |
| source byte drift after install and before activation | EXPECTED FAIL |
| installed byte drift | EXPECTED FAIL |
| source file symlink | EXPECTED FAIL |
| source symlink inside an otherwise excluded real tests subtree | EXPECTED FAIL |
| source directory symlink | EXPECTED FAIL |

Every failure identified the disagreeing path or forbidden symlink. The
fixture returned to baseline correspondence after each scenario, so one
mutation did not mask another.

## 6. Cleanup

```text
temporary active root:
absent

probe/build/venv recovery location:
/Users/chen/.Trash/buddyswitch-s1-e2-preflight-20260728.N7z6qf

probe/pip process:
none
```

The recovery copy is outside the repository and can be deleted independently.
No source, installed BuddySwitch runtime, activation record, test output,
socket, lock or canonical state was changed.

## 7. Gate decision

Accepted:

- the exact source/install path-and-byte comparison is feasible;
- explicit runtime assets and co-located test exclusion coexist without a
  custom build backend;
- file/directory symlink and pre-activation drift rejection are feasible;
- no duplicate setuptools selection engine or generated build manifest is
  required.

Still open:

- F-034;
- R-PKG-019;
- C1 executable implementation and RED/GREEN;
- complete C1 milestone and C2 pre-move preservation proof.

S1 remains `REPLANNING`. C2 remains not started. No E2 Goal Packet is
authorized by this preflight. The next permissible action is to write and
READY-review one bounded E2 implementation plan against this evidence.
