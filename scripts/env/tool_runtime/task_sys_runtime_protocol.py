#!/usr/bin/env python3
"""Current Task Sys application-command protocol shared by client and adapter."""

EXECUTE_INSTRUCTION = "task_sys.execute_instruction"
CLEANUP_SIDE_LEASE = "task_sys.cleanup_side_lease"

COMMAND_KEYS = frozenset({EXECUTE_INSTRUCTION, CLEANUP_SIDE_LEASE})
