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
Estado: complete-with-failures. Fallos pendientes: 4864; capítulos vencidos pendientes: 0. Próximos a vencer: 0; capacidad: behind.
Deuda: conservar observaciones originales; reintentar fuentes verificadas. No se han cambiado fechas para ocultar fallos.
Equivalencia comprobada: Mao, 5/26 capítulos recientes; incidencias pendientes: 21.
Diagnóstico por serie: 208/434; pendientes: 226. Sin consultas adicionales ni aprobación automática. Detalle: provider-data/state/renewal-diagnostics.md.
<!-- /ZZ-RENEW-STATUS -->

<!-- OBSERVED-TOKEN-RECOVERY -->
## Recuperación automática por número observado
Touhai1 y Blue Lock vs. U-20 Japan2: recogida remota, recepción RSA/SHA256 y reproducción Mp4upload comprobadas con JK bloqueado; run40701050398. No es prueba física Android.
Causa corregida: la fuente publica01/02 y el recolector pedía1/2. Se utiliza únicamente el token presente en la lista con título/slug/temporada y número equivalentes; se rechazan duplicados, capítulos ausentes y otras temporadas.
Activado en las tareas existentes de nube, sin otro recopilador ni APK. Reutiliza renovación incremental: omite observaciones frescas, respeta pausas/reintentos y conserva originales/fechas/opciones. Fallos en provider-data/state/renewal-failures.json y ESTADO.md remoto. No declara recuperadas todas las incidencias; los casos sin equivalencia siguen retenidos.
Blue Lock no reprodujo en el primer intento del canal firmado; un único reintento con las mismas URLs pasó por Mp4upload, sin otra recogida. Causa externa no confirmada; conservar esta limitación.
55 controles:20 renovación,12 canal,10 identidad,13 tokens. Evidencia:work/backup-delivery/token-proof/ y automation/hourly/evidence/observed-token-proof.json.
<!-- /OBSERVED-TOKEN-RECOVERY -->

<!-- INCIDENT-DIAGNOSTICS -->
## Auditoría automática de incidencias por serie
Corte local: 3284 capítulos con fallo, agrupados en 332 series; dos muestras reales diagnosticadas. No equivale a reparación ni reproducción.
Publicados diagnósticos separados por fuente/paso: ficha, listado, episodio, opciones y análisis; diferencia404/302/403/429, identidad, capítulo ausente, proveedor no aprobado y límites. Prueba Übel Blatt1/Magi-Lumière1: JK403 al listar, alternativas404 en ficha; seis consultas. No se eluden bloqueos.
Renovación existente reparte reintentos por series distintas y prioriza las aún sin diagnóstico, conservando cuota25%, pausas y omisión de registros frescos. Tio no solicita episodio si su ficha ya falla. Informes state/renewal-diagnostics.json y .md en provider-data; cobertura/fallos en ESTADO remoto. Sin nuevo recopilador, PC, IA por registro ni APK.
72 controles correctos y dos diagnósticos reales antes de instalar. Pendientes se detallan en reintentos permitidos; no se promete auditoría profunda instantánea de todas las series. No hay aprobación automática de equivalencias/reproductores: cada corrección seguirá requiriendo dos reproducciones válidas. Borrador acentos/SW retirado del paquete desplegable y conservado en work/incident-audit/accent-draft; las muestras sin reproducción siguen retenidas.
Código 5a0ba74811aa41d27b7e1dd41273f32624e58c33; evidencia automation/hourly/evidence/incident-diagnostics-proof.json y work/incident-audit/diagnostic-rollout/.
<!-- /INCIDENT-DIAGNOSTICS -->

<!-- SOURCE-FAILURE-CACHE -->
## Pausa breve de fallos de fuentes
Activada en nube tras probar Mao2 y Touhai2: opciones validadas por Java real y reproducción de ambas en navegador con scripts/políticas de la app. No prueba física Android ni nueva recepción firmada de estas muestras: la prueba no modifica el archivo.87 controles correctos.
Memoria temporal acotada: JK403 pausa60s por origen; fichas alternativas404 se reutilizan300s por URL exacta. Respeta Retry-After superior. No guarda documentos positivos, vídeos ni cambia fechas; no rota IP. Es ahorro oportunista entre peticiones atendidas por el mismo Worker, no almacenamiento persistente garantizado. Prueba real:10 consultas y1 fallo reutilizado; simulación dos series/dos vueltas12→5. No garantiza ese ahorro en producción.
Código 31b998bd4ca2d2688ec91e7d34a3a2a9158eda73; evidencia work/incident-audit/source-cache-rollout/ y automation/hourly/evidence/source-failure-cache-proof.json. No APK nueva. Seguir midiendo ritmo real/capacidad en renewal-health; no dar por resueltas todas las incidencias. Próximo: pruebas físicas de avisos y Seguir viendo; catálogo continúa autónomo, Inicio/Horario confirmados intactos.
<!-- /SOURCE-FAILURE-CACHE -->
