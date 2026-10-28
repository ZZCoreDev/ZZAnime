# ZZDub: doblaje por etapas, fuentes autorizadas y gasto acotado

## Estado real de esta entrega

La prueba local utiliza CPU: fragmento CC de Big Buck Bunny con narración sintética inglesa añadida, Demucs real, faster-whisper, Marian inglés→español y voz genérica Piper. Produce MP4 con ES como audio predeterminado, audio original alternativo y subtítulos; verifica el español mediante una segunda transcripción. No es una prueba de japonés, WhisperX large-v3, clonación o GPU.

Modal, almacenamiento remoto y publicación real requieren cuentas/credenciales que no están configuradas. La imagen GPU no está desplegada ni se ha ejecutado: no se presenta como validada por la prueba CPU. `enabled: false`, presupuesto0, publicaciónfalse y la variable de activación ausente impiden gasto o cron activo. Docker y el perfil GPU deben superar su prueba de despliegue antes de activarse.

No se incluyen scraping de ABEMA/TVer, extracción de reproductores restringidos, DRM, captchas, VPN, rotación de IP ni eliminación de atribuciones. Las fuentes se declaran por el operador como propias/autorizadas o reutilizables; la procedencia se conserva. No se clonan personajes/actores: la implementación actual usa voces genéricas configuradas. Adaptadores MEGA/MP4upload no están implementados ni probados; el publicador disponible es YouTube oficial y su vista previa local.

## Estructura

`dubpipe/ingest.py`, `separate.py`, `transcribe.py`, `translate.py`, `tts.py`, `fit.py`, `mix.py`, `qa.py`, `publish.py`, `notify.py`: un módulo por etapa. `core.py`: caché con SHA256; `step_worker.py`: aislamiento y timeouts reales; `state.py`: reservas y checkpoints; `cli.py`: director; `modal_app.py`: GPU efímera. `tests/`: caché, fallos, presupuesto, datos, QA y publicación. Workflow: `../../.github/workflows/pipeline.yml`.

Los artefactos se cachean por bytes de entrada, configuración y código de la etapa. Cada bloque LLM válido se guarda antes de continuar. Un fallo de ajuste no vuelve a ejecutar separación, transcripción ni traducción. El cache remoto usa un objeto comprimido por etapa para reducir peticiones. Un vídeo marcado por QA va a `review/` y no se publica.

## Prueba local gratuita

