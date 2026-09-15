"""System endpoints: health and public configuration.

Deliberately *not* a bounded context. It has no domain, no business rules, and no
database tables of its own — it only reports on the running process. Giving it
the full four-layer module treatment would be ceremony with nothing inside, so it
is a thin interface-only package instead.
"""
