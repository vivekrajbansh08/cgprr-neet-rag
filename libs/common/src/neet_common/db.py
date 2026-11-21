"""Postgres connection factory. Callers pick the role; there is no owner/superuser option here.

Only jobs/ingest connects as neet_ingest; everything else uses neet_reader (read-only).
"""

from __future__ import annotations

from typing import Literal

import psycopg

from neet_common.config import Settings

Role = Literal["neet_ingest", "neet_reader"]


def connect(settings: Settings, role: Role, *, connect_timeout: int = 5) -> psycopg.Connection:
    """A new connection as `role` (neet_ingest or neet_reader). The caller closes it."""
    if role == "neet_ingest":
        password = settings.neet_ingest_password.get_secret_value()
    elif role == "neet_reader":
        password = settings.neet_reader_password.get_secret_value()
    else:
        raise ValueError(f"unsupported role {role!r}")
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_host_port,
        dbname=settings.postgres_db,
        user=role,
        password=password,
        connect_timeout=connect_timeout,
        application_name=f"cgprr-neet-rag:{role}",
    )
