# Rulo Ecommerce — Video Studio (`rulo-video-agents`)

Microservicio que recibe videos crudos `.mp4` de productos, analiza su contenido
con Gemini Vision, redacta guion y copys (TikTok / Reels), genera la voz en off y
ensambla el `.mp4` final mezclado con el audio de fondo original.

Funciona de dos formas con el **mismo pipeline** (`services/pipeline_service.py`):

- **CLI** (macOS / desarrollo): `python main.py`
- **Web móvil** (Ubuntu Server / producción): FastAPI en el puerto `8085`

---

## 1. Requisitos

- Python 3.12 y `ffmpeg` (incluido en la imagen Docker).
- `GEMINI_API_KEY` válida (agente de visión).
- En local opcional: Ollama con `llama3.1:8b` (`USE_LOCAL_OLLAMA=true`).

---

## 2. Configuración (`.env`)

Copia `.env.example` a `.env` y completa los valores:

```bash
cp .env.example .env
```

| Variable | Producción (Ubuntu) | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | *(tu key)* | Clave de Google Gemini para el agente de visión. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Modelo de visión/copy en servidor. |
| `USE_LOCAL_OLLAMA` | `false` | **Siempre `false` en el servidor** (no consume RAM/CPU). |
| `STUDIO_PIN` | *(PIN privado)* | PIN de acceso a la interfaz web. |
| `TTS_PROVIDER` | `edge` | Proveedor de voz: `edge` (gratis), `elevenlabs` o `fish`. |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | *(opcional)* | Para la voz clonada *Lively DJ* sin tocar el código. |

---

## 3. Despliegue en Ubuntu Server (Docker)

El contenedor expone el puerto **`8085`** (sin colisión con `80`, `443`, `8080`)
y fuerza `USE_LOCAL_OLLAMA=false`.

```bash
# 1. Clonar y entrar al proyecto
git clone <repo-url> rulo-video-agents
cd rulo-video-agents

# 2. Crear el .env de producción (ver sección 2)
cp .env.example .env
nano .env   # pega GEMINI_API_KEY, STUDIO_PIN y USE_LOCAL_OLLAMA=false

# 3. Construir y levantar en segundo plano
docker compose up -d --build

# 4. Ver logs / estado
docker compose logs -f
docker compose ps
```

Los resultados persisten en el host mediante el volumen `./media:/app/media`
(`media/output/<slug>/` con `video_final.mp4`, `voiceover.mp3`, `copys.txt` y `result.json`).

### Actualizar a una nueva versión

```bash
git pull
docker compose up -d --build
```

### Detener

```bash
docker compose down
```

---

## 4. Exponer detrás de Cloudflare Tunnel

Publica la interfaz en `studio.rulo-ecommerce.com` sin abrir puertos en el firewall.

```bash
# Instalar cloudflared (una sola vez)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Autenticar y crear el túnel
cloudflared tunnel login
cloudflared tunnel create rulo-studio
```

Crea `~/.cloudflared/config.yml`:

```yaml
tunnel: rulo-studio
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: studio.rulo-ecommerce.com
    service: http://localhost:8085
  - service: http_status:404
```

Enruta el DNS y arranca el túnel como servicio:

```bash
cloudflared tunnel route dns rulo-studio studio.rulo-ecommerce.com
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Abre `https://studio.rulo-ecommerce.com` desde el celular, ingresa el `STUDIO_PIN`,
sube hasta 3 videos y descarga el `.mp4` final con los copys listos.

---

## 5. Uso en macOS local (desarrollo)

```bash
# Entorno
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# a) CLI: procesa todos los videos de media/input/
python main.py
python main.py --context "Precio 4500 Bs, batería 60V" --mute-original --archive

# b) Web local (misma UI que producción)
uvicorn app:app --port 8085
# -> http://localhost:8085
```

En local puedes usar `USE_LOCAL_OLLAMA=true` para redactar los copys con Ollama
(`llama3.1:8b`) sin gastar cuota de Gemini.

---

## 6. Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web móvil. |
| `POST` | `/api/process` | Sube hasta 3 videos y encola el procesamiento. |
| `GET` | `/api/jobs/{job_id}` | Estado y progreso del lote en curso. |
| `GET` | `/api/history` | Videos ya procesados (lee `result.json`). |
| `GET` | `/api/media/{slug}/{archivo}` | Reproduce/descarga `video_final.mp4`. |
| `DELETE` | `/api/cleanup` | Limpia el historial (o `?slug=` puntual). |

Todos los endpoints `/api/*` (excepto `/api/health`) exigen el `STUDIO_PIN`
vía header `X-Studio-Pin` o query `?pin=`.

---

## 7. Cambiar la voz a *Lively DJ* (ElevenLabs)

Sin tocar el pipeline, solo edita `.env` y reinicia el contenedor:

```env
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=tu_api_key
ELEVENLABS_VOICE_ID=id_de_la_voz_clonada
```

```bash
docker compose up -d
```
