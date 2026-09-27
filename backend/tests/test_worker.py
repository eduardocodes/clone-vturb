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


def test_manutencao_roda_no_intervalo_e_jobs_a_cada_tick():
    clock = [0.0]
    calls = []
    tick = worker.make_tick(
        maintenance=lambda: calls.append("m"),
        next_job=lambda: calls.append("j"),
        maintenance_interval=300,
        clock=lambda: clock[0],
    )
    tick()
    tick()
    clock[0] = 301
    tick()
    assert calls == ["m", "j", "j", "m", "j"]


def test_tick_diz_se_rodou_um_job():
    busy = worker.make_tick(maintenance=lambda: True, next_job=lambda: "done", maintenance_interval=300, clock=lambda: 0)
    idle = worker.make_tick(maintenance=lambda: True, next_job=lambda: None, maintenance_interval=300, clock=lambda: 0)
    assert busy() is True
    assert idle() is False


def test_loop_so_dorme_com_a_fila_vazia():
    stop = worker.StopFlag()
    results = iter([True, True, False])
    waits = []

    def fake_tick():
        try:
            return next(results)
        except StopIteration:
            stop.set()
            return False

    stop.wait = lambda timeout=None: waits.append(timeout)
    worker.loop(fake_tick, stop, interval=5)
    assert waits == [5, 5]


def test_erro_inesperado_no_tick_nao_derruba_o_worker():
    stop = worker.StopFlag()
    calls = []

    def boom():
        calls.append(1)
        if len(calls) == 2:
            stop.set()
        raise RuntimeError("banco fora do ar")

    worker.loop(boom, stop, interval=0.01)
    assert calls == [1, 1]
