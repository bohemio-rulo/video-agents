from crewai import Agent, Task, Crew, Process, LLM
from config.settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    USE_LOCAL_OLLAMA,
    STORE_NAME,
    STORE_URL,
    WHATSAPP_NUMBER,
    WHATSAPP_SPOKEN,
    CITY_BASE,
    COUNTRY,
    WORDS_PER_SECOND,
)
from schemas.content_schema import VideoMarketingContent


def _build_llm() -> LLM:
    if USE_LOCAL_OLLAMA:
        return LLM(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.7,
        )
    return LLM(
        model=f"gemini/{GEMINI_MODEL}",
        api_key=GEMINI_API_KEY,
        temperature=0.7,
    )


def create_copywriter_agent() -> Agent:
    return Agent(
        role=f"Copywriter Publicitario Senior de {STORE_NAME}",
        goal=(
            "Redactar guiones de voz dinámicos sincronizados al segundo y descripciones "
            "altamente persuasivas para TikTok y Meta Reels en el mercado boliviano."
        ),
        backstory=(
            f"Eres el estratega creativo detrás de {STORE_NAME} ({STORE_URL}), tienda ubicada "
            f"en {CITY_BASE}, {COUNTRY}, especializada en vehículos eléctricos (trimotos, "
            "bicicletas y scooters eléctricos), cerraduras inteligentes y gadgets tecnológicos. "
            "Tu estilo de locución es moderno, ágil, entretenido y directo al grano (estilo voz Lively DJ). "
            f"Siempre diriges las ventas al WhatsApp {WHATSAPP_NUMBER} destacando entrega inmediata "
            f"en {CITY_BASE}, envíos a toda {COUNTRY}, pago contra entrega y pagos por QR."
        ),
        verbose=True,
        allow_delegation=False,
        llm=_build_llm(),
    )


def generate_marketing_copy(
    video_analysis: str, duration_seconds: float
) -> VideoMarketingContent:
    target_words = max(12, round(duration_seconds * WORDS_PER_SECOND))
    min_words = max(10, target_words - 4)
    max_words = target_words + 3

    agent = create_copywriter_agent()

    task = Task(
        description=(
            f"Analiza el siguiente reporte visual de un video promocional de {STORE_NAME} "
            f"que dura exactamente {duration_seconds:.1f} segundos:\n\n"
            f"--- REPORTE VISUAL ---\n{video_analysis}\n----------------------\n\n"
            "Genera los tres textos requeridos cumpliendo estas reglas estrictas:\n"
            f"1. GUION DE AUDIO: Debe tener entre {min_words} y {max_words} palabras exactas "
            f"para calzar en {duration_seconds:.1f} segundos. "
            "Arranca con un gancho potente, destaca los beneficios vistos en pantalla y cierra "
            f"invitando a escribir al WhatsApp {WHATSAPP_SPOKEN} (escríbelo exactamente así en pares: "
            f"{WHATSAPP_SPOKEN} para que se pronuncie claro). "
            "PROHIBIDO usar emojis, hashtags o indicaciones escénicas.\n"
            "2. DESCRIPCIÓN TIKTOK: Gancho breve con emojis, llamado a la acción al "
            f"WhatsApp {WHATSAPP_NUMBER} y MÁXIMO 5 hashtags relevantes al final.\n"
            "3. DESCRIPCIÓN REELS (Meta Business Suite): Copy persuasivo con viñetas/emojis, "
            f"detallando envíos en {CITY_BASE} y toda {COUNTRY}, pago contra entrega o QR, "
            f"web {STORE_URL} y contacto directo al {WHATSAPP_NUMBER}. "
            "Cierra SIEMPRE con un bloque de 3 a 8 hashtags relevantes al final (después "
            "del texto persuasivo) para maximizar el alcance en Instagram y Facebook Reels."
        ),
        expected_output=(
            "Objeto JSON válido ajustado al esquema VideoMarketingContent con "
            "guion_audio, descripcion_tiktok y descripcion_reels."
        ),
        agent=agent,
        output_pydantic=VideoMarketingContent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    return result.pydantic
