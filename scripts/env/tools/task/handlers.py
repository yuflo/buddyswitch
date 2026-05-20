#!/usr/bin/env python3
"""task env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "create": ("env.tools.task.service", "create_task_for_active_buddy"),
    "list": ("env.tools.task.service", "list_tasks_for_active_buddy"),
    "get": ("env.tools.task.service", "get_task_for_active_buddy"),
    "update": ("env.tools.task.service", "update_task_for_active_buddy"),
    "archive": ("env.tools.task.service", "archive_task_for_active_buddy"),
}
