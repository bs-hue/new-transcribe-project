"""The shared kernel: pure, framework-free building blocks.

Nothing in this package may import FastAPI, SQLAlchemy, pydantic-settings, or any
other framework. It holds the base types and port interfaces that every module
builds on, which is what allows business rules to be tested with no I/O at all.

If you find yourself needing a framework import here, the code belongs in
`core/` (framework-aware plumbing) or in a module's `infrastructure/` layer.
"""
