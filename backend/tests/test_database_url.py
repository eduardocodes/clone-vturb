"""A URL do banco sempre usa o driver instalado (psycopg2), qualquer que seja a grafia do env."""
import pytest

from app.core.db_url import engine_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg2://u:p@h:5432/db"),
        ("postgres://u:p@h:5432/db", "postgresql+psycopg2://u:p@h:5432/db"),
        ("postgresql+psycopg2://u:p@h:5432/db", "postgresql+psycopg2://u:p@h:5432/db"),
    ],
)
def test_engine_url_forca_psycopg2(raw, expected):
    assert engine_url(raw) == expected


def test_engine_url_respeita_outro_driver_explicito():
    assert engine_url("postgresql+asyncpg://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
