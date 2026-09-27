"""Storage S3 genérico (R2/B2/SeaweedFS): config, URLs públicas, multipart e limpeza."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.storage import StorageNotConfigured, StorageService, resolve_storage_config


def _cfg(**overrides):
    base = dict(
        ENVIRONMENT="development",
        STORAGE_ENDPOINT_URL="",
        STORAGE_PRESIGN_ENDPOINT_URL="",
        STORAGE_ACCESS_KEY_ID="",
        STORAGE_SECRET_ACCESS_KEY="",
        STORAGE_BUCKET="",
        STORAGE_PUBLIC_URL="",
        STORAGE_REGION="auto",
        BACKBLAZE_KEY_ID="",
        BACKBLAZE_APPLICATION_KEY="",
        BACKBLAZE_BUCKET_NAME="",
        BACKBLAZE_ENDPOINT_URL="",
        BACKBLAZE_CDN_URL="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


R2 = dict(
    STORAGE_ENDPOINT_URL="https://abc123.r2.cloudflarestorage.com",
    STORAGE_ACCESS_KEY_ID="key",
    STORAGE_SECRET_ACCESS_KEY="secret",
    STORAGE_BUCKET="vturb-videos",
    STORAGE_PUBLIC_URL="https://video.exemplo.com/",
)


def test_config_storage_prefere_variaveis_storage():
    cfg = resolve_storage_config(_cfg(**R2, BACKBLAZE_BUCKET_NAME="antigo"))
    assert cfg.configured
    assert cfg.bucket == "vturb-videos"
    assert cfg.public_base_url == "https://video.exemplo.com"
    assert cfg.presign_endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_config_storage_cai_para_backblaze_quando_storage_vazio():
    cfg = resolve_storage_config(_cfg(
        BACKBLAZE_KEY_ID="k", BACKBLAZE_APPLICATION_KEY="s", BACKBLAZE_BUCKET_NAME="b2-bucket",
        BACKBLAZE_ENDPOINT_URL="s3.us-west-004.backblazeb2.com",
        BACKBLAZE_CDN_URL="https://s3.us-west-004.backblazeb2.com/file/b2-bucket",
    ))
    assert cfg.configured
    assert cfg.endpoint_url == "https://s3.us-west-004.backblazeb2.com"
    assert cfg.public_base_url == "https://s3.us-west-004.backblazeb2.com/b2-bucket"


def test_config_sem_url_publica_usa_endpoint_e_bucket():
    cfg = resolve_storage_config(_cfg(**{**R2, "STORAGE_PUBLIC_URL": ""}))
    assert cfg.public_base_url == "https://abc123.r2.cloudflarestorage.com/vturb-videos"


def test_config_incompleta_nao_e_configurada():
    assert not resolve_storage_config(_cfg(STORAGE_BUCKET="só-bucket")).configured


def _service(**overrides):
    service = StorageService(settings_obj=_cfg(**R2, **overrides))
    service._s3_client = MagicMock()
    service._presign_client = MagicMock()
    return service


def test_public_url_monta_a_partir_da_chave():
    assert _service().public_url("videos/abc/source.mp4") == "https://video.exemplo.com/videos/abc/source.mp4"


def test_multipart_usa_o_bucket_e_o_content_type():
    service = _service()
    service._s3_client.create_multipart_upload.return_value = {"UploadId": "up-1"}

    upload_id = service.create_multipart_upload("videos/abc/source.mp4", "video/mp4")

    assert upload_id == "up-1"
    service._s3_client.create_multipart_upload.assert_called_once_with(
        Bucket="vturb-videos", Key="videos/abc/source.mp4", ContentType="video/mp4",
        CacheControl="public, max-age=31536000, immutable",
    )


def test_presign_de_parte_usa_o_cliente_publico():
    service = _service()
    service._presign_client.generate_presigned_url.return_value = "https://assinada"

    url = service.presign_upload_part("videos/abc/source.mp4", "up-1", 3)

    assert url == "https://assinada"
    args, kwargs = service._presign_client.generate_presigned_url.call_args
    assert args[0] == "upload_part"
    assert kwargs["Params"] == {"Bucket": "vturb-videos", "Key": "videos/abc/source.mp4", "UploadId": "up-1", "PartNumber": 3}
    assert kwargs["ExpiresIn"] == 3600
    service._s3_client.generate_presigned_url.assert_not_called()


def test_complete_ordena_as_partes():
    service = _service()
    service.complete_multipart_upload("k", "up-1", [(2, '"e2"'), (1, '"e1"')])
    kwargs = service._s3_client.complete_multipart_upload.call_args.kwargs
    assert kwargs["MultipartUpload"]["Parts"] == [
        {"PartNumber": 1, "ETag": '"e1"'},
        {"PartNumber": 2, "ETag": '"e2"'},
    ]


def test_presign_put_assina_o_content_type():
    service = _service()
    service.presign_put("thumbs/abc.jpg", "image/jpeg")
    kwargs = service._presign_client.generate_presigned_url.call_args.kwargs
    assert kwargs["Params"]["ContentType"] == "image/jpeg"


def test_delete_prefix_apaga_em_lotes():
    service = _service()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": f"videos/abc/{i}"} for i in range(1000)]},
        {"Contents": [{"Key": "videos/abc/ultimo"}]},
    ]
    service._s3_client.get_paginator.return_value = paginator

    deleted = service.delete_prefix("videos/abc/")

    assert deleted == 1001
    assert service._s3_client.delete_objects.call_count == 2
    paginator.paginate.assert_called_once_with(Bucket="vturb-videos", Prefix="videos/abc/")


def test_delete_prefix_recusa_prefixo_perigoso():
    service = _service()
    for prefix in ("", "/", "videos/", "videos"):
        with pytest.raises(ValueError):
            service.delete_prefix(prefix)


def test_producao_sem_storage_nao_cai_calado_no_disco():
    import io

    service = StorageService(settings_obj=_cfg(ENVIRONMENT="production"))
    with pytest.raises(StorageNotConfigured):
        service.upload_file(io.BytesIO(b"x"), "v.mp4", "video/mp4")


def test_producao_com_falha_no_s3_propaga_o_erro():
    import io

    service = _service(ENVIRONMENT="production")
    service._s3_client.upload_fileobj.side_effect = RuntimeError("s3 fora")
    with pytest.raises(RuntimeError):
        service.upload_file(io.BytesIO(b"x"), "v.mp4", "video/mp4")


def test_download_para_arquivo_em_streaming(tmp_path):
    service = _service()
    service.download_file("videos/x/source.mp4", str(tmp_path / "in.mp4"))
    service._s3_client.download_file.assert_called_once_with("vturb-videos", "videos/x/source.mp4", str(tmp_path / "in.mp4"))


def test_upload_de_arquivo_com_tipo_e_cache(tmp_path):
    service = _service()
    path = tmp_path / "master.m3u8"
    path.write_text("#EXTM3U")
    service.upload_path(str(path), "videos/x/hls/1/master.m3u8", "application/vnd.apple.mpegurl", "public, max-age=31536000, immutable")
    service._s3_client.upload_file.assert_called_once_with(
        str(path), "vturb-videos", "videos/x/hls/1/master.m3u8",
        ExtraArgs={"ContentType": "application/vnd.apple.mpegurl", "CacheControl": "public, max-age=31536000, immutable"},
    )
