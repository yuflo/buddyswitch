# Search Capability Architecture

## Purpose

Search owns runtime-visible backend status and non-opening URL planning. It
does not fetch or summarize results, open a Browser page, persist state, or
own Browser lifecycle.

The current path is:

```text
Actor env.tool request
  -> explicitly composed Search Tool registration
  -> Search-private validation and selected RoleRuntime read
  -> status metadata, rejection, or target URL plan
```

The Tool ID is `search`; its actions are exactly `status` and `request`.
Successful URL planning always reports `page_opened=false`. Browser page
opening remains a separate `chrome-devtools-cockpit.search_page` action.

## Physical owner

Search has one live capability root:
`src/buddyswitch/modules/search/`.

- `src/buddyswitch/modules/search/module.py` exports the passive Search
  `ModuleAssembly`.
- `src/buddyswitch/modules/search/private/adapters/tool/tool.py` owns the Tool
  definition and invocation entrypoint.
- `src/buddyswitch/modules/search/private/adapters/tool/_impl.py` owns Search
  validation, RoleRuntime projection, and URL planning.
- `src/buddyswitch/modules/search/tests/integration` contains the owned
  behavior and response-contract tests.

Search has no Public surface because no current cross-component consumer needs
a Search-owned operation.

## Application composition

`src/buddyswitch/application/composition.py` selects the Search assembly
exactly once. The assembly contributes one Tool registration and no Daemon,
CLI, Web, Skill, cleanup, lifecycle, or state surface.

`src/buddyswitch/application/build.py` validates and flattens that contribution
with every other explicitly selected component. Generic Tool registry and
dispatch code receive the registration without importing Search private code.
Search is not filesystem-discovered.

## Dependency direction

Allowed Search dependencies are:

```text
Search module -> ModuleAssembly + ToolRegistration
Search Tool -> public Tool runtime contracts and results
Search implementation -> generic ToolContext + selected RoleRuntime facts
```

Search does not import another component's private package, Browser
implementation, application composition, repository/domain state, or launcher
owner. Generic hosts do not import Search private code.

## Preserved contract

`search.status` projects configured Browser and `search_api` availability from
the selected immutable Role runtime and instance facts. `search.request` requires an
explicit backend and non-empty query, validates the optional engine, and
returns the existing Google/Web/Reddit/X target URL contract.

Both actions are read-only. Rejections and successes report no product or
runtime state change. No compatibility package, fallback registration,
Search-shaped Browser host method, or second write path exists.
