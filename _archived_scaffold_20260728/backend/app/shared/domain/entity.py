"""Base type for domain entities.

An *entity* is something with a continuous identity: a User, a Job, a Transcript.
Its attributes change over time — a job moves from queued to completed — but it
remains the same job. So equality is by identity, never by comparing fields:
two objects loaded from the database at different moments represent the same
entity even if one is stale.

Value objects (an email address, a time range) are the opposite: they have no
identity and are equal when their contents match. Those use
``@dataclass(frozen=True)`` directly and do not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(eq=False)
class Entity:
    """An object identified by a stable UUID.

    Note ``eq=False``: the dataclass-generated field-by-field equality would be
    wrong here, so identity comparison is defined explicitly below.
    """

    id: UUID = field(default_factory=uuid4)

    def __eq__(self, other: object) -> bool:
        # The exact-class test matters: a Job and a JobItem that happened to share
        # an id are still different things.
        if not isinstance(other, Entity) or other.__class__ is not self.__class__:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((self.__class__, self.id))
