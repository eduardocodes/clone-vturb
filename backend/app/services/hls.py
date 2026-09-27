"""Transcode do vídeo original para HLS (fMP4, segmentos de 4s) com escada de qualidades.

Funções puras (escada, leitura do ffprobe, montagem do comando) ficam separadas da
execução (subprocess), para testar a lógica sem ffmpeg.
"""
import json
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

SEGMENT_SECONDS = 4
# (lado menor, kbps de vídeo, kbps de áudio). Lado menor: vídeo vertical 1080x1920 é "1080p".
RUNGS = ((360, 800, 96), (540, 1400, 128), (720, 2500, 128), (1080, 4500, 128))
TOP_RUNG = RUNGS[-1][0]
MIN_NATIVE_KBPS = 400
PROBE_TIMEOUT_SECONDS = 120
ERROR_TAIL_CHARS = 300

CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".m4s": "video/iso.segment",
    ".mp4": "video/mp4",
}


class TranscodeError(Exception):
    """Falha do ffmpeg/ffprobe. A mensagem é curta e sem caminhos internos (vai para o painel)."""


class TranscodeInterrupted(Exception):
    """O worker recebeu sinal de parada no meio do transcode."""


@dataclass(frozen=True)
class Rendition:
    height: int  # lado menor, em pixels
    video_kbps: int
    audio_kbps: int


@dataclass(frozen=True)
class ProbeInfo:
    width: int
    height: int
    duration: float
    has_audio: bool

    @property
    def portrait(self) -> bool:
        return self.height > self.width


def _even(n: int) -> int:
    return n - (n % 2)


def ladder_for(width: int, height: int) -> list[Rendition]:
    """Degraus até o tamanho da fonte (sem upscale). Fonte entre degraus ganha um degrau nativo."""
    short = _even(min(width, height))
    ladder = [Rendition(h, v, a) for h, v, a in RUNGS if h <= short]
    if short < TOP_RUNG and all(r.height != short for r in ladder):
        kbps = max(MIN_NATIVE_KBPS, round(RUNGS[-1][1] * (short / TOP_RUNG) ** 2))
        ladder.append(Rendition(short, kbps, 96 if short < 540 else 128))
    return ladder


def parse_probe(probe: dict) -> ProbeInfo:
    streams = probe.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video or not video.get("width") or not video.get("height"):
        raise TranscodeError("O arquivo não tem uma faixa de vídeo legível.")
    width, height = int(video["width"]), int(video["height"])
    rotation = 0
    for side in video.get("side_data_list") or []:
        if "rotation" in side:
            rotation = int(side["rotation"])
    rotation = rotation or int((video.get("tags") or {}).get("rotate") or 0)
    if abs(rotation) % 180 == 90:
        # Celular grava deitado com metadado de rotação; o ffmpeg gira ao encodar
        width, height = height, width
    duration = float((probe.get("format") or {}).get("duration") or video.get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return ProbeInfo(width=width, height=height, duration=duration, has_audio=has_audio)


def ffmpeg_args(src: str, out_dir: str, info: ProbeInfo, ladder: list[Rendition], threads: int) -> list[str]:
    n = len(ladder)
    splits = "".join(f"[s{i}]" for i in range(n))
    scale = "scale={h}:-2" if info.portrait else "scale=-2:{h}"
    filters = [f"[0:v]split={n}{splits}"] + [f"[s{i}]{scale.format(h=r.height)}[v{i}]" for i, r in enumerate(ladder)]

    args = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error", "-i", src,
            "-filter_complex", ";".join(filters)]
    for i, r in enumerate(ladder):
        args += ["-map", f"[v{i}]", f"-b:v:{i}", f"{r.video_kbps}k",
                 f"-maxrate:v:{i}", f"{round(r.video_kbps * 1.07)}k", f"-bufsize:v:{i}", f"{round(r.video_kbps * 1.5)}k"]
        if info.has_audio:
            args += ["-map", "0:a:0", f"-b:a:{i}", f"{r.audio_kbps}k"]
    args += ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main", "-pix_fmt", "yuv420p",
             "-sc_threshold", "0", "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})"]
    if info.has_audio:
        args += ["-c:a", "aac", "-ac", "2"]
    stream_map = " ".join(f"v:{i},a:{i}" if info.has_audio else f"v:{i}" for i in range(n))
    out = Path(out_dir)
    args += ["-threads", str(threads),
             "-f", "hls", "-hls_time", str(SEGMENT_SECONDS), "-hls_playlist_type", "vod",
             "-hls_segment_type", "fmp4", "-hls_flags", "independent_segments",
             "-hls_fmp4_init_filename", "init.mp4",
             "-hls_segment_filename", str(out / "v%v" / "seg_%05d.m4s"),
             "-master_pl_name", "master.m3u8", "-var_stream_map", stream_map,
             str(out / "v%v" / "index.m3u8")]
    return args


def content_type_for(name: str) -> str:
    return CONTENT_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


def _clean(text: str, *paths: str) -> str:
    for p in paths:
        text = text.replace(p, "<arquivo>")
    return text.strip()[-ERROR_TAIL_CHARS:]


def probe(src: str) -> ProbeInfo:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", src],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise TranscodeError("Tempo esgotado ao ler o arquivo de vídeo.")
    if res.returncode != 0:
        raise TranscodeError("Arquivo de vídeo inválido ou corrompido.")
    return parse_probe(json.loads(res.stdout or "{}"))


def run_ffmpeg(
    args: list[str],
    should_stop: Callable[[], bool] = lambda: False,
    on_tick: Optional[Callable[[], None]] = None,
    popen=subprocess.Popen,
    poll_seconds: float = 1.0,
    redact: tuple[str, ...] = (),
) -> None:
    """Roda o ffmpeg vigiando o sinal de parada; stderr vai para arquivo (pipe cheio trava)."""
    with tempfile.TemporaryFile(mode="w+") as err:
        proc = popen(args, stdout=subprocess.DEVNULL, stderr=err, stdin=subprocess.DEVNULL)
        while proc.poll() is None:
            if should_stop():
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                raise TranscodeInterrupted()
            if on_tick:
                on_tick()
            time.sleep(poll_seconds)
        if proc.returncode != 0:
            err.seek(0)
            detail = _clean(err.read(), *redact)
            raise TranscodeError(f"ffmpeg falhou (código {proc.returncode}): {detail}" if detail else f"ffmpeg falhou (código {proc.returncode}).")


def transcode(
    src: str,
    out_dir: str,
    *,
    threads: int = 2,
    should_stop: Callable[[], bool] = lambda: False,
    on_tick: Optional[Callable[[], None]] = None,
) -> ProbeInfo:
    """Gera `out_dir/master.m3u8` + `out_dir/v<N>/` a partir de `src`. Retorna o ffprobe da fonte."""
    info = probe(src)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ffmpeg_args(src, out_dir, info, ladder_for(info.width, info.height), threads),
        should_stop=should_stop, on_tick=on_tick, redact=(src, out_dir),
    )
    if not (Path(out_dir) / "master.m3u8").exists():
        raise TranscodeError("ffmpeg terminou sem gerar a playlist.")
    return info
