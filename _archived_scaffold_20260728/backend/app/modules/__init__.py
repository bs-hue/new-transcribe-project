"""Bounded contexts.

Each subpackage is a self-contained module with its own four layers
(`domain`, `application`, `infrastructure`, `interface`). A module never imports
another module's internals; cross-module needs go through the shared kernel or a
module's published contract.

Adding a future module (Insights, Semantic Search, Translation) means adding a
folder here and mounting its router — no changes to existing modules.
"""
