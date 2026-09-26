import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_user
from app.models.user import User

client = TestClient(app)

mock_admin = User(
    id="test-admin-id",
    email="admin@vturb.com",
    is_super_admin=True
)

@pytest.fixture(autouse=True)
def override_auth_dependency():
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    yield
    app.dependency_overrides.pop(get_current_user, None)

def test_video_crud_and_analytics_flow():
    # 1. Criação do Vídeo
    payload = {
        "title": "Vídeo de Teste Vturb",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "thumbnail_url": "https://images.unsplash.com/photo-1536240478700-b869070f9279",
        "duration": 60.0,
        "player_settings": {
            "primary_color": "#10b981",
            "autoplay": True,
            "show_controls": True,
            "cta_enabled": True,
            "cta_time": 10,
            "cta_text": "Quero Aproveitar a Oferta",
            "cta_link": "https://checkout.exemplo.com"
        }
    }
    create_res = client.post("/videos/", json=payload)
    assert create_res.status_code == 201
    video_data = create_res.json()
    video_id = video_data["id"]
    assert video_data["title"] == payload["title"]
    assert video_data["player_settings"]["primary_color"] == "#10b981"
    assert video_data["plays_count"] == 0

    # 2. Listagem
    list_res = client.get("/videos/")
    assert list_res.status_code == 200
    videos = list_res.json()
    created_video_item = next(v for v in videos if v["id"] == video_id)
    assert created_video_item["plays_count"] == 0

    # 3. Consulta individual
    get_res = client.get(f"/videos/{video_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == video_id

    # 4. Envio de telemetria / eventos do player
    # Evento de impressão
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "impression",
        "session_id": "sess_123",
        "referer": "https://meusite.com"
    })
    # Evento de play
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "play",
        "watch_time_seconds": 1.0,
        "session_id": "sess_123"
    })
    # Eventos de retenção
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "progress_25",
        "watch_time_seconds": 15.0,
        "session_id": "sess_123"
    })
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "progress_50",
        "watch_time_seconds": 30.0,
        "session_id": "sess_123"
    })
    # Evento de clique
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "click",
        "session_id": "sess_123"
    })

    # Outra impressão do mesmo visitante (ex: refresh na página)
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "impression",
        "session_id": "sess_123",
        "referer": "https://meusite.com"
    })
    # Impressão de um segundo visitante diferente
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "impression",
        "session_id": "sess_456",
        "referer": "https://outro-site.com"
    })

    # 5. Validação das Métricas Consolidadas
    metrics_res = client.get(f"/videos/{video_id}/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["video_id"] == video_id
    # Total de 3 impressões (2 de sess_123 + 1 de sess_456)
    assert metrics["total_impressions"] == 3
    # Apenas 2 visitantes únicos
    assert metrics["unique_impressions"] == 2
    assert metrics["total_plays"] == 1
    assert metrics["unique_plays"] == 1
    assert metrics["play_rate"] == 33.33
    assert metrics["total_clicks"] == 1
    assert metrics["ctr"] == 100.0
    assert metrics["retention"]["25%"] == 1
    assert metrics["retention"]["50%"] == 1
    assert metrics["retention"]["75%"] == 0

    # 6. Deleção
    del_res = client.delete(f"/videos/{video_id}")
    assert del_res.status_code == 204

    # Confirma que foi deletado
    assert client.get(f"/videos/{video_id}").status_code == 404


def test_upload_video_and_thumbnail_files():
    # 1. Upload de arquivo de vídeo (.mp4)
    video_content = b"dummy mp4 video bytes"
    res_video = client.post(
        "/videos/upload",
        files={"file": ("minha_vsl.mp4", video_content, "video/mp4")}
    )
    assert res_video.status_code == 200
    video_json = res_video.json()
    assert video_json["filename"] == "minha_vsl.mp4"
    assert video_json["url"].startswith("/static/uploads/") or "backblazeb2.com" in video_json["url"] or video_json["url"].startswith("http")
    assert video_json["url"].endswith(".mp4")

    # 2. Upload de arquivo de imagem/capa (.png)
    img_content = b"dummy png image bytes"
    res_img = client.post(
        "/videos/upload",
        files={"file": ("capa_promocional.png", img_content, "image/png")}
    )
    assert res_img.status_code == 200
    img_json = res_img.json()
    assert img_json["filename"] == "capa_promocional.png"
    assert img_json["url"].startswith("/static/uploads/") or "backblazeb2.com" in img_json["url"] or img_json["url"].startswith("http")
    assert img_json["url"].endswith(".png")

    # 3. Rejeição de extensão não permitida (.exe)
    res_bad = client.post(
        "/videos/upload",
        files={"file": ("malware.exe", b"bad", "application/x-msdownload")}
    )
    assert res_bad.status_code == 400
    assert "Formato de arquivo não suportado" in res_bad.json()["detail"]


def test_metrics_date_filters_and_hourly_distribution():
    # 1. Cria um vídeo para teste analítico
    create_res = client.post("/videos/", json={
        "title": "Vídeo Analítico por Horário",
        "video_url": "https://exemplo.com/analytics.mp4"
    })
    video_id = create_res.json()["id"]

    # 2. Registra eventos no vídeo
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "impression",
        "session_id": "sess_h1"
    })
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "play",
        "watch_time_seconds": 25.0,
        "session_id": "sess_h1"
    })
    client.post(f"/videos/{video_id}/events", json={
        "event_type": "click",
        "session_id": "sess_h1"
    })

    # 3. Testa consulta com filtro 'today'
    res_today = client.get(f"/videos/{video_id}/metrics?period=today")
    assert res_today.status_code == 200
    metrics_today = res_today.json()
    assert metrics_today["period"] == "today"
    assert metrics_today["total_impressions"] == 1
    assert metrics_today["total_plays"] == 1
    assert metrics_today["total_clicks"] == 1
    assert len(metrics_today["hourly_distribution"]) == 24
    assert metrics_today["peak_hour"] is not None
    assert metrics_today["peak_hour"]["total_activity"] >= 1

    # 4. Testa consulta com filtro de período que não tem eventos (ex: ontem)
    res_yesterday = client.get(f"/videos/{video_id}/metrics?period=yesterday")
    assert res_yesterday.status_code == 200
    metrics_yesterday = res_yesterday.json()
    assert metrics_yesterday["period"] == "yesterday"
    assert metrics_yesterday["total_impressions"] == 0
    assert metrics_yesterday["total_plays"] == 0
    assert metrics_yesterday["peak_hour"] is None

    # 5. Testa consulta com período '7d'
    res_7d = client.get(f"/videos/{video_id}/metrics?period=7d")
    assert res_7d.status_code == 200
    assert res_7d.json()["total_plays"] == 1

    # 6. Testa consulta com datas customizadas
    res_custom = client.get(f"/videos/{video_id}/metrics?start_date=2026-01-01&end_date=2026-12-31")
    assert res_custom.status_code == 200
    metrics_custom = res_custom.json()
    assert metrics_custom["period"] == "custom"
    assert metrics_custom["total_plays"] >= 1

    # 7. Validação do Fuso Horário de Brasília (America/Sao_Paulo / UTC-3)
    assert "Horário de Brasília" in metrics_today["timezone"]
    assert "America/Sao_Paulo" in metrics_today["timezone"]

    # Criação de evento com timestamp em UTC para validar conversão para Brasília
    # Ex: 2026-09-10 17:00:00 UTC deve virar 14:00 em Brasília (UTC-3)
    from app.core.database import SessionLocal
    from app.models.video import VideoAnalytics
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        utc_dt = datetime(2026, 9, 10, 17, 0, 0, tzinfo=timezone.utc)
        ev_brt_test = VideoAnalytics(
            video_id=video_id,
            event_type="play",
            created_at=utc_dt,
            session_id="sess_brt_test",
        )
        db.add(ev_brt_test)
        db.commit()
    finally:
        db.close()

    res_custom_hour = client.get(f"/videos/{video_id}/metrics?start_date=2026-09-10&end_date=2026-09-10")
    assert res_custom_hour.status_code == 200
    metrics_hour = res_custom_hour.json()
    # No bucket 14 (14:00 BRT), deve haver pelo menos 1 play vindo do evento das 17h UTC
    bucket_14 = next(h for h in metrics_hour["hourly_distribution"] if h["hour"] == 14)
    assert bucket_14["plays"] >= 1

    # Limpeza
    client.delete(f"/videos/{video_id}")


