from crewai import Agent, Task, Crew, Process, LLM
from config.settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    USE_LOCAL_OLLAMA,
    WORDS_PER_SECOND,
)
from services.branding import BrandContext, build_brand_context, enforce_spoken_whatsapp
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


def create_copywriter_agent(brand: BrandContext) -> Agent:
    if brand.has_store_name:
        identity = f"Eres el estratega creativo detrás de {brand.store_name}"
        if brand.has_url:
            identity += f" ({brand.store_url})"
        role = f"Copywriter Publicitario Senior de {brand.store_name}"
    else:
        identity = "Eres un estratega creativo de copywriting para ecommerce"
        role = "Copywriter Publicitario Senior de Ecommerce"

    location = ""
    if brand.has_location:
        place = ", ".join(p for p in [brand.city_base, brand.country] if p)
        location = f" La tienda realiza envíos desde {place}."

    if brand.has_whatsapp:
        contact = (
            f" Diriges las ventas al WhatsApp {brand.whatsapp_number}, destacando entrega "
            "inmediata, pago contra entrega y pagos por QR."
        )
    else:
        contact = (
            " Invitas a la acción de forma persuasiva SIN mencionar ningún número de "
            "teléfono ni dato de contacto (no inventes marcas ni números)."
        )

    backstory = (
        f"{identity}, especializado en productos de ecommerce (vehículos eléctricos, "
        "cerraduras inteligentes, herramientas y gadgets tecnológicos). "
        "Tu estilo de locución es moderno, ágil, entretenido y directo al grano "
        f"(estilo voz Lively DJ).{location}{contact}"
    )

    return Agent(
        role=role,
        goal=(
            "Redactar guiones de voz dinámicos sincronizados al segundo y descripciones "
            "altamente persuasivas para TikTok y Meta Reels."
        ),
        backstory=backstory,
        verbose=True,
        allow_delegation=False,
        llm=_build_llm(),
    )


def generate_marketing_copy(
    video_analysis: str,
    duration_seconds: float,
    brand: BrandContext | None = None,
) -> VideoMarketingContent:
    if brand is None:
        brand = build_brand_context()

    target_words = max(12, round(duration_seconds * WORDS_PER_SECOND))
    min_words = max(10, target_words - 4)
    max_words = target_words + 3

    agent = create_copywriter_agent(brand)

    # --- Fragmentos condicionales del GUION DE AUDIO ---
    if brand.has_store_name:
        audio_brand = f"Puedes nombrar la marca '{brand.store_name}' con naturalidad si refuerza el gancho. "
    else:
        audio_brand = "NO menciones ni inventes ningún nombre de tienda, marca, web ni ubicación. "

    if brand.has_whatsapp:
        audio_contact = (
            f"Cierra invitando a escribir al WhatsApp {brand.whatsapp_spoken} "
            f"(escríbelo EXACTAMENTE en pares así: {brand.whatsapp_spoken}, para que se pronuncie claro)."
        )
    else:
        audio_contact = (
            "Cierra con un llamado a la acción claro (invita a consultar disponibilidad o a "
            "pedir el producto) SIN mencionar ningún número de teléfono ni WhatsApp."
        )

    # --- Fragmento condicional de TIKTOK ---
    if brand.has_whatsapp:
        tiktok_contact = f"llamada a la acción al WhatsApp {brand.whatsapp_number}"
    else:
        tiktok_contact = "llamada a la acción breve SIN número de teléfono ni WhatsApp"

    # --- Fragmentos condicionales de REELS ---
    reels_fragments = ["Copy persuasivo con viñetas/emojis destacando los beneficios del producto"]
    if brand.has_location:
        if brand.city_base and brand.country:
            reels_fragments.append(f"envíos en {brand.city_base} y toda {brand.country}")
        elif brand.country:
            reels_fragments.append(f"envíos en todo {brand.country}")
        else:
            reels_fragments.append(f"envíos en {brand.city_base}")
    reels_fragments.append("opciones de pago contra entrega o QR")
    if brand.has_url:
        reels_fragments.append(f"web {brand.store_url}")
    if brand.has_whatsapp:
        reels_fragments.append(f"contacto directo al WhatsApp {brand.whatsapp_number}")
    else:
        reels_fragments.append("invitación a consultar disponibilidad (sin número de teléfono ni WhatsApp)")
    reels_instruction = "; ".join(reels_fragments)

    if not brand.has_store_name and not brand.has_whatsapp:
        global_rule = (
            "\n\nREGLA GLOBAL: No se proporcionó marca ni WhatsApp. NO inventes nombres de "
            "tienda, webs, ubicaciones ni números de contacto en ninguno de los tres textos."
        )
    else:
        global_rule = ""

    task = Task(
        description=(
            "Analiza el siguiente reporte visual de un video promocional que dura exactamente "
            f"{duration_seconds:.1f} segundos:\n\n"
            f"--- REPORTE VISUAL ---\n{video_analysis}\n----------------------\n\n"
            "Genera los tres textos requeridos cumpliendo estas reglas estrictas:\n"
            f"1. GUION DE AUDIO: Debe tener entre {min_words} y {max_words} palabras exactas "
            f"para calzar en {duration_seconds:.1f} segundos. Arranca con un gancho potente y "
            f"destaca los beneficios vistos en pantalla. {audio_brand}{audio_contact} "
            "PROHIBIDO usar emojis, hashtags o indicaciones escénicas entre corchetes o paréntesis.\n"
            f"2. DESCRIPCIÓN TIKTOK: Gancho breve con emojis, {tiktok_contact} y MÁXIMO 5 "
            "hashtags relevantes al final.\n"
            f"3. DESCRIPCIÓN REELS (Meta Business Suite): {reels_instruction}. "
            "Cierra SIEMPRE con un bloque de 3 a 8 hashtags relevantes al final para maximizar "
            "el alcance en Instagram y Facebook Reels."
            f"{global_rule}"
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
    content = result.pydantic

    # Red de seguridad: normaliza el WhatsApp a pares en el guion locutado.
    if brand.has_whatsapp:
        content.guion_audio = enforce_spoken_whatsapp(
            content.guion_audio, brand.whatsapp_number
        )

    return content
