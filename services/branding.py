import re
from dataclasses import dataclass

from config.settings import (
    CITY_BASE,
    COUNTRY,
    STORE_NAME,
    STORE_URL,
    WHATSAPP_NUMBER,
)


def format_whatsapp_spoken(number: str) -> str:
    """
    Convierte un número en su forma hablada por pares para el TTS.
    Ej: '72206808' -> '72 20 68 08'. Devuelve '' si no hay dígitos.
    """
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return ""
    return " ".join(digits[i : i + 2] for i in range(0, len(digits), 2))


def enforce_spoken_whatsapp(text: str, number: str) -> str:
    """
    Red de seguridad: reemplaza cualquier aparición del número (compacto o con
    separadores) por su forma hablada en pares dentro del guion de audio.
    """
    digits = re.sub(r"\D", "", number or "")
    if len(digits) < 2 or not text:
        return text
    spoken = format_whatsapp_spoken(number)
    pattern = r"[\s\-\.]?".join(re.escape(d) for d in digits)
    return re.sub(pattern, spoken, text)


@dataclass
class BrandContext:
    """
    Datos de marca por video. Campos vacíos => no se mencionan en el copy.
    """

    store_name: str = ""
    store_url: str = ""
    whatsapp_number: str = ""
    whatsapp_spoken: str = ""
    city_base: str = ""
    country: str = ""

    @property
    def has_store_name(self) -> bool:
        return bool(self.store_name.strip())

    @property
    def has_url(self) -> bool:
        return bool(self.store_url.strip())

    @property
    def has_whatsapp(self) -> bool:
        return bool(self.whatsapp_number.strip())

    @property
    def has_location(self) -> bool:
        return bool(self.city_base.strip() or self.country.strip())


def build_brand_context(
    store_name: str | None = None,
    whatsapp_number: str | None = None,
    store_url: str | None = None,
    city_base: str | None = None,
    country: str | None = None,
) -> BrandContext:
    """
    Construye el contexto de marca.
    - `None`  => usa el valor por defecto de settings (útil para la CLI de Rulo).
    - `""`    => se respeta como vacío explícito (no se menciona en el copy).
    - texto   => se usa tal cual.
    """
    resolved_name = STORE_NAME if store_name is None else store_name
    resolved_number = WHATSAPP_NUMBER if whatsapp_number is None else whatsapp_number
    resolved_url = STORE_URL if store_url is None else store_url
    resolved_city = CITY_BASE if city_base is None else city_base
    resolved_country = COUNTRY if country is None else country

    return BrandContext(
        store_name=resolved_name.strip(),
        store_url=resolved_url.strip(),
        whatsapp_number=resolved_number.strip(),
        whatsapp_spoken=format_whatsapp_spoken(resolved_number),
        city_base=resolved_city.strip(),
        country=resolved_country.strip(),
    )
