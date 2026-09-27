"""Storage de vídeos e capas em qualquer serviço compatível com S3.

Duas formas de envio:
- Upload direto (preferido): o navegador envia para o storage com URLs assinadas
  (multipart para vídeo, PUT único para capa). O arquivo nunca passa pelo backend.
- ``upload_file`` (legado): o arquivo passa pelo backend. Mantido para dev e para
  instalações sem storage; em produção exige storage e não cai calado no disco.
"""
import logging
import mimetypes
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Optional

import boto3
from botocore.config import Config

from app.core.config import settings

logger = logging.getLogger("projetovturb")

# Diretório local padrão para fallback de desenvolvimento e testes
LOCAL_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "uploads"
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Objetos de vídeo/capa nunca mudam de conteúdo (chave nova a cada envio): cache eterno
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
PRESIGNED_PART_TTL_SECONDS = 3600
PRESIGNED_PUT_TTL_SECONDS = 900
_DELETE_BATCH = 1000


class StorageNotConfigured(RuntimeError):
    """Storage S3 ausente onde ele é obrigatório (produção)."""


def _with_scheme(endpoint: str) -> str:
    endpoint = endpoint.strip().rstrip("/")
    if endpoint and not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}"
    return endpoint


def _strip_b2_file_segment(url: str) -> str:
    # O endpoint S3 do Backblaze não aceita o segmento /file/ da URL "amigável"
    return re.sub(r"(https?://s3\.[^/]+\.backblazeb2\.com)/file", r"\1", url)


@dataclass(frozen=True)
class StorageConfig:
    endpoint_url: str
    presign_endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    public_base_url: str
    region: str

    @property
    def configured(self) -> bool:
        return bool(self.endpoint_url and self.access_key_id and self.secret_access_key and self.bucket)


def resolve_storage_config(cfg=settings) -> StorageConfig:
    """STORAGE_* tem prioridade; sem ele, usa as variáveis antigas BACKBLAZE_*."""
    use_generic = bool(cfg.STORAGE_BUCKET or cfg.STORAGE_ENDPOINT_URL)
    if use_generic:
        endpoint = _with_scheme(cfg.STORAGE_ENDPOINT_URL)
        key_id, secret, bucket = cfg.STORAGE_ACCESS_KEY_ID, cfg.STORAGE_SECRET_ACCESS_KEY, cfg.STORAGE_BUCKET
        public = cfg.STORAGE_PUBLIC_URL
        presign = _with_scheme(cfg.STORAGE_PRESIGN_ENDPOINT_URL) or endpoint
    else:
        endpoint = _with_scheme(cfg.BACKBLAZE_ENDPOINT_URL)
        key_id, secret, bucket = cfg.BACKBLAZE_KEY_ID, cfg.BACKBLAZE_APPLICATION_KEY, cfg.BACKBLAZE_BUCKET_NAME
        public = cfg.BACKBLAZE_CDN_URL
        presign = endpoint

    public = _strip_b2_file_segment(public.strip().rstrip("/")) if public else ""
    if not public and endpoint and bucket:
        public = f"{endpoint}/{bucket}"

    return StorageConfig(
        endpoint_url=endpoint,
        presign_endpoint_url=presign,
        access_key_id=(key_id or "").strip(),
        secret_access_key=(secret or "").strip(),
        bucket=(bucket or "").strip(),
        public_base_url=public,
        region=getattr(cfg, "STORAGE_REGION", "auto") or "auto",
    )


