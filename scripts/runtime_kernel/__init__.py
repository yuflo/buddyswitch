#!/usr/bin/env python3
"""Runtime kernel entrypoints for runless broker operations."""

from .broker import dispatch_runtime_request

__all__ = ["dispatch_runtime_request"]
