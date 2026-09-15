"""Ports: the sockets our business logic plugs into.

A port declares a *need* ("something that tells the time", "something that runs
work in the background") without naming a technology. Concrete plugs — adapters —
live in `core/` or a module's `infrastructure/` layer and are chosen in the
composition root based on configuration.

This is the seam that lets v1 stay simple while remaining swappable: replacing
in-process background tasks with a Redis worker means writing one new adapter,
not editing business rules. See docs/TECHNICAL_ARCHITECTURE.md §2.1.
"""
