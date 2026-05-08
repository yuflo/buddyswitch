# Projects/App Framework Placeholder Consensus Memo

Date: 2026-05-08
Status: Accepted consensus for next cleanup path

## Problem And Background

BuddySwitch is a framework and control layer for launcher-managed buddy
instances. It should provide runtime structure, state contracts, skills,
handoff flow, and a shared project-source mount point. It should not ship a
concrete product instance as part of the framework source tree.

The PM buddy test exposed that `projects/app` currently contains a concrete
landing-page product named DayFlow. Because product-mode instances project
`projects/app` into each runtime workspace, PM treated that concrete page as
current product context and produced DayFlow-specific PRD and positioning
artifacts.

That behavior was understandable from the current repository state, but the
repository state is the problem: framework source should not include instance
content that can bias product-mode buddy work.

## User Feedback

The user clarified the intended boundary:

- `projects/app` in the BuddySwitch repo should be empty or only an abstract
  placeholder if the directory is required.
- Framework initialization may create or project workspace directories, but it
  should not seed concrete sample product content.
- DayFlow, AI Scheduler, onboarding-demo pages, or similar app content are
  historical development residue, not framework contract.

This feedback changes the interpretation of the earlier finding. DayFlow is not
stale residue inside a single PM instance; it is worse: it is tracked framework
repo content being correctly projected into product-mode instances.

## Investigation And Consensus Process

Two checks established the consensus.

First, the runtime projection path is intentional. Product mode keeps shared
project source under `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`, and buddy
instances use relative `projects/app` as the shared project-source path. The
launcher and env profiles depend on the path existing.

Second, the concrete content at that path is not intentional framework
contract. `rg DayFlow` finds DayFlow only in `projects/app`; tests and docs
expect `projects/app` to exist and be projected, but they do not require the
product to be DayFlow. Git history shows this directory has held different
sample products over time, which supports treating the contents as residue.

The agreed distinction is:

- Keep the `projects/app` path contract.
- Remove concrete instance content from the BuddySwitch framework repo.

## Final Consensus

1. `projects/app` is a framework mount point / placeholder path.
2. The BuddySwitch repo should not ship concrete sample product files under
   `projects/app`.
3. Product-mode workspaces may project `projects/app`, but the projected source
   should come from real user/project content, not framework-bundled examples.
4. A tracked placeholder such as `projects/app/README.md` or `.gitkeep` is
   acceptable if launcher materialization requires the directory.
5. Tests should verify path existence, symlink/projection behavior, and buddy
   access boundaries; they should not verify concrete HTML/JS/CSS sample files.
6. Future framework tests and docs should avoid product-specific names such as
   DayFlow unless the file is explicitly a fixture isolated from runtime
   framework source.

## Affected Assumptions, Tests, And Docs

Current assumptions to replace:

- `tests/test_buddyswitch_launcher.py` currently checks for concrete files such
  as `index.html`, `main.js`, and `styles.css` in the shared project workspace.
- `tests/test_repo_consistency.py` and `framework/docs/interface-spec.md`
  currently treat `projects/app/main.js` as a framework UI surface.
- Root workspace guidance currently calls `projects/app/` "Main app code",
  which implies bundled source rather than a mount point.

Path contracts to preserve:

- Launcher materialization still needs `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}`.
- Runtime workspaces still need relative `projects/app`.
- Env profiles still describe buddy-specific read/write access to that path.
- Dev remains the only buddy allowed to directly write project source in
  product mode; non-Dev buddies use artifacts and handoff.

## Solution Direction

Smallest cleanup path:

1. Delete concrete app files from repo `projects/app`, including DayFlow HTML,
   JS, and CSS.
2. Add a minimal placeholder file that explains `projects/app` is a shared
   product-source mount point for runtime workspaces.
3. Update launcher tests to assert directory/projection/access behavior, not
   sample product files.
4. Update docs and repo consistency tests so framework UI references point to
   framework code, not `projects/app`.
5. Add a guard test that rejects concrete sample product residue under
   `projects/app`.
6. Verify with targeted launcher, repo consistency, and runtime context tests.

This keeps the shortest validated loop: remove product residue, preserve the
runtime path contract, and prevent the same drift from returning.
