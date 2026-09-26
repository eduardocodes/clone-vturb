"""Upload direto do navegador para o storage S3 (R2/B2), com URLs assinadas.

Fluxo do vídeo (multipart): init -> sign-parts (em lotes) -> PUT de cada parte
direto no storage -> complete. Capa: init devolve um PUT assinado único.
O arquivo nunca passa pelo backend nem pelo Cloudflare Tunnel.
"""
import logging
import math
import re
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.storage import storage_service

logger = logging.getLogger("projetovturb.uploads")
router = APIRouter(prefix="/uploads", tags=["Uploads"])

S3_MAX_PARTS = 10_000
MAX_PARTS_PER_SIGN = 100

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Chaves que este módulo gera; nada fora disso pode ser assinado
VIDEO_SOURCE_KEY_RE = re.compile(r"^videos/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/source\.(mp4|webm|mov|m4v)$")


class InitUploadRequest(BaseModel):
    kind: Literal["video", "thumbnail"]
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    size: int = Field(..., ge=0)


class SignPartsRequest(BaseModel):
    key: str = Field(..., max_length=200)
    upload_id: str = Field(..., min_length=1, max_length=1024)
    part_numbers: list[int] = Field(..., min_length=1, max_length=MAX_PARTS_PER_SIGN)


class UploadedPart(BaseModel):
    part_number: int = Field(..., ge=1, le=S3_MAX_PARTS)
    etag: str = Field(..., min_length=1, max_length=200)


class CompleteUploadRequest(BaseModel):
    key: str = Field(..., max_length=200)
    upload_id: str = Field(..., min_length=1, max_length=1024)
    size: int = Field(..., gt=0)
    parts: list[UploadedPart] = Field(..., min_length=1, max_length=S3_MAX_PARTS)


class AbortUploadRequest(BaseModel):
    key: str = Field(..., max_length=200)
    upload_id: str = Field(..., min_length=1, max_length=1024)


def _require_storage() -> None:
    if not storage_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload direto indisponível: storage não configurado.",
        )


def _require_video_key(key: str) -> None:
    if not VIDEO_SOURCE_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chave de upload inválida.")


def _validate_file(payload: InitUploadRequest) -> str:
    ext = Path(payload.filename).suffix.lower()
    if payload.kind == "video":
        allowed, mime_prefix, max_bytes = VIDEO_EXTENSIONS, "video/", settings.MAX_VIDEO_BYTES
    else:
        allowed, mime_prefix, max_bytes = IMAGE_EXTENSIONS, "image/", settings.MAX_IMAGE_BYTES

    if ext not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Formato não suportado: {ext or 'sem extensão'}.")
    if not payload.content_type.lower().startswith(mime_prefix):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo do arquivo não corresponde à extensão.")
    if payload.size <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")
    if payload.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo maior que o limite de {max_bytes // (1024 * 1024)} MB.",
        )
    return ext


def plan_parts(size: int, base_part_size: int) -> tuple[int, int]:
    """(tamanho da parte, quantidade de partes) respeitando o limite de 10.000 partes do S3."""
    part_size = max(base_part_size, math.ceil(size / S3_MAX_PARTS))
    return part_size, math.ceil(size / part_size)


@router.get("/config")
def upload_config(current_user: User = Depends(get_current_user)):
    return {
        "direct": storage_service.is_configured(),
        "max_video_bytes": settings.MAX_VIDEO_BYTES,
        "max_image_bytes": settings.MAX_IMAGE_BYTES,
        "part_size": settings.UPLOAD_PART_SIZE,
    }


@router.post("/init")
def init_upload(payload: InitUploadRequest, current_user: User = Depends(get_current_user)):
    ext = _validate_file(payload)
    _require_storage()
    content_type = payload.content_type.lower()

    if payload.kind == "thumbnail":
        key = f"thumbs/{uuid.uuid4()}{ext}"
        return {
            "method": "put",
            "key": key,
            "url": storage_service.presign_put(key, content_type),
            "headers": {"Content-Type": content_type},
            "public_url": storage_service.public_url(key),
        }

    key = f"videos/{uuid.uuid4()}/source{ext}"
    upload_id = storage_service.create_multipart_upload(key, content_type)
    part_size, part_count = plan_parts(payload.size, settings.UPLOAD_PART_SIZE)
    logger.info(f"Upload direto iniciado por {current_user.email}: {key} ({payload.size} bytes, {part_count} partes)")
    return {
        "method": "multipart",
        "key": key,
        "upload_id": upload_id,
        "part_size": part_size,
        "part_count": part_count,
    }


@router.post("/sign-parts")
def sign_parts(payload: SignPartsRequest, current_user: User = Depends(get_current_user)):
    _require_storage()
    _require_video_key(payload.key)
    if any(n < 1 or n > S3_MAX_PARTS for n in payload.part_numbers):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Número de parte inválido.")
    urls = {
        str(n): storage_service.presign_upload_part(payload.key, payload.upload_id, n)
        for n in sorted(set(payload.part_numbers))
    }
    return {"urls": urls}


@router.post("/complete")
def complete_upload(payload: CompleteUploadRequest, current_user: User = Depends(get_current_user)):
    _require_storage()
    _require_video_key(payload.key)
    storage_service.complete_multipart_upload(
        payload.key, payload.upload_id, [(p.part_number, p.etag) for p in payload.parts]
    )
    stored = storage_service.head(payload.key)
    if stored["size"] != payload.size:
        logger.warning(f"Upload {payload.key} com tamanho divergente: esperado {payload.size}, recebido {stored['size']}")
        storage_service.delete_object(payload.key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload incompleto. Tente enviar novamente.")
    return {"key": payload.key, "url": storage_service.public_url(payload.key), "size": stored["size"]}


@router.post("/abort", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(payload: AbortUploadRequest, current_user: User = Depends(get_current_user)):
    _require_storage()
    _require_video_key(payload.key)
    storage_service.abort_multipart_upload(payload.key, payload.upload_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
