"""Task-owned Actor Console section projection."""

from __future__ import annotations

from buddyswitch.env.domain.identity import ActorIdentityProfile
from buddyswitch.launcher.web_contracts import ActorConsoleSectionRegistration
from buddyswitch.modules.task.private import read_model


def project(actor_profile: ActorIdentityProfile) -> dict[str, object]:
    projection = read_model.actor_external_task_projection(
        actor_profile=actor_profile,
    )
    return {
        "active_count": projection["active_count"],
        "terminal_count": projection["terminal_count"],
        "active_tasks": projection["active_tasks"][:10],
        "terminal_tasks": projection["terminal_tasks"][:5],
    }


REGISTRATION = ActorConsoleSectionRegistration(
    name="task_sys",
    project=project,
)