Python3.12, Windows/Linux. Desde esta carpeta:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -r requirements-local.txt
.venv/Scripts/python -m unittest discover -s tests -v
.venv/Scripts/python demo.py
```

En Linux sustituir `.venv/Scripts/python` por `.venv/bin/python`. En este workspace se ha usado `../../work/dubbing-runtime/Scripts/python.exe`; salida en `../../work/dubbing-demo/completion.json` y `ready/` o `review/`. La prueba no sube nada. Descargar modelos requiere red y espacio local; 0USD significa cero facturación GPU/API, no una medición del consumo eléctrico. Big Buck Bunny no contiene diálogo: la narración de ensayo se añade explícitamente para ejercitar la cadena.

## Activación futura, únicamente después de validar japonés y coste

1. **Fuentes:** configurar `sources.yml` con archivos directos y procedencia. El ejemplo BBB está apagado; se marcaría para revisión si no se detecta habla. El descubrimiento lee archivos declarados o un JSON cambiante de un dominio autorizado (`kind: json_manifest`, `manifest_url`, cuerpo con `episodes`). Así puede detectar episodios nuevos del feed propio cada6h sin cambiar código. No incluye un crawler de plataformas japonesas restringidas.
2. **Modal:** cuenta y token con permiso para desplegar esta app. Añadir `MODAL_TOKEN_ID` y `MODAL_TOKEN_SECRET` mediante `gh secret set NOMBRE --repo ZZCoreDev/ZZAnime` (introducir valores de forma privada). No activar planes ni asumir que créditos o precios permanecen iguales. El workflow despliega `modal_app.py` solo después de preflight completo. El método local equivalente, con credenciales inyectadas en memoria, es `python -m modal deploy modal_app.py`.
3. **Almacenamiento:** bucket privado dedicado S3 o R2 ya aprobado por el operador. Secretos `S3_BUCKET`, `S3_ENDPOINT` (para R2), `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` y opcional `S3_REGION`. Permisos solo para el bucket/prefijo. No se crea ni cambia facturación automáticamente. Configurar la regla de `tools/lifecycle.json` para el prefijo `zzdub/temporary/` y **conservar las reglas preexistentes del bucket**. El programa comprueba la regla y rechaza ejecución si falta. El vencimiento se solicita a7d; la eliminación efectiva depende del proveedor. Nunca aplicar esa regla al bucket completo ni a vídeos originales del usuario.
4. **YouTube:** habilitar YouTube Data API en un proyecto Google y crear cliente OAuth de escritorio. Desde un equipo del dueño ejecutar `python tools/youtube_oauth.py`: el consentimiento se hace en el navegador y el token se envía directamente a `YOUTUBE_OAUTH_JSON` en GitHub Secrets. No imprime ni guarda el token en el repo. Se necesitan permisos de subir vídeos y gestionar sus subtítulos/listas. Las credenciales se inyectan al proceso; los secretos de almacenamiento pasan a Modal como secreto efímero, no como valores en archivos ni en parámetros de datos.
5. **Prueba GPU:** antes de cron, subir una muestra autorizada japonesa de20–60s, configurar una fuente y `max_episodes_per_run: 1`, activar `enabled`, `publish.enabled` y un presupuesto explícito. Revisar/declarar las revisiones de modelos antes de uso de producción (actualmente los nombres de algunos modelos apuntan a `main`). Ejecutar manualmente con `dry_run: true` primero: solo pruebas/doctor. Después realizar una ejecución manual controlada con publicación privada programada y confirmar QA, coste y reproducción en la plataforma. Esta fase sigue pendiente por falta de cuentas y autorización de pago.
6. Solo tras esa prueba fijar `ZZ_DUBBING_ENABLED=true` en variables del repo. El cron preparado es cada6h. `dry_run` está activado por defecto al despachar manualmente. Con la variable ausente el cron no procesa nada.

El workflow debe publicarse junto con esta carpeta mediante una lista explícita de archivos; nunca subir `work/`, pesos, vídeos, claves o el árbol entero del workspace. `state/processed.json` es la plantilla; el estado vivo se versiona en la rama separada `dubbing-state`, ruta `state/processed.json`. Las reservas se empujan a GitHub **antes** de invocar GPU, con exclusión de ejecuciones concurrentes. Si se pierde el acuse de un despacho sin id, se conserva como incierto en lugar de cobrar una invocación duplicada. Los vídeos subidos se reconcilian por una etiqueta de hash antes de permitir otro insert. Los casos irresolubles quedan retenidos; no existe una garantía de recuperación automática frente a toda caída de un servicio externo.

La salida `state/published-links.json` contiene identificador, hash, idioma y URL oficial. ZZAnime puede guardar esos enlaces sin alojar el vídeo. **La importación a ZZAnime no está conectada en esta entrega**: su reproducción oficial debe probarse tras elegir destino y disponer de una subida autorizada. No se modificaron los servidores ni el código de la app.

## Costes y límites

La ejecución GPU usa L4, como máximo1200s por llamada y600s de arranque; cada llamada reserva ese peor caso más30s. El límite diario es de **GPU**, usando la tarifa declarada; no garantiza la factura global de CPU, memoria, imagen, almacenamiento o tráfico. Las hipótesis de precio caducan a30d y bloquean nuevos trabajos hasta revisarlas. No hay reintentos automáticos de una llamada GPU sin identidad persistida. El estado contabiliza reservas conservadoramente, incluso si un proceso cae antes de consumirlas.

Con L4 a0,000222USD/s, más2 núcleos y16GiB, un escenario de10–30min de función cuesta aproximadamente0,17–0,51USD por episodio antes de almacenamiento/tráfico/créditos. Para30 episodios serían unos5–15USD con esas hipótesis; reservar20–30USD/mes sería un margen provisional, no una predicción medida. La prueba CPU no sirve para deducir el rendimiento de un episodio japonés largo ni la calidad de voces por personaje. No se ha contratado nada.

Destino MEGA/MP4upload no reduce el coste del doblaje: solo cambia almacenamiento, reproducción y tráfico. Evaluar un adaptador oficial y una subida pequeña autorizada antes de pagar; no se recomienda un plan por el resultado de esta demo.

## Control de calidad y fallos

- WER español>15%, frases fuera de tiempo>5%, duración desviada>3%, clipping o silencio dentro de la voz ⇒ revisión.
- Sin habla ⇒ revisión; nunca se interpreta un vídeo mudo como doblaje correcto.
- Compresión de duración máxima25%; una sola reescritura breve por frase que no cabe en el backend LLM. El perfil CPU Marian no finge un reescritor: retiene frases que no caben.
- JSON traducido debe conservar cantidad e ids. El traductor CPU divide todas las oraciones para evitar perder las últimas; las marcas de tiempo del segmento original se conservan.
- Descargas con backoff acotado; HTTP403/429 se conservan para reintento y no se sortean. Cada fallo queda registrado. No se permiten rutas de cache fuera del directorio ni extracción de archivos arbitrarios.
- Email/Telegram opcionales; sin destinatario se genera solo informe local. Telegram requiere `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`; email requiere variables/secretos SMTP y destinatario explícito. No se envía nada durante la demo.

## Fuentes técnicas

[Modal GPU](https://modal.com/docs/guide/gpu), [tarifas](https://modal.com/pricing), [WhisperX](https://github.com/m-bain/whisperX), [Piper](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md), [YouTube insert](https://developers.google.com/youtube/v3/docs/videos/insert), [BBB CC-BY](https://peach.blender.org/about/). Las fichas de voces se conservan junto a los modelos descargados. Las licencias de cada modelo y material siguen aplicándose; no se eliminan atribuciones.
