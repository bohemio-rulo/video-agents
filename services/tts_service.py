import asyncio
from pathlib import Path
import edge_tts

from config.settings import TTS_VOICE, TTS_RATE, TTS_PITCH
from services.video_service import get_media_duration


async def _synthesize_async(
    text: str,
    output_path: Path,
    voice: str = TTS_VOICE,
    rate: str = TTS_RATE,
    pitch: str = TTS_PITCH,
) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))


def generate_voiceover(
    text: str,
    output_audio_path: Path,
    voice: str = TTS_VOICE,
    rate: str = TTS_RATE,
    pitch: str = TTS_PITCH,
) -> float:
    """
    Genera el archivo .mp3 a partir del guion limpio y retorna su duración en segundos.
    """
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(
        _synthesize_async(text, output_audio_path, voice=voice, rate=rate, pitch=pitch)
    )
    return get_media_duration(output_audio_path)