def test_video_turbo_speed_setting():
    # 1. Cria um vídeo
    create_res = client.post("/videos/", json={
        "title": "Vídeo Modo Turbo",
        "video_url": "https://exemplo.com/turbo.mp4"
    })
    assert create_res.status_code == 201
    video_id = create_res.json()["id"]

    # 2. Atualiza com velocidade Turbo 1.5x
    update_res = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            "primary_color": "#f59e0b",
            "playback_rate": 1.5,
            "turbo_enabled": True
        }
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["player_settings"]["playback_rate"] == 1.5
    assert updated_data["player_settings"]["turbo_enabled"] is True

    # 3. Consulta para garantir persistência
    get_res = client.get(f"/videos/{video_id}")
    assert get_res.status_code == 200
    assert get_res.json()["player_settings"]["playback_rate"] == 1.5

    # 4. Atualiza para 0.5x (mais devagar)
    update_slow = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            "playback_rate": 0.5,
            "turbo_enabled": True
        }
    })
    assert update_slow.status_code == 200
    assert update_slow.json()["player_settings"]["playback_rate"] == 0.5

    # 5. Atualiza para 2.0x (ultra-rápido)
    update_fast = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            "playback_rate": 2.0,
            "turbo_enabled": True
        }
    })
    assert update_fast.status_code == 200
    assert update_fast.json()["player_settings"]["playback_rate"] == 2.0

    # Limpeza
    client.delete(f"/videos/{video_id}")


