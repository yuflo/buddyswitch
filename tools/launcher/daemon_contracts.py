"""Stable, product-neutral contracts for the actor instance daemon."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol

if TYPE_CHECKING:
    from daemon_triggers import DaemonTrigger


class HandlerResult:
    def __init__(self, status: str, message: str | None = None) -> None:
        if status not in {"ignored", "handled", "failed"}:
            raise ValueError(f"invalid handler result status: {status}")
        self.status = status
        self.message = message

    @classmethod
    def ignored(cls) -> "HandlerResult":
        return cls("ignored")

    @classmethod
    def handled(cls) -> "HandlerResult":
        return cls("handled")

    @classmethod
    def failed(cls, message: str) -> "HandlerResult":
        return cls("failed", message or "handler failed")


class DaemonContext:
    def __init__(
        self,
        *,
        instance_json: Path,
        instance_payload: dict[str, Any],
        actor_id: str,
        instance_root: Path,
        main_thread_id: str,
        role: str,
        workspace_dir: Path,
        project_workspace_dir: Path,
        socket_path: Path,
        permissions: str = "buddyswitch-runtime",
    ) -> None:
        self.instance_json = instance_json
        self.instance_payload = instance_payload
        self.actor_id = actor_id
        self.instance_root = instance_root
        self.main_thread_id = main_thread_id
        self.role = role
        self.workspace_dir = workspace_dir
        self.project_workspace_dir = project_workspace_dir
        self.socket_path = socket_path
        self.permissions = permissions


ApplicationCommand = Callable[[Mapping[str, object]], Mapping[str, object]]
ApplicationCommandFactory = Callable[[DaemonContext], Mapping[str, ApplicationCommand]]


class DaemonHandler(Protocol):
    name: str

    def handles(self, trigger: "DaemonTrigger") -> bool:
        """Return whether this handler owns the trigger."""

    def handle(
        self,
        context: DaemonContext,
        state: Any,
        runtime: Any,
        trigger: "DaemonTrigger",
    ) -> HandlerResult | dict[str, Any]:
        """Handle one owned trigger and return the observable daemon result."""
