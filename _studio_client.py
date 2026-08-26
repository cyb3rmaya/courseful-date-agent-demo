"""Compatibility entry point for the travel MCP stdio client.

The repository owner's original module is named ``_stdio_client.py`` because
the transport is stdio.  This module keeps the requested ``_studio_client``
name usable without duplicating the connection implementation.
"""

from _stdio_client import connect_to_travel_server

__all__ = ["connect_to_travel_server"]
