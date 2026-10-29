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
Estado: complete-with-failures. Fallos pendientes: 25335; capítulos vencidos pendientes: 0. Próximos a vencer: 0; capacidad: behind.
Deuda: conservar observaciones originales; reintentar fuentes verificadas. No se han cambiado fechas para ocultar fallos.
Equivalencia comprobada: Mao, 12/26 capítulos recientes; incidencias pendientes: 0.
Diagnóstico por serie: 2715/2716; pendientes: 1. Sin consultas adicionales ni aprobación automática. Detalle: provider-data/state/renewal-diagnostics.md.
Cobertura de catálogo: 5053 títulos, 71675 capítulos con registros, 1852 capítulos observados sin opciones y 0 vencidos. Presencia no equivale a reproducción. Detalle: state/archive-coverage.md.
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

<!-- ENTITY-TITLE-RECOVERY -->
## Vivy y títulos con entidades HTML
Causa confirmada en dos documentos reales: Vivy y King’s Raid usan&#039; en el título; el recolector solo decodificaba&#39;. Faltaban los listados completos y las series nunca entraron en el respaldo de proveedores. La renovación de nube no las borró: solo recorría registros existentes.
Corregida decodificación numérica decimal/hexadecimal de una sola pasada; sigue rechazando capítulos/títulos distintos, controles y entidades inválidas.14 controles de entidades,23 de parser,8 de importación más suites previas. Vivy1/Vivy2 y King’s Raid1 reprodujeron en navegador con JK bloqueado; no equivale a prueba física Android.
Entregados39 capítulos nuevos por el canal firmado: Vivy13/13 y King’s Raid26/26. Run40714623776, firma RSA y huellas verificadas contra el canal público. No APK nueva; al reabrir la app debe recibir los datos. Originales y fechas auténticas conservados, importación idempotente dentro de la concurrencia compartida.
Grupo de64 candidatos del mismo problema: recuperación histórica puntual local con el recopilador existente y sin IA; novedades y renovación permanentes siguen en nube. Se recuperaron650 registros adicionales reutilizando39; estado de entrega automática: complete. Incidencias de fuente conservadas: 17; no confundir con rechazos de validación de la importación. No prometer reproducción de cada capítulo por validar URLs.
Estado/evidencias: work/incident-audit/vivy/automatic-group.json, batch-preparation.json, first-two/delivery.json y title-group/delivery.json. Registro automático final: entity-result.json. Pendiente miniatura por defecto de Seguir viendo sigue compilada sin publicar APK.
<!-- /ENTITY-TITLE-RECOVERY -->

<!-- PLAYER-PROTECTION-COVERAGE -->
## Protección de reproducción y cobertura completa, 28/10/2026
Publicado móvil57/TV89 mediante pipeline existente: bloquea documentos/iframe externos al proveedor seleccionado y ventanas emergentes; iframe sin permiso de navegación superior/popups. Opciones guardadas priorizan Mp4upload, Streamwish y Vidhide antes de MEGA. Conserva alternativas/manual, ServidorZZ Online y Respaldo. No se promete ausencia universal de publicidad. Seguir viendo usa miniatura original del capítulo en ambas apps, sin capturar controles del proveedor.
Pruebas:58 controles de proveedores/políticas; Vivy1 y King's Raid1 reproducen con los scripts y restricciones actuales en navegador, JK bloqueado. Compilación/publicación completa y seis descargas GitHub verificadas; no prueba física Android. Recibo work/cloud-integration/runs/20261028T155505Z, work/player-mega-controls/ads-playback-proof.json.
Auditoría determinista de TODO el catálogo, reutilizando archivo y listados observados:5053 títulos,73253 capítulos observados,71246 con registros,2007 sin opciones,0 vencidos y52 series sin listado observado. Grupos se solapan:969 series con huecos,818 con redirecciones retenidas,434 con errores de renovación. No equivale a reproducción masiva; disponibilidad de esas52 desconocida. Cero consultas a fuentes/IA para este inventario. Detalle work/incident-audit/coverage/archive-coverage.md y .csv.
Recuperación incremental añadida a renovación existente en nube: solo capítulos observados ausentes, omite guardados y pausados; comparte cuota de reparación máxima25% cuando hay renovaciones sanas, máximo400 por ejecución/11min, sin otro recopilador. Fallos se conservan y reintentan; entrega firmada ya existente sin APK.34 pruebas de cobertura/renovación pasan. Mao2 y Touhai2 recuperados desde estado aislado sin esos registros con colector real y validador Java; segunda pasada0 consultas y fechas intactas. Ambas muestras reproducen; Mao necesitó un reintento, conservar esta limitación. Evidencia work/incident-audit/coverage/missing-proof/.
Pokémon películas5 y4 NO reparadas: /1/ redirige al mismo padre /pelicula/, antes retenido. Ninguna de sus cinco familias independientes inició vídeo en la prueba; API AnimeCast tampoco devolvió alternativas. No promover ni ampliar ese grupo como reproducible. Capacidad allowObservedSingle de fast-http queda opcional, no activada en recopilación masiva; hash del transporte cambió, no reutilizar prueba antigua de recover-ona sin validarla. Originales y fechas conservados. Evidencia work/incident-audit/movie-redirect/.
Supuestos: no tocar Inicio/Horario/carrusel confirmados; presencia de enlace no es reproducción. Instalación de actualización y ausencia de anuncios/reanudación física en Android pendientes de comprobar en dispositivos.
<!-- /PLAYER-PROTECTION-COVERAGE -->
Instalación de nube verificada por SHA256: 664ed11bb9d0312581333ef3412bfb697b0f962f. Renovación habilitada; informes y recuperación se ejecutan en la tarea existente.

