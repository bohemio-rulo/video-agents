import argparse

from config.settings import INPUT_DIR, KEEP_ORIGINAL_AUDIO, OUTPUT_DIR, STORE_NAME
from services.pipeline_service import process_single_video


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Automatización de videos y copys para {STORE_NAME}"
    )
    parser.add_argument(
        "--context",
        type=str,
        default="",
        help="Dato extra opcional para los videos del lote (ej. 'Precio: 350 Bs, garantía 3 meses')",
    )
    parser.add_argument(
        "--mute-original",
        action="store_true",
        help="Silencia el audio original del video (útil si tiene locución en chino en vez de música)",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Mueve los videos originales procesados a media/input/processed/",
    )
    args = parser.parse_args()

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = sorted(
        p for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv"}
    )

    if not videos:
        print(f"No hay videos en '{INPUT_DIR}'. Coloca tus archivos .mp4 ahí y vuelve a ejecutar.")
        return

    print(f"Se encontraron {len(videos)} video(s) en cola para {STORE_NAME}.")
    for video in videos:
        try:
            process_single_video(
                video_path=video,
                extra_context=args.context,
                keep_original_audio=(not args.mute_original) and KEEP_ORIGINAL_AUDIO,
                archive_input=args.archive,
            )
        except Exception as err:
            print(f"\n[ERROR] Falló el procesamiento de '{video.name}': {err}")


if __name__ == "__main__":
    main()
