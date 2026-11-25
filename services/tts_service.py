import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import edge_tts
import httpx

from config.settings import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_VOICE_ID,
    FISH_API_KEY,
    FISH_VOICE_ID,
    TTS_PITCH,
    TTS_PROVIDER,
    TTS_RATE,
    TTS_VOICE,
)
from services.video_service import get_media_duration


class TTSProvider(ABC):
    """Interfaz base para proveedores de síntesis de voz (Strategy)."""

    name: str = "base"

    @abstractmethod
    def synthesize(self, text: str, output_audio_path: Path) -> None:
        """Genera un archivo de audio a partir de texto."""


class EdgeTTSProvider(TTSProvider):
    """Proveedor gratuito por defecto basado en Microsoft Edge TTS."""

    name = "edge"

    def __init__(
        self,
        voice: str = TTS_VOICE,
        rate: str = TTS_RATE,
        pitch: str = TTS_PITCH,
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def _synthesize_async(self, text: str, output_audio_path: Path) -> None:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        await communicate.save(str(output_audio_path))

    def synthesize(self, text: str, output_audio_path: Path) -> None:
        try:
            asyncio.get_running_loop()
            in_running_loop = True
        except RuntimeError:
            in_running_loop = False

        if not in_running_loop:
            asyncio.run(self._synthesize_async(text, output_audio_path))
            return

        # Evita choque si se invoca desde un contexto con event loop activo
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                lambda: asyncio.run(self._synthesize_async(text, output_audio_path))
            )
            future.result()


class ElevenLabsTTSProvider(TTSProvider):
    """Adaptador para voz clonada (ej. Lively DJ) vía ElevenLabs REST API."""

    name = "elevenlabs"

    def __init__(
        self,
        api_key: str = ELEVENLABS_API_KEY,
        voice_id: str = ELEVENLABS_VOICE_ID,
        model_id: str = ELEVENLABS_MODEL_ID,
    ) -> None:
        self.api_key = api_key.strip()
        self.voice_id = voice_id.strip()
        self.model_id = model_id.strip() or "eleven_multilingual_v2"

    def synthesize(self, text: str, output_audio_path: Path) -> None:
        if not self.api_key:
            raise ValueError(
                "Falta configurar ELEVENLABS_API_KEY en .env para usar TTS_PROVIDER=elevenlabs."
            )
        if not self.voice_id:
            raise ValueError(
                "Falta configurar ELEVENLABS_VOICE_ID en .env (ID de voz clonada, ej. Lively DJ)."
            )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                headers=headers,
                json=payload,
                params={"output_format": "mp3_44100_128"},
            )
            response.raise_for_status()
            output_audio_path.write_bytes(response.content)


class FishTTSProvider(TTSProvider):
    """Adaptador opcional para Fish Audio API."""

    name = "fish"

    def __init__(
        self,
        api_key: str = FISH_API_KEY,
        voice_id: str = FISH_VOICE_ID,
    ) -> None:
        self.api_key = api_key.strip()
        self.voice_id = voice_id.strip()

    def synthesize(self, text: str, output_audio_path: Path) -> None:
        if not self.api_key or not self.voice_id:
            raise ValueError(
                "Faltan FISH_API_KEY y/o FISH_VOICE_ID en .env para usar TTS_PROVIDER=fish."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "reference_id": self.voice_id,
            "format": "mp3",
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.fish.audio/v1/tts",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            output_audio_path.write_bytes(response.content)


def get_tts_provider(
    provider_name: str | None = None,
    voice: str = TTS_VOICE,
    rate: str = TTS_RATE,
    pitch: str = TTS_PITCH,
) -> TTSProvider:
    """Devuelve la instancia del proveedor TTS configurado."""
    selected = (provider_name or TTS_PROVIDER or "edge").strip().lower()

    if selected == "edge":
        return EdgeTTSProvider(voice=voice, rate=rate, pitch=pitch)
    if selected == "elevenlabs":
        return ElevenLabsTTSProvider()
    if selected == "fish":
        return FishTTSProvider()

    raise ValueError(
        f"TTS_PROVIDER no soportado: '{selected}'. Opciones válidas: edge, elevenlabs, fish."
    )


def generate_voiceover(
    text: str,
    output_audio_path: Path,
    voice: str = TTS_VOICE,
    rate: str = TTS_RATE,
    pitch: str = TTS_PITCH,
    provider: str | None = None,
) -> float:
    """
    Genera el archivo .mp3 a partir del guion limpio usando el proveedor TTS
    configurado y retorna su duración en segundos.
    """
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    tts_provider = get_tts_provider(
        provider_name=provider,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )
    tts_provider.synthesize(text=text, output_audio_path=output_audio_path)
    return get_media_duration(output_audio_path)