<!-- MANUAL-PROVIDER-CHOICE -->
## Selección controlada de proveedores y recuperación continua
Publicado móvil59/TV91 mediante pipeline existente; todas sus etapas correctas y seis descargas GitHub verificadas. Recibo work/cloud-integration/runs/20261028T164949Z y work/player-mega-controls/choice-delivery.json.
Nueva decisión del usuario: primer intento con el proveedor preferido si está disponible en Servidor ZZ; al fallar no recorrer proveedores/fuentes automáticamente. Abrir Fuente cancela temporizadores y resultados asíncronos anteriores, muestra opciones sin reproducirlas y mantiene el control manual incluso al cancelar. Elegir proveedor inicia solo ese; fallo queda visible para elegir otro. No se retiran reproductores, descargas, fuentes, progreso ni protección publicitaria. Sustituye expresamente el encadenado automático anterior.
ServidorZZ Online consulta metadatos sin abrir reproductor: combina botones estáticos y tabla JSON dinámica de formato observado, sin ejecutar scripts, y solo carga la página de vídeo después de seleccionar. Valida ID y nombre al aplicar la opción; si no están o la fuente no responde, informa sin cambiar automáticamente. No promete superar bloqueos externos. Pruebas:58 políticas/proveedores y62 de selección/metadatos; dos documentos reales con7 opciones cada uno, sin cargar vídeo. No prueba física Android; navegación y ausencia de saltos requieren confirmación en TV.
Recuperación existente reanudada en nube, run40728881634 finalizado:400 solicitados,53 actualizados,6 registros adicionales, entrega firmada publicada y siguiente lote40730236546 iniciado automáticamente. Se conserva lo guardado. Observaciones ahora73274, registros71252, huecos2022,0 vencidos; se observaron21 capítulos adicionales, por eso el número de huecos también puede aumentar.52 títulos sin listado observado conservan disponibilidad desconocida. No declarar todas las series reparadas ni un enlace validado como reproducción.
Continuación ahora también considera capítulos observados ausentes cuando no quedan renovaciones previas; errores de ausentes se incluyen en cobertura y se reintentan con pausas.35 pruebas de cobertura/renovación correctas; instalación de nube verificada por hash, código7f9f93ba932c13848a048c45abec5352a9b852ae. Originales, procedencia, fechas reales, URLs canónicas y cuarentena intactos. Fuentes alternativas ya se copian al mismo archivo firmado cuando son identificadas/validadas; no crear otro recopilador ni guardar vídeos propios.
Pendiente: incidencias externas/identidades retenidas continúan por grupos; Pokémon5/4 no demostraron reproducción. No dar por finalizada su reparación. Perfil/estadísticas/iPhone siguen aplazados; Inicio/Horario/carrusel confirmados intactos.
<!-- /MANUAL-PROVIDER-CHOICE -->

