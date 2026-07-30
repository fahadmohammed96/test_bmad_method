"""Test delle migrazioni Alembic forward-only (AR-11)."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def test_upgrade_head_crea_le_tabelle_core(pg_engine: Engine) -> None:
    # L'upgrade è già stato eseguito dalla fixture di sessione.
    tabelle = set(inspect(pg_engine).get_table_names())
    assert {"outbox", "job"} <= tabelle


def test_il_downgrade_e_vietato(pg_engine: Engine) -> None:
    with pytest.raises(Exception, match="forward-only"):
        command.downgrade(_config(), "-1")
