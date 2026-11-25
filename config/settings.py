import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "media" / "input"
OUTPUT_DIR = BASE_DIR / "media" / "output"

# Configuración de modelos (LLM)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ollama/llama3.1:8b")
USE_LOCAL_OLLAMA = os.getenv("USE_LOCAL_OLLAMA", "true").lower() == "true"

# Reglas de negocio - Rulo Ecommerce
STORE_NAME = "Rulo Ecommerce"
STORE_URL = "rulo-ecommerce.com"
WHATSAPP_NUMBER = "72206808"       # Para descripciones escritas (TikTok / Reels)
WHATSAPP_SPOKEN = "72 20 68 08"    # Para locución en pares (TTS)
CITY_BASE = "Cochabamba"
COUNTRY = "Bolivia"

# Seguridad de interfaz web móvil
STUDIO_PIN = os.getenv("STUDIO_PIN", "2026")

# Configuración de voz (TTS) estilo comercial / Lively DJ
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").strip().lower()
TTS_VOICE = os.getenv("TTS_VOICE", "es-US-AlonsoNeural")
TTS_RATE = os.getenv("TTS_RATE", "+15%")
TTS_PITCH = os.getenv("TTS_PITCH", "+6Hz")
WORDS_PER_SECOND = 2.7             # Palabras por segundo calibradas a +15%

# Credenciales opcionales para clonación de voz (ElevenLabs / Fish Audio)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "")

# Mezcla de audio original de fondo
KEEP_ORIGINAL_AUDIO = True         # Mantiene la música/sonido original del video
ORIGINAL_AUDIO_VOLUME = 0.18       # Volumen de fondo (0.10 = suave, 0.25 = más presente)
