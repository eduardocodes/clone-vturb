"""União dos trechos assistidos e curva de retenção por segundo (funções puras)."""
import math

import pytest

from app.services.watch_ranges import MAX_RETENTION_SECONDS, merge_ranges, retention_counts, sum_counts, watched_seconds


def test_uniao_de_trechos_sobrepostos_e_encostados():
    assert merge_ranges([[0, 10]], [[5, 20], [20.2, 30]], duration=100) == [[0, 30]]


def test_trechos_separados_continuam_separados_e_ordenados():
    assert merge_ranges([], [[50, 60], [0, 10]], duration=100) == [[0, 10], [50, 60]]


def test_trechos_invalidos_sao_descartados_e_limitados_a_duracao():
    raw = [[-5, 3], [10, 5], [float("nan"), 4], [90, 150], [7, 7]]
    assert merge_ranges([], raw, duration=100) == [[0, 3], [90, 100]]


def test_sem_duracao_conhecida_limita_ao_teto():
    assert merge_ranges([], [[0, MAX_RETENTION_SECONDS + 500]], duration=0) == [[0, MAX_RETENTION_SECONDS]]


def test_uniao_e_idempotente():
    ranges = [[0, 10], [20, 30]]
    once = merge_ranges([], ranges, duration=100)
    assert merge_ranges(once, ranges, duration=100) == once


def test_segundos_assistidos_somam_a_uniao():
    assert watched_seconds([[0, 10], [20, 25.5]]) == pytest.approx(15.5)


def test_retencao_conta_cada_segundo_tocado_uma_vez_por_sessao():
    counts = retention_counts([
        [[0, 3.5]],          # segundos 0,1,2,3
        [[2, 4], [2.5, 3]],  # segundos 2,3 (trechos repetidos não contam duas vezes)
    ])
    assert counts == [1, 1, 2, 2]


def test_retencao_vazia():
    assert retention_counts([]) == []


def test_soma_de_curvas_de_tamanhos_diferentes():
    assert sum_counts([[1, 2, 3], [1], []]) == [2, 2, 3]


def test_retencao_nunca_passa_do_teto():
    counts = retention_counts([[[0, MAX_RETENTION_SECONDS]]])
    assert len(counts) == MAX_RETENTION_SECONDS
    assert not any(math.isnan(c) for c in counts)
