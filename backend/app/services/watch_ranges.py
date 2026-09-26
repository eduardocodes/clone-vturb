"""Trechos assistidos (ranges) e curva de retenção por segundo. Funções puras."""
import math
from typing import Iterable, Sequence

# Curva de retenção vai até 4 h de vídeo (resolução de 1 s)
MAX_RETENTION_SECONDS = 4 * 3600
# Buracos menores que isso (ruído do timeupdate) são unidos
MERGE_GAP_SECONDS = 0.5

Range = list  # [início, fim] em segundos


def _clean(ranges: Iterable[Sequence[float]], limit: float) -> list[list[float]]:
    cleaned = []
    for item in ranges:
        if len(item) != 2:
            continue
        start, end = float(item[0]), float(item[1])
        if math.isnan(start) or math.isnan(end):
            continue
        start, end = max(0.0, start), min(limit, end)
        if end > start:
            cleaned.append([start, end])
    return cleaned


def merge_ranges(existing: Iterable[Sequence[float]], new: Iterable[Sequence[float]], duration: float) -> list[list[float]]:
    """União ordenada e sem sobreposição, limitada a [0, duração] (ou ao teto, sem duração)."""
    limit = min(duration, MAX_RETENTION_SECONDS) if duration and duration > 0 else MAX_RETENTION_SECONDS
    items = sorted(_clean(list(existing) + list(new), limit))
    merged: list[list[float]] = []
    for start, end in items:
        if merged and start <= merged[-1][1] + MERGE_GAP_SECONDS:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [[round(s, 2), round(e, 2)] for s, e in merged]


def watched_seconds(ranges: Iterable[Sequence[float]]) -> float:
    return sum(max(0.0, e - s) for s, e in ranges)


def retention_counts(sessions_ranges: Iterable[Iterable[Sequence[float]]]) -> list[int]:
    """counts[s] = quantas sessões assistiram alguma parte do segundo s."""
    counts: list[int] = []
    for ranges in sessions_ranges:
        seen: set[int] = set()
        for start, end in ranges:
            first = max(0, int(math.floor(start)))
            last = min(MAX_RETENTION_SECONDS, int(math.ceil(end)))
            seen.update(range(first, last))
        if not seen:
            continue
        top = max(seen) + 1
        if top > len(counts):
            counts.extend([0] * (top - len(counts)))
        for second in seen:
            counts[second] += 1
    return counts


def sum_counts(curves: Iterable[Sequence[int]]) -> list[int]:
    total: list[int] = []
    for curve in curves:
        if len(curve) > len(total):
            total.extend([0] * (len(curve) - len(total)))
        for i, value in enumerate(curve):
            total[i] += value
    return total
