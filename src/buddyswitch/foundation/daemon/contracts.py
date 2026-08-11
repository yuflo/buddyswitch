"""Stable, product-neutral contracts for the actor instance daemon."""

from dataclasses import dataclass
from pathlib import Path
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol

if TYPE_CHECKING:
    from buddyswitch.foundation.daemon.triggers import DaemonTrigger


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


class DaemonHostError(RuntimeError):
    """The application host could not complete a daemon operation."""


class DaemonHostTimeout(DaemonHostError):
    """The application notification stream reached its poll timeout."""


class DaemonNotificationClient(Protocol):
    def bind(self, context: DaemonContext) -> None:
        """Bind the client's notification stream to the actor's main thread."""

    def read_notification(self) -> dict[str, Any]:
        """Read one application notification or raise DaemonHostTimeout."""


class DaemonHost(Protocol):
    maintenance_interval_seconds: float

    def resolve_socket_path(self, *, actor_id: str, instance_root: Path) -> Path:
        """Resolve the concrete application socket for an actor instance."""

    def instance_daemon_command(self, instance_json: Path) -> list[str]:
        """Return the explicit application command for the child daemon."""

    def notification_client(
        self,
        context: DaemonContext,
    ) -> AbstractContextManager[DaemonNotificationClient]:
        """Open the bound application notification transport."""

    def parent_activity(self, context: DaemonContext) -> dict[str, Any]:
        """Project the parent thread's current activity."""

    def input_actor(self, context: DaemonContext, text: str) -> dict[str, Any]:
        """Submit input to the actor through the application host."""


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


@dataclass(frozen=True)
class DaemonHandlerRegistration:
    name: str
    factory: Callable[[], DaemonHandler]
    application_command_factory: ApplicationCommandFactory | None = None


class DaemonReconciler(Protocol):
    """Optional product-neutral lifecycle hook invoked during bounded polling."""

    name: str

    def reconcile(
        self,
        context: DaemonContext,
        state: Any,
        runtime: Any,
    ) -> HandlerResult | dict[str, Any]:
        """Reconcile durable product state without relying on a notification."""
