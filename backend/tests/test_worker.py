"""Worker: rollup periódico com trava entre réplicas e parada limpa."""
from unittest.mock import patch

from sqlalchemy import text

from app import worker
from app.core.database import SessionLocal, engine


def test_tick_consolida_as_metricas():
    with patch.object(worker.metrics_rollup, "run_all") as run_all:
        assert worker.run_maintenance(SessionLocal) is True
    run_all.assert_called_once()


def test_tick_pula_quando_outra_replica_esta_consolidando():
    with engine.connect() as other:
        other.execute(text("SELECT pg_advisory_lock(:id)"), {"id": worker.MAINTENANCE_LOCK_ID})
        try:
            with patch.object(worker.metrics_rollup, "run_all") as run_all:
                assert worker.run_maintenance(SessionLocal) is False
            run_all.assert_not_called()
        finally:
            other.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": worker.MAINTENANCE_LOCK_ID})


def test_erro_no_rollup_nao_derruba_o_worker():
    with patch.object(worker.metrics_rollup, "run_all", side_effect=RuntimeError("boom")):
        assert worker.run_maintenance(SessionLocal) is False


def test_loop_para_quando_recebe_sinal():
    stop = worker.StopFlag()
    calls = []

    def fake_tick():
        calls.append(1)
        stop.set()

    worker.loop(fake_tick, stop, interval=0.01)
    assert calls == [1]
