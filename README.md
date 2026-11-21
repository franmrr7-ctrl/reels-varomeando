# reels-varomeando

Reels verticales (1080x1920, ~17 s) de [varomeando.es](https://varomeando.es), generados gratis con FFmpeg + Pillow en GitHub Actions y publicados por un escenario de Make en la pagina de Facebook.

## Piezas

| Archivo | Para que sirve |
|---|---|
| `build_index.py` + `.github/workflows/index.yml` | Cada madrugada lee los sitemaps (`osetin_recipe-sitemap*.xml`) y el JSON-LD de cada receta Thermomix. Guarda `data/index.json` (lista ligera) y `data/recipes/<id>.json`. La API REST de WordPress **no** expone las recetas, por eso se hace asi. |
| `generate.py` | Crea el video desde un JSON (ver `examples/`). Marca Varomeando: naranja `#F3A12A` del logo, Yanone Kaffeesatz + Noto Serif. Las fotos son pequenas, asi que van en una tarjeta con marco sobre fondo desenfocado en vez de a pantalla completa. |
| `.github/workflows/reel.yml` | `workflow_dispatch` que genera el video y lo sube como asset de una release (conserva las 40 ultimas). |
| `music/` | Pistas lo-fi CC0 de OpenGameArt (ver `music/LICENSE.txt`). |

## Flujo en Make (2 veces al dia, 13:30 y 20:30)

1. `GET https://raw.githubusercontent.com/franmrr7-ctrl/reels-varomeando/main/data/index.json`
2. Rotacion: `((floor((formatDate(now; "X") + 28800) / 43200)) % length(lista)) + 1` (una receta distinta por ejecucion, recorre todas sin saltarse ninguna).
3. `GET data/recipes/<id>.json`, Gemini genera el JSON del video y el texto del post.
4. `workflow_dispatch` de `reel.yml`, espera ~150 s, lee la ultima release y comprueba que es de esa receta.
5. Publica el Reel en la pagina y comenta con el enlace a la receta.

## Uso local

```bash
pip install pillow numpy   # y ffmpeg instalado
python generate.py examples/tarta-de-galletas.json salida.mp4
python build_index.py      # regenera data/ (tarda unos minutos la primera vez)
```
