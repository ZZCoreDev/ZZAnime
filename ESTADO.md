# ZZAnime — contexto corto para cada chat

Actualizado: **28/10/2026**. Leer este archivo al empezar; consultar después solo
el módulo afectado en `MAPA-PROYECTO.md` / `MAPA-ARCHIVOS.md`. Este resumen sustituye
checkpoints históricos contradictorios; las evidencias actuales prevalecen.

**Stack y entrega.** Android nativo Java 8, vistas Android + WebView y reproducción
nativa; JDK 17.0.20.1, Gradle 9.6.0, AGP 9.4.0, compileSdk 37 / target 35 / min 23.
TV y móvil comparten Java/assets; móvil añade Cast. Supabase para cuenta/sincronía;
Cloudflare Free para imágenes/canal firmado/colector; GitHub Actions para novedades.
Release visible **1.1**, tag **v1.0**: **TV 80 / móvil 48**, publicación verificada
27/10, ciclo `work/cloud-integration/runs/20261027T171215Z`.

**Carpetas activas (una línea por módulo).**
- `outputs/jkanime-tv-android/app`: app TV y código/datos compartidos.
- `outputs/jkanime-tv-android/mobile`: configuración y adaptaciones móvil/Cast.
- `outputs/catalog-lab`: observaciones originales, portadas y paquetes inmutables.
- `work/player-provider-audit`: recogida histórica, filtros y preparación incremental.
- `work/backup-integration`: empaquetado, listados observados y verificación Java/APK.
- `work/backup-delivery`: receptor firmado, entrega de datos y colector de nube.
- `work/cloud-integration`: integración, compilación y publicación verificadas.
- `work/incident-audit`: incidencias, recuperación acotada y recibo final.
- `work/ideas-1`, `work/sync-audit`: pruebas de interfaz, datos y sincronización.
- `scripts`, `work/project-checks`: comandos estables y resultados por ejecución.

**Hecho.** Servidor ZZ primero, JK segundo y cambio automático. Fichas/listados
locales sin consulta automática a JK; recomendaciones con capítulos observados.
Último APK: **4.053 series / 70.549 capítulos con opciones aprobadas**; distinto
del catálogo y del número de listados. Recuperación ONA terminó: **37 recuperados,
824 retenidos**, seis descargas verificadas. Novedades programadas cada **5 min**
en nube (puede haber retrasos de GitHub), entrega sin APK; receptor al abrir y
aproximadamente cada hora en segundo plano. Sincronía entre dispositivos confirmada
por usuario en una versión anterior. Mp4upload/Streamwish/Vidhide confirmados en muestras.

**Pendiente / límites.** 824 casos retenidos no aprobados. Frescura de opciones
limitada a **7 días**: falta refresco histórico sostenido. Home/ranking/horario y
algunas búsquedas aún dependen de JK. MEGA/Mixdrop no reproducen todas las muestras;
no prometer reproducción universal. Validación física de últimos cambios pendiente.
Arranque TV con capas duplicadas/salto de tamaño pendiente; perfil/estadísticas al
final y después iPhone/Windows. Vídeos externos: se archivan enlaces, no vídeos.
Correcciones locales de compatibilidad minSdk detectadas por lint en este lote;
no publicadas (autofill, notificaciones TV, longitud de descarga y semana ISO).

## Deuda

### Lote 2A — renovación del respaldo
Supuestos: renovar exige volver a observar y validar opciones reales; no basta
cambiar fechas ni alargar la caducidad. Tarea de nube independiente de novedades,
sin PC y con la misma firma, permisos y publicación existentes. Ningún cron nuevo
se activa antes de superar verificar y una prueba real con dos series.
El usuario canceló el contrato de lotes/gate Git y pidió retomar la hoja de ruta.
No importar masivamente archivos personales ni fuentes preexistentes para publicarlos.
Renovación preparada con estado dividido por serie, conservación de fechas reales,
validación Java y tarea independiente. Pruebas locales pasan; despliegue y muestras
remotas pendientes. No dar por renovados todos los enlaces ni por probada su reproducción.