def test_bulk_delete_videos():
    # 1. Cria 3 vídeos de teste
    created_ids = []
    for i in range(3):
        res = client.post("/videos/", json={
            "title": f"Vídeo Bulk {i+1}",
            "video_url": f"https://cdn.exemplo.com/v_{i+1}.mp4",
        })
        assert res.status_code == 201
        created_ids.append(res.json()["id"])

    assert len(created_ids) == 3

    # 2. Executa a exclusão em massa
    bulk_res = client.post("/videos/bulk-delete", json={
        "video_ids": created_ids
    })
    assert bulk_res.status_code == 200
    bulk_data = bulk_res.json()
    assert bulk_data["deleted_count"] == 3
    assert set(bulk_data["deleted_ids"]) == set(created_ids)

    # 3. Verifica que nenhum dos 3 vídeos existe mais
    for vid_id in created_ids:
        get_res = client.get(f"/videos/{vid_id}")
        assert get_res.status_code == 404


def test_advanced_player_settings_persistence():
    # 1. Cria vídeo
    create_res = client.post("/videos/", json={
        "title": "Vídeo Recursos Avançados",
        "video_url": "https://cdn.exemplo.com/vsl_avancada.mp4",
        "player_settings": {
            "primary_color": "#4f46e5",
            "smart_autoplay": {
                "enabled": True,
                "text": "Seu vídeo já começou!",
                "button_color": "#ef4444",
                "button_text": "CLIQUE PARA OUVIR",
                "restart_on_unmute": True,
                "size": "small"
            },
            "floating_player": {
                "enabled": True,
                "position": "bottom-right",
                "width": 340,
                "closeable": True
            },
            "pitch_delay": {
                "enabled": True,
                "time": 45,
                "target_css_selector": ".delay-pitch, #oferta",
                "auto_scroll": True,
                "persistence": True
            },
            "tracking_pixels": {
                "enabled": True,
                "facebook_pixel_id": "1234567890",
                "google_analytics_id": "G-XXXX1234",
                "tiktok_pixel_id": "TT998877",
                "events": [
                    {"trigger": "percent_50", "event_name": "View50", "enabled": True}
                ]
            },
            "domain_protection": {
                "enabled": True,
                "allowed_domains": ["meusite.com.br", "checkout.exemplo.com"],
                "anti_download": True
            }
        }
    })
    assert create_res.status_code == 201
    video_id = create_res.json()["id"]

    # 2. Consulta e valida persistência
    get_res = client.get(f"/videos/{video_id}")
    assert get_res.status_code == 200
    settings = get_res.json()["player_settings"]

    assert settings["smart_autoplay"]["enabled"] is True
    assert settings["smart_autoplay"]["button_text"] == "CLIQUE PARA OUVIR"
    assert settings["smart_autoplay"]["size"] == "small"
    assert settings["floating_player"]["enabled"] is True
    assert settings["floating_player"]["position"] == "bottom-right"
    assert settings["pitch_delay"]["enabled"] is True
    assert settings["pitch_delay"]["time"] == 45
    assert settings["tracking_pixels"]["enabled"] is True
    assert settings["tracking_pixels"]["facebook_pixel_id"] == "1234567890"
    assert settings["domain_protection"]["enabled"] is True
    assert "meusite.com.br" in settings["domain_protection"]["allowed_domains"]

    # 3. Atualiza ativando mode direct (sem chamada na frente)
    update_res_direct = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            **settings,
            "smart_autoplay": {
                **settings["smart_autoplay"],
                "enabled": True,
                "mode": "direct"
            }
        }
    })
    assert update_res_direct.status_code == 200
    direct_settings = update_res_direct.json()["player_settings"]
    assert direct_settings["smart_autoplay"]["enabled"] is True
    assert direct_settings["smart_autoplay"]["mode"] == "direct"

    # 4. Atualiza desativando smart_autoplay, alterando size para mini e alterando tempo do pitch
    update_res = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            **settings,
            "smart_autoplay": {
                **settings["smart_autoplay"],
                "enabled": False,
                "size": "mini"
            },
            "pitch_delay": {
                **settings["pitch_delay"],
                "time": 90
            }
        }
    })
    assert update_res.status_code == 200
    updated_settings = update_res.json()["player_settings"]
    assert updated_settings["smart_autoplay"]["enabled"] is False
    assert updated_settings["smart_autoplay"]["size"] == "mini"
    assert updated_settings["pitch_delay"]["time"] == 90

    # Limpeza
    client.delete(f"/videos/{video_id}")

