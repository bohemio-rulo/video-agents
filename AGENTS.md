# AGENTS.md — Rulo Ecommerce Video Studio (`rulo-video-agents`)

## 1. Objetivo del Proyecto
Pipeline automatizado en Python para **Rulo Ecommerce** (`rulo-ecommerce.com`, Cochabamba, Bolivia) que recibe videos crudos `.mp4` de productos (vehículos eléctricos, cerraduras inteligentes, herramientas y gadgets), analiza su contenido visual, redacta el guion comercial y las descripciones para redes sociales, genera la voz en off y ensambla el `.mp4` final mezclado con el audio de fondo original.

El sistema debe ejecutarse como un **microservicio web móvil (FastAPI + Docker)** en un servidor **Ubuntu Server** (que ya aloja WooCommerce en Docker) para operarlo desde el celular, manteniendo compatibilidad con ejecución CLI en macOS (Apple Silicon M3).

---

## 2. Reglas de Negocio Inmutables (Rulo Ecommerce)
1. **Contacto oficial:** WhatsApp `72206808`.
   - En **descripciones escritas** (TikTok / Reels): escribir junto `72206808`.
   - En **guion de audio (`guion_audio`)**: escribir separado en pares `72 20 68 08` para que el motor TTS lo pronuncie con claridad (validado por regex en `schemas/content_schema.py`).
2. **Guion de audio (`guion_audio`):**
   - **CERO emojis**, **CERO hashtags** y **CERO acotaciones** entre corchetes o paréntesis.
   - Escribir números como dígitos sin comas (ej. `1000`, `2000`) y designar potencia eléctrica siempre como `Watts`.
   - Calcular extensión estricta según la duración real del `.mp4` (`WORDS_PER_SECOND = 2.7`) para evitar cortes o silencios largos.
3. **Descripción TikTok (`descripcion_tiktok`):**
   - Gancho corto con emojis, llamado a la acción al WhatsApp `72206808` y **estrictamente máximo 5 hashtags** al final (validado determinísticamente en `schemas/content_schema.py`).
4. **Descripción Reels (`descripcion_reels` — Meta Business Suite):**
   - Texto persuasivo con viñetas/emojis, destacando envíos en Cochabamba y toda Bolivia, pago contra entrega o QR, sitio `rulo-ecommerce.com` y WhatsApp `72206808`.

---

## 3. Arquitectura y Estado Actual del Código

### Archivos ya implementados y probados en macOS:
- `config/settings.py`: Constantes de negocio, rutas (`INPUT_DIR`, `OUTPUT_DIR`), configuración LLM (`USE_LOCAL_OLLAMA`), voz (`TTS_VOICE = "es-US-AlonsoNeural"`, `TTS_RATE = "+15%"`, `TTS_PITCH = "+6Hz"`) y mezcla de audio (`KEEP_ORIGINAL_AUDIO = True`, `ORIGINAL_AUDIO_VOLUME = 0.18`).
- `schemas/content_schema.py`: Esquema Pydantic `VideoMarketingContent` con sanitización de emojis/hashtags en `guion_audio`, formateo `72 20 68 08` y recorte a 5 hashtags en `descripcion_tiktok`.
- `agents/vision_agent.py`: Comprime un proxy ligero con FFmpeg (`480p`, `4 fps`, sin audio) para acelerar subida, lo sube a Gemini File API (`google-genai`), descubre dinámicamente modelos activos priorizando `gemini-3.8-flash` con reintentos/backoff ante errores `503` y limpia archivos temporales.
- `agents/copy_agent.py`: Agente CrewAI que usa Ollama (`ollama/llama3.1:8b`) en desarrollo local (`USE_LOCAL_OLLAMA=true`) o `gemini/gemini-3.8-flash` en servidor (`USE_LOCAL_OLLAMA=false`).
- `services/tts_service.py`: Síntesis de voz con `edge-tts` y cálculo de duración con `ffprobe`.
- `services/video_service.py`: Ensamblado con FFmpeg; usa `tpad=stop_mode=clone` si la voz supera la duración del video y `amix=...:normalize=0` para mezclar el audio original al 18% sin atenuar la voz en off.
- `main.py`: Script CLI funcional para procesar videos en `media/input/`.

### Archivos de fase web + Docker (verificar/completar):
- `services/pipeline_service.py`: Orquestador reutilizable que ejecuta todo el flujo de un video y guarda `video_final.mp4`, `copys.txt` y `result.json` en `media/output/<slug>/`.
- `app.py`: API FastAPI con cola en segundo plano (`BackgroundTasks`), endpoints `/`, `/api/process`, `/api/jobs/{job_id}`, `/api/history`, `DELETE /api/cleanup` y validación por `STUDIO_PIN`.
- `templates/index.html`: Interfaz web responsive móvil para subir hasta 3 videos desde el celular, reproducir/descargar el `.mp4` final y copiar textos de TikTok y Reels con un toque.
- `Dockerfile` y `docker-compose.yml`: Contenedor Python 3.12 + FFmpeg expuesto en puerto `8085` con `USE_LOCAL_OLLAMA=false`.

---

## 4. Restricciones del Servidor de Producción (Ubuntu Server)
- El servidor Ubuntu corre otros contenedores en producción (WooCommerce, Nginx/Cloudflare).
- **NO ejecutar Ollama en el servidor:** mantener `USE_LOCAL_OLLAMA=false` en Docker para no consumir RAM ni CPU innecesarios.
- **Puerto asignado:** `8085` (evitar colisión con `80`, `443`, `8080`).

---

## 5. Tareas Pendientes para Claude Code
1. **Verificar/Crear capa web y Docker:** Comprobar si `services/pipeline_service.py`, `app.py`, `templates/index.html`, `Dockerfile` y `docker-compose.yml` ya existen en el repo; si faltan o están incompletos, implementarlos siguiendo las especificaciones de la sección 3.
2. **Refactorizar `main.py`:** Hacer que `main.py` importe y llame a `process_single_video` desde `services/pipeline_service.py` para eliminar código duplicado entre CLI y FastAPI.
3. **Validación local:** Levantar `uvicorn app:app --port 8085`, probar los endpoints `/api/history` y `/` y verificar que no haya errores de importación ni sintaxis.
4. **Preparar arquitectura extensible de TTS (Lively DJ):** Refactorizar `services/tts_service.py` usando un patrón Strategy/Provider (`TTS_PROVIDER` en `settings.py`: `"edge"` por defecto, `"elevenlabs"` o `"fish"` opcionales) para poder conectar en el futuro un `voice_id` clonado de *Lively DJ* solo agregando API key en `.env` sin tocar el resto del pipeline.
5. **Documentar despliegue:** Crear `README.md` breve con los comandos exactos para levantar el contenedor en Ubuntu Server y exponerlo detrás de Cloudflare Tunnel (`studio.rulo-ecommerce.com`).
