"""Origem do espectador (público, chamado pelo player): POST /videos/{id}/attribution.

First-touch por (video_id, session_id): as UTMs da primeira chegada ficam; o
external_id (xid) só é gravado enquanto estiver nulo. Contrato: contracts/export-v1.json.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.models.video import Video
from app.models.viewer_attribution import UTM_FIELDS, UTM_MAX_LENGTH, XID_MAX_LENGTH, ViewerAttribution

router = APIRouter(prefix="/videos", tags=["Attribution"])

XID_PATTERN = rf"^[A-Za-z0-9_-]{{1,{XID_MAX_LENGTH}}}$"


class AttributionPayload(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    # Opaco para o Smart VSL (o TrackDash manda o _eid da LP)
    xid: Optional[str] = Field(None, pattern=XID_PATTERN)
    # Truncadas (não recusadas): UTMs de anúncio podem ser longas
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None


def _utm(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    return value[:UTM_MAX_LENGTH]


@router.post(
    "/{video_id}/attribution",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("attribution", 120))],
)
def record_attribution(video_id: str, payload: AttributionPayload, db: Session = Depends(get_db)):
    if not db.query(Video.id).filter(Video.id == video_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    values = {
        "video_id": video_id,
        "session_id": payload.session_id,
        "external_id": payload.xid,
        **{field: _utm(getattr(payload, field)) for field in UTM_FIELDS},
    }
    stmt = pg_insert(ViewerAttribution).values(**values)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["video_id", "session_id"],
            set_={"external_id": func.coalesce(ViewerAttribution.external_id, stmt.excluded.external_id)},
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