def test_video_controls_styling_config():
    """Valida salvamento e recuperação das opções visuais de controles do player (Voltar 10s, Avançar 10s, etc.)."""
    create_res = client.post("/videos/", json={
        "title": "Vídeo Estilização Controles",
        "video_url": "https://cdn.exemplo.com/estilizacao.mp4",
        "duration": 180.0,
        "player_settings": {
            "primary_color": "#10b981",
            "controls_config": {
                "rewind_10s": True,
                "forward_10s": False,
                "volume": True,
                "fullscreen": True,
                "speed_control": False
            }
        }
    })
    assert create_res.status_code == 201
    video = create_res.json()
    video_id = video["id"]
    cfg = video["player_settings"].get("controls_config", {})
    assert cfg.get("rewind_10s") is True
    assert cfg.get("forward_10s") is False
    assert cfg.get("speed_control") is False

    # Atualiza opções
    update_res = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            **video["player_settings"],
            "controls_config": {
                "rewind_10s": False,
                "forward_10s": True,
                "volume": True,
                "fullscreen": False,
                "speed_control": True
            }
        }
    })
    assert update_res.status_code == 200
    updated_cfg = update_res.json()["player_settings"]["controls_config"]
    assert updated_cfg["rewind_10s"] is False
    assert updated_cfg["forward_10s"] is True
    assert updated_cfg["fullscreen"] is False
    assert updated_cfg["speed_control"] is True

    # Limpeza
    client.delete(f"/videos/{video_id}")







def test_video_smart_progress_setting():
    """Valida persistência do Progresso Inteligente (smart_progress) via POST e PUT."""
    create_res = client.post("/videos/", json={
        "title": "Vídeo Progresso Inteligente",
        "video_url": "https://cdn.exemplo.com/progresso.mp4",
        "duration": 300.0,
        "player_settings": {
            "primary_color": "#ef4444",
            "smart_progress": {"enabled": True, "intensity": "forte"}
        }
    })
    assert create_res.status_code == 201
    video = create_res.json()
    video_id = video["id"]
    assert video["player_settings"]["smart_progress"] == {"enabled": True, "intensity": "forte"}

    update_res = client.put(f"/videos/{video_id}", json={
        "player_settings": {
            **video["player_settings"],
            "smart_progress": {"enabled": False, "intensity": "suave"}
        }
    })
    assert update_res.status_code == 200
    assert update_res.json()["player_settings"]["smart_progress"] == {"enabled": False, "intensity": "suave"}

    get_res = client.get(f"/videos/{video_id}")
    assert get_res.json()["player_settings"]["smart_progress"]["intensity"] == "suave"

    client.delete(f"/videos/{video_id}")

def test_video_smart_progress_defaults_and_absence():
    """Sem a chave, o vídeo continua válido; com a chave parcial, aplica os padrões."""
    res_without = client.post("/videos/", json={
        "title": "Vídeo sem Progresso Inteligente",
        "video_url": "https://cdn.exemplo.com/sem.mp4",
        "player_settings": {"primary_color": "#111111"}
    })
    assert res_without.status_code == 201
    assert res_without.json()["player_settings"].get("smart_progress") is None

    res_partial = client.post("/videos/", json={
        "title": "Vídeo com Progresso Inteligente parcial",
        "video_url": "https://cdn.exemplo.com/parcial.mp4",
        "player_settings": {"smart_progress": {"enabled": True}}
    })
    assert res_partial.status_code == 201
    assert res_partial.json()["player_settings"]["smart_progress"] == {"enabled": True, "intensity": "medio"}

    client.delete(f"/videos/{res_without.json()['id']}")
    client.delete(f"/videos/{res_partial.json()['id']}")

@pytest.mark.parametrize("intensity", ["turbo", "", "FORTE", 3])
def test_video_smart_progress_rejects_invalid_intensity(intensity):
    """Intensidade fora de suave/medio/forte é rejeitada com 422."""
    res = client.post("/videos/", json={
        "title": "Vídeo intensidade inválida",
        "video_url": "https://cdn.exemplo.com/invalido.mp4",
        "player_settings": {"smart_progress": {"enabled": True, "intensity": intensity}}
    })
    assert res.status_code == 422
