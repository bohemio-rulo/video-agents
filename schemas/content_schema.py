import re
from pydantic import BaseModel, Field, field_validator
from config.settings import WHATSAPP_SPOKEN


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
            "con emojis, beneficios claros, envíos desde Cochabamba a toda Bolivia, "
            "pago contra entrega / QR y contacto al 72206808."
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
        if len(hashtags) <= 5:
            return value.strip()

        allowed = set(hashtags[:5])
        seen = set()

        def replace_extra(match: re.Match) -> str:
            tag = match.group(0)
            if tag in allowed and tag not in seen:
                seen.add(tag)
                return tag
            return ""

        trimmed = re.sub(r"#\w+", replace_extra, value)
        return re.sub(r"\s{2,}", " ", trimmed).strip()
