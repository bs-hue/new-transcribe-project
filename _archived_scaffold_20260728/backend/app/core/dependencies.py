"""Shared FastAPI dependencies.

Endpoints declare what they need as a parameter and FastAPI supplies it. The
alternative — reaching for module-level globals — makes endpoints impossible to
test in isolation, because there is no way to substitute a test double.

Long-lived objects (engine, session factory, clock) are built once in the
composition root and stored on ``app.state``; these functions read them back out.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import SqlAlchemyUnitOfWork
from app.shared.ports.clock import Clock
from app.shared.ports.unit_of_work import UnitOfWork


def get_app_settings(request: Request) -> Settings:
    """Return the settings this application instance was built with."""
    settings: Settings = request.app.state.settings
    return settings


def get_engine(request: Request) -> Engine:
    """Return the process-wide database engine."""
    engine: Engine = request.app.state.engine
    return engine


def get_clock(request: Request) -> Clock:
    """Return the clock adapter."""
    clock: Clock = request.app.state.clock
    return clock


def get_unit_of_work(request: Request) -> Iterator[UnitOfWork]:
    """Provide a unit of work scoped to this request.

    Yielded rather than returned so FastAPI closes it when the response is
    finished, whether or not the endpoint raised. Note there is no automatic
    commit: use cases commit explicitly (see ``SqlAlchemyUnitOfWork``).
    """
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        yield uow


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
EngineDep = Annotated[Engine, Depends(get_engine)]
ClockDep = Annotated[Clock, Depends(get_clock)]
UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]
