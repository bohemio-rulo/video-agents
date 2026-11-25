import subprocess
from pathlib import Path
import ffmpeg

from config.settings import KEEP_ORIGINAL_AUDIO, ORIGINAL_AUDIO_VOLUME


def get_media_duration(file_path: Path) -> float:
    """
    Obtiene la duración exacta en segundos de un archivo de audio o video usando ffprobe.
    """
    probe = ffmpeg.probe(str(file_path))
    return float(probe["format"]["duration"])


def has_audio_stream(file_path: Path) -> bool:
    """
    Verifica si el video original contiene al menos una pista de audio.
    """
    probe = ffmpeg.probe(str(file_path), select_streams="a")
    return len(probe.get("streams", [])) > 0


def merge_video_with_voiceover(
    video_path: Path,
    audio_path: Path,
    output_video_path: Path,
    keep_original_audio: bool = KEEP_ORIGINAL_AUDIO,
    original_volume: float = ORIGINAL_AUDIO_VOLUME,
) -> Path:
    """
    Ensambla el video HD original con la locución TTS, mezclando el audio
    original de fondo a bajo volumen sin atenuar la voz en off.
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    video_duration = get_media_duration(video_path)
    audio_duration = get_media_duration(audio_path)
    extra_seconds = max(0.0, (audio_duration - video_duration) + 0.25)
    mix_bg_audio = keep_original_audio and has_audio_stream(video_path)

    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path)]

    # Caso 1: Video sin audio de fondo y voz dentro de la duración original
    if extra_seconds == 0.0 and not mix_bg_audio:
        cmd.extend([
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_video_path),
        ])
    else:
        filter_complex = []

        if extra_seconds > 0.0:
            filter_complex.append(
                f"[0:v]tpad=stop_mode=clone:stop_duration={extra_seconds:.2f}[vout]"
            )
            video_map = "[vout]"
            video_codec = ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p"]
        else:
            video_map = "0:v:0"
            video_codec = ["-c:v", "copy"]

        if mix_bg_audio:
            # normalize=0 mantiene la voz en off al 100% mientras baja la música de fondo
            filter_complex.append(
                f"[0:a]volume={original_volume}[bg];"
                f"[1:a]volume=1.0[fg];"
                f"[bg][fg]amix=inputs=2:duration=longest:normalize=0[aout]"
            )
            audio_map = "[aout]"
        else:
            audio_map = "1:a:0"

        if filter_complex:
            cmd.extend(["-filter_complex", ";".join(filter_complex)])

        cmd.extend([
            "-map", video_map,
            "-map", audio_map,
            *video_codec,
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_video_path),
        ])

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_video_path
