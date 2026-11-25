import re
from pydantic import BaseModel, Field, field_validator
from config.settings import WHATSAPP_SPOKEN

TIKTOK_MAX_HASHTAGS = 5
REELS_MAX_HASHTAGS = 8


class VideoMarketingContent(BaseModel):
    guion_audio: str = Field(
        ...,
        description=(
            "Guion locutado para el video. Tono moderno, enérgico y persuasivo. "
            "CERO emojis, CERO hashtags y el número escrito en pares: 72 20 68 08."
        ),
    )
    descripcion_tiktok: str = Field(
        ...,
        description=(
            "Descripción corta y viral para TikTok con emojis, llamada a la acción "
            "al WhatsApp 72206808 y estrictamente máximo 5 hashtags al final."
        ),
    )
    descripcion_reels: str = Field(
        ...,
        description=(
            "Descripción completa para Meta Business Suite Reels (Facebook/Instagram) "
            "con viñetas/emojis, beneficios claros, envíos desde Cochabamba a toda Bolivia, "
            "pago contra entrega / QR, web rulo-ecommerce.com y contacto al 72206808. "
            "Cierra con un bloque de 3 a 8 hashtags relevantes al final para maximizar alcance."
        ),
    )

    @field_validator("guion_audio")
    @classmethod
    def sanitize_audio_script(cls, value: str) -> str:
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002600-\U000027BF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u200d\ufe0f"
            "]+",
            flags=re.UNICODE,
        )
        cleaned = emoji_pattern.sub("", value)
        cleaned = re.sub(r"#\S+", "", cleaned)
        cleaned = re.sub(r"\[.*?\]|\(.*?\)", "", cleaned)

        # Garantiza que el número siempre quede separado en pares para el TTS
        cleaned = re.sub(r"722[\s\-]?06[\s\-]?80[\s\-]?8", WHATSAPP_SPOKEN, cleaned)
        return " ".join(cleaned.split()).strip()

    @field_validator("descripcion_tiktok")
    @classmethod
    def enforce_max_five_hashtags(cls, value: str) -> str:
        hashtags = re.findall(r"#\w+", value)
        if len(hashtags) <= TIKTOK_MAX_HASHTAGS:
            return value.strip()

        allowed = set(hashtags[:TIKTOK_MAX_HASHTAGS])
        seen = set()

        def replace_extra(match: re.Match) -> str:
            tag = match.group(0)
            if tag in allowed and tag not in seen:
                seen.add(tag)
                return tag
            return ""

        trimmed = re.sub(r"#\w+", replace_extra, value)
        return re.sub(r"\s{2,}", " ", trimmed).strip()

    @field_validator("descripcion_reels")
    @classmethod
    def enforce_reels_hashtag_limit(cls, value: str) -> str:
        """
        Recorta determinísticamente la descripción de Reels a un máximo de
        hashtags (8) preservando viñetas, saltos de línea y emojis del copy.
        No fuerza un mínimo: deja pasar de 0 a 8 hashtags tal como los redacte el LLM.
        """
        hashtags = re.findall(r"#\w+", value)
        if len(hashtags) <= REELS_MAX_HASHTAGS:
            return value.strip()

        allowed: list[str] = []
        for tag in hashtags:
            if tag not in allowed:
                allowed.append(tag)
            if len(allowed) >= REELS_MAX_HASHTAGS:
                break
        allowed_set = set(allowed)
        seen: set[str] = set()

        def replace_extra(match: re.Match) -> str:
            tag = match.group(0)
            if tag in allowed_set and tag not in seen:
                seen.add(tag)
                return tag
            return ""

        trimmed = re.sub(r"#\w+", replace_extra, value)
        trimmed = re.sub(r"[ \t]{2,}", " ", trimmed)
        trimmed = re.sub(r"[ \t]+\n", "\n", trimmed)
        return trimmed.strip()