<!-- NEWS-WATCHDOG -->
## Respaldo del disparador de novedades
Cron5min habilitado, pero GitHub registra huecos de varias horas. Recolección incremental manual de recuperación solicitada40766629288. Watchdog dentro del ejecutor serializado de renovación reutiliza run.py --collect --publish si la última recogida comprobada tiene300s; no segundo recolector ni escritura paralela. Conserva capítulos y firmas, recarga observaciones después de cada intento; fuente fallida espera900s y registra news-watchdog.json. Proceso de novedades y calendario de renovación existentes se mantienen. No depende de PC, no APK ni IA por registro.44 pruebas locales correctas, incluidas dos series de fixture y conservación de originales; no equivale a reproducción ni a prueba viva concluida. Cadencia efectiva pendiente de medir y limitada por duración/colas de GitHub; no prometer cinco minutos exactos.
<!-- /NEWS-WATCHDOG -->

## Novedades en nube: comprobación real 29/10/2026
Recuperación40766629288 finalizada success. Watchdog instalado y ejecutado realmente: último intento05:00:09UTC complete; publicación05:00:23UTC,4168 series,71450 capítulos,349524 opciones. Lector real de la app acepta entrega remota; firma RSA e integridad del índice público comprobadas de nuevo. No prueba física de reproducción. Sin PC ni APK nuevo, sin segundo recopilador. Registro collection-status conserva5 pendientes y8 retenidos, reintento15min; no declarar todas las incidencias reparadas. Cadencia objetivo300s, limitada por colas/duración; no SLA exacto. Renovación histórica aún insuficiente:253.73 capítulos/h,11.73 días por barrido,0 vencidos a05:03UTC. Prioridad posterior: mejorar capacidad incremental respetando límites antes de caducidad. Evidencias: work/backup-delivery/current-cloud-status.json y news-watchdog-install.json.

## Recuperación de las cinco novedades y ahorro del histórico29/10
Diagnóstico real: JK devuelve403 desde Cloudflare, incluso consultando directamente el capítulo; tres equivalencias alternativas404 y otras dos soloVOE, no admitido en APK actual. No se evita el bloqueo ni se habilita un dominio/proveedor sin probar. Vía directa experimental NO activada para recogida general al no recuperar las muestras en nube. Recuperación puntual por HTTP normal de los5 capítulos exactos; Mahou no Shimai3 y Sekai Saikyou no Majo4 reproducen con scripts/protección actuales en prueba automática headless, sin JK durante reproducción; no prueba física Android. Otros3 validados por identidad/número/opciones, no reproducción. Importación incremental existente conserva capítulos y fechas, solo añade ausentes; entrega pendiente del workflow de prueba recovered-import. No afirmar resuelta la causa externa ni recogida futura de estos5 desde nube hasta desaparecer bloqueo/equivalencia válida.
Ahorro: watchdog usa --news-only para omitir auditoría completa y despliegue cuando no recibió opciones ni referencias nuevas; histórico conserva su publicación final. Novedad real sigue entrega inmediata por mecanismo existente.45 pruebas pasan (incluye2 series y cero build/despliegue en comprobación vacía). news-incidents.json registra fuentes/códigos/fecha y reintento; collection-status diferencia cobertura parcial del éxito técnico. Rendimiento por medir en nube; no prometer capacidad7d.

Recuperación5 novedades terminada: workflow40822801440 success; importados5, reutilizados0,0 retenidos. Los5 aparecen con opciones en shards públicos reales; auditoría de inicio24/24 guardados. Sin APK ni reemplazar originales. Causa externa403 persiste; reintentos/diagnóstico activados, no declarar solucionada captación futura desdeJK. Ahorro --news-only desplegado,45 pruebas; capacidad histórica real pendiente de medir. Evidencia work/backup-delivery/news-five-rollout.json.