Diez hallazgos originales de Android Lint (rutas relativas a
`outputs/jkanime-tv-android/app/src/main/java/tv/jkanime/web/`). Las correcciones
ya se habían aplicado antes de la orden de parar; en esta continuación no se toca
la app ni se publica. Se conserva el diagnóstico original para trazabilidad.

| ID | Archivo:línea | Regla / llamada | Clase |
|---|---|---|---|
| L01 | AccountActivity.java:101 | NewApi: setImportantForAutofill, API 26 | a |
| L02 | AccountActivity.java:115 | NewApi: setImportantForAutofill, API 26 | a |
| L03 | AppUpdater.java:119 | NewApi: getContentLengthLong, API 24 | a |
| L04 | FavoriteEpisodeMonitor.java:42 | NewApi: TvExtender.setContentIntent, API 35 | a |
| L05 | FavoriteEpisodeMonitor.java:42 | NewApi: constructor TvExtender, API 35 | a |
| L06 | MainActivity.java:1611 | NewApi: Calendar.getWeekYear, API 24 | a |
| L07 | UpdateMonitor.java:64 | NewApi: TvExtender.setContentIntent, API 35 | a |
| L08 | UpdateMonitor.java:64 | NewApi: constructor TvExtender, API 35 | a |
| L09 | UpdateMonitor.java:64 | NewApi: conversión TvExtender → Extender, API 35 | a |
| L10 | SessionSecurityActivity.java:9 | WrongConstant: setOrientation(1), equivalente a VERTICAL | c |

**a:** llamada sin guarda de versión en el código original, riesgo real en minSdk 23
si se ejecuta esa ruta; los hallazgos TvExtender comparten causa.
**b:** compatibilidad puramente cosmética: ninguno de estos diez errores.
**c:** falso positivo semántico por literal equivalente; no implica fallo de ejecución.
Las advertencias de estilo restantes no se corrigen en esta tarea.

**Decisiones cerradas.** Automatizar primero; no se propone refactor no pedido;
una publicación por lote. Terminar/comprobar/registrar antes de cambiar de tarea.
Probar 1–2 series de extremo a extremo antes de ampliar. Reutilizar datos, no repetir
capítulos, respetar límites y cuarentena; no rotar IP ni inventar fechas/identidades.
Sin planes de pago/R2. No imprimir secretos; token Cloudflare limitado caduca
27/10/2027. No duplicar recopiladores ni borrar bloqueos activos. No confundir build
con prueba física. Leer fallos en terminal y resolverlos sin pedir otro turno al usuario.

**Rutina vigente.** Automatizar primero y cerrar cada tarea antes de la siguiente.
Usar los pipelines existentes de `work/cloud-integration` (apps) y
`work/backup-delivery` (datos), con auditorías, muestras y recibos verificables.
Agrupar cambios antes de publicar; no usar el gate Git cancelado como bloqueo.
Repositorio conectado al historial real `ZZCoreDev/ZZAnime`, rama `lote-1-infra`,
mediante worktree del checkout existente `work/remote-artwork/hosting`.
Base real `origin/main`: `f9e6c734a7bd4477eb70aa94a5f54e620b6ff514`.
No se ha creado un commit artificial ni incorporado archivos locales para ocultar
cambios. Los archivos sin seguimiento también deben pasar el alcance del lote;
no ignorar código de app ni ampliar la lista indiscriminadamente para obtener verde.

<!-- ZZ-RENEW-STATUS -->
## Refresco automático del respaldo
Estado: complete-with-failures. Fallos pendientes: 527; capítulos vencidos pendientes: 0. Próximos a vencer: 0; capacidad: insufficient-history.
Deuda: conservar observaciones originales; reintentar fuentes verificadas. No se han cambiado fechas para ocultar fallos.
<!-- /ZZ-RENEW-STATUS -->
