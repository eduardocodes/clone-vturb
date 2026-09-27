"""HLS: escada de qualidades, leitura do ffprobe e comando do ffmpeg (funções puras) + transcode real."""
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services import hls

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _heights(renditions):
    return [r.height for r in renditions]


def test_escada_completa_para_fonte_1080p():
    assert _heights(hls.ladder_for(1920, 1080)) == [360, 540, 720, 1080]


def test_escada_nunca_faz_upscale():
    assert _heights(hls.ladder_for(1280, 720)) == [360, 540, 720]


def test_fonte_entre_degraus_ganha_a_qualidade_original():
    # 480p não pode cair para 360p como teto
    assert _heights(hls.ladder_for(854, 480)) == [360, 480]


def test_fonte_menor_que_o_primeiro_degrau_fica_no_tamanho_original():
    assert _heights(hls.ladder_for(426, 240)) == [240]


def test_video_vertical_usa_o_lado_menor():
    # VSL gravada no celular: 1080x1920 é "1080p", não 1920p
    ladder = hls.ladder_for(1080, 1920)
    assert _heights(ladder) == [360, 540, 720, 1080]


def test_dimensao_impar_vira_par():
    assert _heights(hls.ladder_for(640, 361)) == [360]


def test_bitrate_sobe_com_a_qualidade():
    rates = [r.video_kbps for r in hls.ladder_for(1920, 1080)]
    assert rates == sorted(rates)


PROBE = {
    "streams": [
        {"codec_type": "video", "width": 1920, "height": 1080},
        {"codec_type": "audio"},
    ],
    "format": {"duration": "150.4"},
}


def test_leitura_do_ffprobe():
    info = hls.parse_probe(PROBE)
    assert (info.width, info.height, info.duration, info.has_audio) == (1920, 1080, 150.4, True)


def test_ffprobe_de_celular_girado_troca_largura_e_altura():
    probe = {
        "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "side_data_list": [{"rotation": -90}]}],
        "format": {"duration": "10"},
    }
    info = hls.parse_probe(probe)
    assert (info.width, info.height, info.has_audio) == (1080, 1920, False)


def test_ffprobe_sem_video_e_recusado():
    with pytest.raises(hls.TranscodeError):
        hls.parse_probe({"streams": [{"codec_type": "audio"}], "format": {"duration": "3"}})


def test_comando_ffmpeg():
    info = hls.parse_probe(PROBE)
    args = hls.ffmpeg_args("/tmp/in.mp4", "/tmp/out", info, hls.ladder_for(info.width, info.height), threads=2)
    joined = " ".join(args)
    assert args[0] == "ffmpeg"
    assert "-hls_segment_type fmp4" in joined
    assert f"-hls_time {hls.SEGMENT_SECONDS}" in joined
    assert "-sc_threshold 0" in joined
    assert "-threads 2" in joined
    assert "-master_pl_name master.m3u8" in joined
    assert "v:0,a:0 v:1,a:1 v:2,a:2 v:3,a:3" in joined
    # keyframe a cada segmento, independente do fps
    assert f"expr:gte(t,n_forced*{hls.SEGMENT_SECONDS})" in joined


def test_comando_ffmpeg_sem_audio():
    info = hls.ProbeInfo(width=640, height=360, duration=3, has_audio=False)
    joined = " ".join(hls.ffmpeg_args("/in", "/out", info, hls.ladder_for(640, 360), threads=2))
    assert "v:0" in joined and "a:0" not in joined
    assert "-c:a" not in joined


def test_comando_ffmpeg_vertical_escala_pela_largura():
    info = hls.ProbeInfo(width=1080, height=1920, duration=3, has_audio=True)
    joined = " ".join(hls.ffmpeg_args("/in", "/out", info, hls.ladder_for(1080, 1920), threads=2))
    assert "scale=360:-2" in joined


@pytest.mark.parametrize(
    "name,expected",
    [("master.m3u8", "application/vnd.apple.mpegurl"), ("seg_00001.m4s", "video/iso.segment"), ("init.mp4", "video/mp4")],
)
def test_tipo_dos_arquivos(name, expected):
    assert hls.content_type_for(name) == expected


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg ausente")
def test_transcode_real_gera_master_com_as_variantes(tmp_path: Path):
    src = tmp_path / "in.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=960x540:rate=25", "-f", "lavfi",
         "-i", "sine=frequency=440", "-t", "3", "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(src)],
        check=True,
    )
    out = tmp_path / "out"

    info = hls.transcode(str(src), str(out), threads=2)

    assert info.height == 540 and info.duration == pytest.approx(3, abs=0.2)
    master = (out / "master.m3u8").read_text()
    assert master.count("#EXT-X-STREAM-INF") == 2
    files = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    for variant in ("v0", "v1"):
        assert f"{variant}/index.m3u8" in files
        assert any(f.startswith(f"{variant}/init") and f.endswith(".mp4") for f in files)
        assert any(f.startswith(f"{variant}/seg_") and f.endswith(".m4s") for f in files)
        assert f'{variant}/index.m3u8' in master


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg ausente")
def test_transcode_de_arquivo_invalido_falha_com_erro_legivel(tmp_path: Path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"nao sou video")
    with pytest.raises(hls.TranscodeError):
        hls.transcode(str(src), str(tmp_path / "out"), threads=2)


def test_transcode_interrompido_mata_o_ffmpeg(tmp_path: Path):
    calls = []

    class FakeProc:
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")
            self.returncode = -15

        def wait(self, timeout=None):
            return self.returncode

    with pytest.raises(hls.TranscodeInterrupted):
        hls.run_ffmpeg(["ffmpeg"], should_stop=lambda: True, popen=lambda *a, **k: FakeProc(), poll_seconds=0)
    assert calls == ["terminate"]