## Publicación VOE completada29/10
TV93/móvil61 publicados con pipeline existente: 27 etapas correctas,descargas verificadas por el pipeline,misma firma. Dos muestrasVOE reproducen en navegador aislado, no prueba físicaAndroid. Corrección: documento principal limitado aVOE/alias observado, PlayJW, CDNlegítima; ventanas/anuncios/navegaciones externas siguen filtrados, nonce y origen preservados. VOE disponible enRespaldo online de la APK nueva. Canal compartido NO ampliado aVOE para evitar rechazo enAPK anteriores; entrega compatible de nueva familia pendiente. AnimeFenix comparte mismos enlacesVOE en dos muestras; no fuente automática nueva activada. Anikuro no ofrece episodios en páginaobservada. Cinco novedades recuperadas ypublicadas aparte,24/24 portada con opciones. Histórico reanudado con omisión de publicaciones vacías; capacidad final por medir. Recibo work/backup-delivery/voe-release-result.json.

## Complemento VOE compatible: fase de dos muestras
Canal adicional firmado /voe/channel.json, misma clave y formato; canal raíz mantiene exclusivamente proveedores compatibles con APK antiguas. Observaciones VOE aisladas en state/voe-state, sin reemplazar enlaces/fechas de legado. Colección globalVOE deshabilitada; prueba autenticada fija Sasaki4/Sekai4 antes de ampliar. Ambos lectores reales Java se ejecutan antes/después de publicar. RenovaciónVOE a5d dentro del histórico existente, con pausas/fallos anteriores; novedades conservan su proceso separado.50 pruebas Python y64 controles de fuentes pasan; prueba viva aún pendiente. Cliente debe sumar complemento sin sustituir respaldo anterior. No servicios nuevos, IA ni pago.

## Complemento VOE entregado y automatizado
Dos muestras Sasaki4/Sekai4 recogidas desde nube, firma y hashes verificados, lector real suma VOE sin perder opciones antiguas; firma inválida aislada y caché offline comprobadas. Ambas reproducen desde entrega pública con scripts/política actuales; no prueba física Android. ClienteTV94/móvil62 publicado y descargas verificadas por pipeline. VOE enServidorZZ mediante complemento firmado/voe, canal antiguo conserva su esquema y proveedores. Recogida global activada solo después de esas pruebas; incremental, sin reemplazar legado, sin IA por registro/PC/servicios nuevos. RenovaciónVOE real a5d integrada en histórico con reintentos y sin falsificar fechas. Histórico existente retomado; siguiente tarea: medir/cuadrar capacidad antes7d, no afirmar ya alcanzada. Evidencias work/backup-delivery/voe-overlay-completion.json y voe-overlay-live-consumer.json.

## Histórico: reparaciones accesibles desde el inicio del lote
Tras cerrar VOE, corregido selector: presupuesto nominal75/25 antes concatenaba300 sanos y100 reparaciones; el límite11min podía acabar antes de llegar a ellas. Ahora entrelaza3 sanos+1 reparación, alternando fallos y capítulos observados ausentes. Prueba8 primeros:6 sanos+1 fallo+1 ausente; sin repetidos, frescos ni pausados. Verificadores previos pasan; cambios publicados en nube759f688920c6c945786fff8c636f53058076a6f2. No sube frecuencia de consultas ni cambia fechas, límites o recolector. Añadidos contadores attempted/repairAttempts/earlyRepairAttempts para medir ejecución real; rendimiento sostenido aún por medir. Evidencias work/historical-throughput/status.json.

Histórico: reparto entrelazado validado también con cola lineal(deque), sin desplazamientos cuadráticos al evaluar todo el archivo.29 pruebas de selección/renovación pasan tras este ajuste; código23b0a96d8de8450d38e44232b830a0e9408491dd. Medición sostenida pendiente; no declarar todo el archivo renovado.
Módulos VOE: automation/hourly/voe_channel.py separa/captura/renueva y firma complemento; voe-java contiene consumidor actual, java conserva consumidor legado para comprobar canal raíz. App ProviderBackupUpdates usa cachés independientes y ProviderBackupCatalog las combina sin duplicar opciones. /voe/channel.json comparte clave, no reemplaza /channel.json. Orquestación y recibo local: work/backup-delivery/complete_voe_overlay.py y voe-overlay-completion.json. Histórico: work/historical-throughput/advance.py y status.json.