class StorageService:
    def __init__(self, settings_obj=None):
        self._settings = settings_obj
        self._s3_client = None
        self._presign_client = None

    # --- configuração ---------------------------------------------------------

    @property
    def _cfg(self):
        return self._settings if self._settings is not None else settings

    @property
    def config(self) -> StorageConfig:
        # Resolvido a cada acesso: testes e scripts ajustam settings em tempo de execução
        return resolve_storage_config(self._cfg)

    def is_configured(self) -> bool:
        return self.config.configured

    # Nome antigo, mantido por compatibilidade
    def is_backblaze_configured(self) -> bool:
        return self.is_configured()

    def _is_production(self) -> bool:
        return getattr(self._cfg, "ENVIRONMENT", "development") == "production"

    def _build_client(self, endpoint: str):
        cfg = self.config
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=cfg.access_key_id,
            aws_secret_access_key=cfg.secret_access_key,
            region_name=cfg.region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def get_s3_client(self):
        """Cliente para operações feitas pelo backend (rede interna)."""
        if self._s3_client is None:
            self._s3_client = self._build_client(self.config.endpoint_url)
        return self._s3_client

    def get_presign_client(self):
        """Cliente só para assinar URLs que o navegador vai usar (endpoint público)."""
        if self._presign_client is None:
            self._presign_client = self._build_client(self.config.presign_endpoint_url)
        return self._presign_client

    # --- URLs públicas --------------------------------------------------------

    def public_url(self, key: str) -> str:
        return f"{self.config.public_base_url}/{key.lstrip('/')}"

    def key_from_public_url(self, url: Optional[str]) -> Optional[str]:
        """Chave do objeto se a URL for deste storage; None para URLs externas ou locais."""
        base = self.config.public_base_url
        if not url or not base or not url.startswith(base + "/"):
            return None
        return url[len(base) + 1:]

    # --- upload direto (URLs assinadas) ---------------------------------------

    def create_multipart_upload(self, key: str, content_type: str) -> str:
        res = self.get_s3_client().create_multipart_upload(
            Bucket=self.config.bucket, Key=key, ContentType=content_type,
            CacheControl=IMMUTABLE_CACHE_CONTROL,
        )
        return res["UploadId"]

    def presign_upload_part(self, key: str, upload_id: str, part_number: int) -> str:
        return self.get_presign_client().generate_presigned_url(
            "upload_part",
            Params={"Bucket": self.config.bucket, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
            ExpiresIn=PRESIGNED_PART_TTL_SECONDS,
        )

    def complete_multipart_upload(self, key: str, upload_id: str, parts: Iterable[tuple[int, str]]) -> None:
        ordered = sorted(parts, key=lambda p: p[0])
        self.get_s3_client().complete_multipart_upload(
            Bucket=self.config.bucket, Key=key, UploadId=upload_id,
            MultipartUpload={"Parts": [{"PartNumber": n, "ETag": etag} for n, etag in ordered]},
        )

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self.get_s3_client().abort_multipart_upload(Bucket=self.config.bucket, Key=key, UploadId=upload_id)

    def presign_put(self, key: str, content_type: str) -> str:
        # O Content-Type entra na assinatura: o navegador precisa enviar exatamente o mesmo
        return self.get_presign_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.config.bucket, "Key": key, "ContentType": content_type,
                "CacheControl": IMMUTABLE_CACHE_CONTROL,
            },
            ExpiresIn=PRESIGNED_PUT_TTL_SECONDS,
        )

    def head(self, key: str) -> dict:
        res = self.get_s3_client().head_object(Bucket=self.config.bucket, Key=key)
        return {"size": res["ContentLength"], "content_type": res.get("ContentType")}

    # --- arquivos do worker (transcode) ------------------------------------------

    def download_file(self, key: str, path: str) -> None:
        """Baixa o objeto para disco em partes (nunca inteiro na memória)."""
        self.get_s3_client().download_file(self.config.bucket, key, path)

    def upload_path(self, path: str, key: str, content_type: str, cache_control: str) -> None:
        self.get_s3_client().upload_file(
            path, self.config.bucket, key,
            ExtraArgs={"ContentType": content_type, "CacheControl": cache_control},
        )

    # --- limpeza ----------------------------------------------------------------

    def delete_object(self, key: str) -> None:
        self.get_s3_client().delete_object(Bucket=self.config.bucket, Key=key)

    def delete_prefix(self, prefix: str) -> int:
        """Apaga todos os objetos sob o prefixo (ex.: ``videos/<uuid>/``)."""
        parts = [p for p in prefix.split("/") if p]
        if len(parts) < 2 or ".." in parts or not prefix.endswith("/"):
            raise ValueError(f"Prefixo perigoso para exclusão em massa: {prefix!r}")

        s3 = self.get_s3_client()
        bucket = self.config.bucket
        deleted = 0
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            for start in range(0, len(keys), _DELETE_BATCH):
                batch = keys[start:start + _DELETE_BATCH]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
                deleted += len(batch)
        return deleted

    # --- upload legado (arquivo passa pelo backend) -------------------------------

    def upload_file(
        self,
        file_obj: BinaryIO,
        original_filename: str,
        content_type: Optional[str] = None
    ) -> str:
        """Envia para o storage S3 e retorna a URL pública.

        Em dev, sem storage (ou com erro nele), grava em static/uploads/. Em produção
        isso é proibido: sem storage levanta StorageNotConfigured e erros propagam.
        """
        ext = Path(original_filename).suffix.lower()
        unique_key = f"{uuid.uuid4()}{ext}"

        if not content_type:
            guessed_type, _ = mimetypes.guess_type(original_filename)
            content_type = guessed_type or "application/octet-stream"

        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(0)
            except Exception:
                pass

        if not self.is_configured():
            if self._is_production():
                raise StorageNotConfigured("Storage S3 não configurado (defina STORAGE_*).")
            return self._save_local(file_obj, unique_key)

        try:
            s3 = self.get_s3_client()
            logger.info(f"Iniciando upload para o storage: bucket={self.config.bucket}, key={unique_key}")
            s3.upload_fileobj(
                file_obj,
                self.config.bucket,
                unique_key,
                ExtraArgs={"ContentType": content_type},
            )
            public_url = self.public_url(unique_key)
            logger.info(f"Upload concluído no storage: {public_url}")
            return public_url
        except Exception as exc:
            if self._is_production():
                logger.error(f"Erro no upload para o storage: {exc}")
                raise
            logger.error(f"Erro no upload para o storage: {exc}. Realizando fallback para armazenamento local.")
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            return self._save_local(file_obj, unique_key)

    def _save_local(self, file_obj: BinaryIO, unique_key: str) -> str:
        destination = LOCAL_UPLOAD_DIR / unique_key
        with open(destination, "wb") as buffer:
            while chunk := file_obj.read(1024 * 1024):
                buffer.write(chunk)
        local_url = f"/static/uploads/{unique_key}"
        logger.info(f"Arquivo salvo com sucesso no storage local: {local_url}")
        return local_url


storage_service = StorageService()
