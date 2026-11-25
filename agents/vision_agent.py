import subprocess
import tempfile
import time
from pathlib import Path
from google import genai
from google.genai import types
from google.genai.errors import APIError

from config.settings import GEMINI_API_KEY, STORE_NAME

EXCLUDED_KEYWORDS = ("embedding", "imagen", "veo", "tts", "lyria", "aqa", "robotics")


def _discover_models(client: genai.Client) -> list[str]:
    """
    Prioriza gemini-3.8-flash y descubre dinámicamente otros modelos Gemini
    activos en la cuenta para evitar errores 404 en los respaldos.
    """
    models = ["gemini-3.8-flash"]
    try:
        for m in client.models.list():
            name = (m.name or "").replace("models/", "")
            if not name.startswith("gemini-"):
                continue
            if any(bad in name.lower() for bad in EXCLUDED_KEYWORDS):
                continue
            actions = getattr(m, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            if name not in models:
                models.append(name)
    except Exception:
        pass
    return models


def _create_lightweight_proxy(source_path: Path) -> Path:
    """
    Crea una copia temporal ligera (480p, 4 fps, sin audio) para acelerar
    la subida y el análisis en Gemini sin alterar el video HD original.
    """
    tmp_file = tempfile.NamedTemporaryFile(suffix="_proxy.mp4", delete=False)
    proxy_path = Path(tmp_file.name)
    tmp_file.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vf",
        "scale=-2:480,fps=4",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "30",
        "-an",
        str(proxy_path),
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return proxy_path


def analyze_video_content(video_path: Path) -> str:
    """
    Comprime un proxy ligero del .mp4, lo sube a Gemini File API con reintentos
    y descubrimiento automático de modelos disponibles, extrae el reporte visual
    y limpia los temporales.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "pega_aqui_tu_api_key_de_gemini":
        raise ValueError("Falta configurar GEMINI_API_KEY en el archivo .env")

    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de video: {path}")

    client = genai.Client(api_key=GEMINI_API_KEY)
    uploaded_file = None
    proxy_path = None
    t_start = time.perf_counter()

    analysis_prompt = (
        f"Eres un analista de producto audiovisual para la tienda '{STORE_NAME}' en Bolivia "
        "(especializada en vehículos eléctricos como trimotos/bicicletas/scooters, "
        "cerraduras inteligentes, herramientas eléctricas y gadgets tecnológicos).\n\n"
        "Observa este video promocional de principio a fin y entrega un reporte factual "
        "y detallado con estas 4 secciones exactas:\n"
        "1. PRODUCTO Y MODELO: Qué artículo se muestra, color, diseño y marca/modelo si se distingue.\n"
        "2. ACCIONES EN PANTALLA (CRONOLOGÍA): Qué hace la persona o qué funciones se demuestran "
        "paso a paso (ej. desempaquetado, encendido, pruebas de uso, luces, pantalla, seguridad).\n"
        "3. ACCESORIOS Y DETALLES VISIBLES: Qué piezas vienen incluidas en la caja o se ven en el entorno, "
        "y cualquier texto, número o especificación técnica visible en el producto.\n"
        "4. GANCHO VISUAL PRINCIPAL: Cuál es la escena o demostración más llamativa del video "
        "para captar la atención en los primeros 3 segundos.\n\n"
        "Sé objetivo y describe únicamente lo que realmente se ve en el video."
    )

    try:
        t0 = time.perf_counter()
        orig_mb = path.stat().st_size / (1024 * 1024)
        proxy_path = _create_lightweight_proxy(path)
        proxy_mb = proxy_path.stat().st_size / (1024 * 1024)
        print(
            f"[1/3] Proxy generado en {time.perf_counter() - t0:.1f}s "
            f"({orig_mb:.1f} MB -> {proxy_mb:.2f} MB)"
        )

        t0 = time.perf_counter()
        uploaded_file = client.files.upload(file=str(proxy_path))
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1.5)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            raise RuntimeError(f"Gemini falló al procesar el video '{path.name}'.")
        print(f"[2/3] Subida y procesamiento listos en {time.perf_counter() - t0:.1f}s")

        t0 = time.perf_counter()
        candidate_models = _discover_models(client)
        last_error = None

        for model_name in candidate_models:
            max_attempts = 4 if model_name == "gemini-3.8-flash" else 2
            for attempt in range(1, max_attempts + 1):
                try:
                    print(f"[3/3] Analizando con {model_name} (intento {attempt}/{max_attempts})...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file, analysis_prompt],
                        config=types.GenerateContentConfig(temperature=0.3),
                    )
                    print(
                        f"Análisis completado en {time.perf_counter() - t0:.1f}s "
                        f"(Total: {time.perf_counter() - t_start:.1f}s)"
                    )
                    return response.text.strip()

                except APIError as err:
                    last_error = err
                    if err.code in (400, 404):
                        break
                    if err.code in (429, 503, 504):
                        wait_seconds = attempt * 4
                        print(f"Servidor ocupado ({err.code}). Reintentando en {wait_seconds}s...")
                        time.sleep(wait_seconds)
                        continue
                    raise

        raise RuntimeError(
            f"No se pudo analizar el video tras agotar modelos ({candidate_models}). Último error: {last_error}"
        )

    finally:
        if proxy_path and proxy_path.exists():
            proxy_path.unlink(missing_ok=True)
        if uploaded_file is not None:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as cleanup_err:
                print(f"Advertencia: no se pudo eliminar el temporal remoto: {cleanup_err}")
