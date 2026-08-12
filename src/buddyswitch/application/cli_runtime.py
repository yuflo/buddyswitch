"""Assemble the one current application input for Foundation CLI Runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from buddyswitch.application.build import ApplicationAssembly
from buddyswitch.foundation.cli_runtime.contracts import CliRuntimeApplicationInput
from buddyswitch.foundation.tool_runtime import native_mcp
from buddyswitch.runtime_support import env_manifest, env_profiles


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
WEB_MODULE = "buddyswitch.application.entrypoints.web"
ACTOR_BUILD_MODULE = "buddyswitch.application.entrypoints.actor_build"
BROWSER_RUNTIME_MODULE = "buddyswitch.application.entrypoints.browser_runtime"
ENV_MCP_MODULE = "buddyswitch.application.entrypoints.env_mcp"
BROWSER_COCKPIT_PROXY_MODULE = (
    "buddyswitch.application.entrypoints.browser_cockpit_proxy"
)
CLEANUP_MODULE = "buddyswitch.application.entrypoints.cleanup"
DIAGNOSTICS_MODULE = "buddyswitch.application.entrypoints.diagnostics"


def _resolve_role_profile(
    role_id: str,
    manifest_path: Path,
) -> Mapping[str, object]:
    return env_profiles.require_env_profile(
        role_id,
        manifest_path=manifest_path,
        package_root=PACKAGE_ROOT,
    )


def assemble_cli_runtime(
    application: ApplicationAssembly,
) -> CliRuntimeApplicationInput:
    """Build the concrete CLI Runtime input from current application truth."""

    if not isinstance(application, ApplicationAssembly):
        raise ValueError("CLI Runtime assembly requires ApplicationAssembly")
    return CliRuntimeApplicationInput(
        web_module=WEB_MODULE,
        actor_build_module=ACTOR_BUILD_MODULE,
        browser_runtime_module=BROWSER_RUNTIME_MODULE,
        env_mcp_module=ENV_MCP_MODULE,
        browser_cockpit_proxy_module=BROWSER_COCKPIT_PROXY_MODULE,
        cleanup_module=CLEANUP_MODULE,
        diagnostics_module=DIAGNOSTICS_MODULE,
        manifest_path=env_manifest.DEFAULT_MANIFEST,
        role_profile_resolver=_resolve_role_profile,
        parent_disabled_tools=tuple(
            native_mcp.encode_native_tool_name(
                registration.definition.id,
                action.name,
            )
            for registration in application.tools
            for action in registration.definition.actions
            if action.bound_capability_env is not None
        ),
    )


def resolve_role_browser_capability(
    application_input: CliRuntimeApplicationInput,
    role_id: str,
) -> str:
    """Resolve the current Application-owned Browser fact for one Role."""

    profile = application_input.resolve_role_profile(role_id)
    tool_capability = profile.get("tool_capability")
    browser_capability = (
        tool_capability.get("browser_cockpit")
        if isinstance(tool_capability, Mapping)
        else None
    )
    if browser_capability not in {"available", "required"}:
        raise ValueError(
            "CLI Runtime Role profile must provide a current Browser cockpit capability"
        )
    return browser_capability
