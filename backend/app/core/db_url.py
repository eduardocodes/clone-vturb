"""Normalização da URL do banco (sem imports do app: seguro de importar cedo)."""


def engine_url(url: str) -> str:
    """Fixa o driver psycopg2 (o instalado).

    O SQLAlchemy 2.1 passou a usar psycopg (v3) para ``postgresql://``; sem isso,
    uma DATABASE_URL comum quebra o boot com ``No module named 'psycopg'``.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url
