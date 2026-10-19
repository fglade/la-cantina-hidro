# La Cantina — Prefactibilidad hidroeléctrica geoespacial

Revisión 2 — 19 de octubre de 2026. **Arroyo norte incluido; cauces y curvas sin recorte predial.** Estudio preliminar con herramientas gratuitas y datos proporcionados por el propietario. Sin presupuesto de obras ni estudio de rentabilidad.

Esta revisión sustituye la selección anterior de 13,23 m de salto. El deslinde se usa como referencia para identificar obras dentro/fuera, no como límite de exclusión del recurso. Se priorizan los arroyos permanentes; las quebradas no permanentes se conservan sólo en última prioridad, según la aclaración del propietario de que acceder al agua requeriría perforar.

## Resultado principal

Se identifica la alternativa **C2-1-1 en el Arroyo norte (ID 2)**, reportado como permanente por el propietario. Presenta **172,91 m de salto bruto**, 6,0 m de aducción y **720,0 m de tubería de presión 3D** (684,8 m en planta). La ruta prioriza linderos y caminos y no cruza interiores de lotes a más de 4 m del lindero. Las cotas y geometría requieren verificación de campo; no es un emplazamiento de obra aprobado ni una solución óptima global.

**Obras exteriores al deslinde original:** 374,0 m de tubería en planta (54,6% de la ruta) y 6,0 m de aducción. El visor marca estos tramos en rojo discontinuo; los puntos indican individualmente si quedan dentro o fuera. La propuesta requiere validar acceso y tenencia en esos sectores, además de los antecedentes de uso del agua. Incluirlos en la evaluación no acredita disponibilidad para construir.

La subdivisión contiene diez lotes y un camino vehicular, con 14,49 ha de lotes. El deslinde original abarca 104,57 ha. La cobertura DTM calculada a 2 m alcanza **50,6% del deslinde**. El área DTM válida total analizada es 90,73 ha, incluyendo topografía exterior al predio. Se conservan las 512 curvas completas y los seis cauces; no se extrapola potencial donde falta DTM.

## Inventario completo de cauces

| ID | Cauce | Prioridad | Longitud total (m) | Longitud con DTM (m) | Cobertura lineal DTM |
|---:|---|---:|---:|---:|---:|
| 1 | Arroyo 1 | 1 | 2.012,1 | 668,0 | 33,2% |
| 2 | Arroyo norte | 1 | 1.513,1 | 648,5 | 42,9% |
| 3 | Quebrada 3 | 3 | 421,3 | 421,3 | 100,0% |
| 4 | Quebrada 4 | 3 | 801,8 | 801,8 | 100,0% |
| 5 | Quebrada 5 | 3 | 462,8 | 462,8 | 100,0% |
| 6 | Arroyo 6 | 1 | 797,3 | 0,0 | 0,0% |

El arroyo norte corresponde al ID 2. El ID 6 también queda visible y registrado como permanente, pero sin topografía suficiente para calcular salto o potencia. Las longitudes con DTM se estiman en un muestreo de unos 2 m; no indican que todo el cauce esté levantado.

## Coordenadas de referencia (EPSG:4326)

| Elemento | Latitud | Longitud | Cota terreno DTM (m) |
|---|---:|---:|---:|
| Bocatoma | -46.0586091 | -72.5910940 | 524,00 |
| Cámara de carga | -46.0586041 | -72.5911712 | 523,56 |
| Turbina / restitución | -46.0594616 | -72.5984324 | 351,09 |

Las coordenadas indican referencias conceptuales sobre el cauce. La casa de máquinas debe desplazarse y replantearse en una margen segura frente a crecidas, conservando la posibilidad de restitución. Las cotas de terreno se usan como aproximación de los niveles hidráulicos; no son niveles de agua medidos y el datum vertical no está certificado.

## Escenarios de generación de la propuesta base

| Q (L/s) | D interior (pulg.) | hf (m) | hm (m) | H neto (m) | P (kW) | kWh/mes medio | kWh/año |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 5,0 | 3,495 | 0,095 | 168,89 | 10,77 | 6.289 | 75.470 |
| 25 | 8,0 | 1,933 | 0,091 | 170,45 | 27,17 | 15.869 | 190.425 |
| 50 | 10,0 | 2,354 | 0,149 | 169,98 | 54,19 | 31.648 | 379.781 |
| 100 | 12,0 | 3,497 | 0,287 | 168,69 | 107,57 | 62.820 | 753.837 |

Los diámetros son **interiores idealizados de cálculo**, no diámetros nominales comerciales. Cada caudal usa un diámetro distinto: no son cuatro condiciones de una misma instalación. La energía supone factor de planta 80%, equivalente a 7.008 horas anuales a potencia nominal. La energía mensual es anual/12, no una predicción mensual. Los caudales 10/25/50/100 L/s se consideran disponibles en turbina; aún no hay aforos que acrediten caudal derivable o permanente.

Familia sugerida para la base: **Pelton / Turgo**, con salto neto de 169,98 m a 50 L/s. La selección es una inferencia de prefactibilidad por el alto salto y los caudales analizados, pendiente de curvas de fabricante y rendimiento a carga parcial. No se acredita un caudal de diseño por la sola declaración de permanencia.

## Balance hidráulico

- Hb = cota captación − cota turbina = 172,91 m.
- Salto cámara–turbina = 172,48 m.
- El descenso captación–cámara (0,43 m) se descuenta: la cámara de lámina libre interrumpe la carga de captación.
- hf = 10,67 × L × Q^1,852 / (C^1,852 × D^4,8704), en SI.
- C = 145 para plástico nuevo; K accesorios = 3 supuesto.
- hm = K × v² / (2g); Hn = Hb − descenso de aducción − hf − hm.
- P = 9,81 × Q × Hn × 0,65; E anual = P × 8.760 × 0,80.

Se elige el menor diámetro de la serie 2 a 24 pulgadas interiores que limita hf a 10% de Hb, hf+hm a 10% del salto cámara–turbina y velocidad a 3 m/s, y que conserva el eje de tubería bajo la línea piezométrica a lo largo del perfil. Para ello se supone enterramiento de 1 m. En la meseta inicial del arroyo norte, el criterio de presión exige diámetros mayores que el límite de pérdidas por sí solo; se verifica cada caudal por separado. La comprobación preliminar distribuye la fricción uniformemente y considera las pérdidas locales al final del balance; no sustituye el modelo hidráulico detallado de accesorios.

La presión estática máxima aproximada sobre el eje enterrado es de **17,01 bar**, sin golpe de ariete. Es un dimensionamiento hidráulico preliminar, no una optimización de costo. Para HDPE/PVC se debe seleccionar diámetro exterior/SDR/PN y recalcular con el diámetro interior real, presión de trabajo y transitorios. Faltan aducción, cámara/desarenador, válvulas y anclajes.

## Alternativas revisadas

| ID | Cauce / prioridad | Hb (m) | Tubería 3D (m) | Tubería exterior en planta (m) | Cruce interior (m) | Revisión piezométrica |
|---|---|---:|---:|---:|---:|---|
| C2-1-1 | Arroyo norte · P1 | 172,91 | 720,0 | 374,0 | 0,0 | Aceptable con diámetros corregidos y 1 m enterrado |
| C1-1-1 | Arroyo 1 · P1 | 97,28 | 736,9 | 493,2 | 0,0 | Aceptable con diámetros corregidos y 1 m enterrado |
| C4-1-1 | Quebrada 4 · P3 | 180,17 | 764,8 | 34,5 | 2,7 | Aceptable con diámetros corregidos y 1 m enterrado |
| C3-1-1 | Quebrada 3 · P3 | 137,44 | 474,4 | 204,3 | 0,0 | Aceptable con diámetros corregidos y 1 m enterrado |
| C5-1-1 | Quebrada 5 · P3 | 89,14 | 361,1 | 0,0 | 2,6 | Aceptable con diámetros corregidos y 1 m enterrado |

**Las quebradas son de última prioridad y quedan excluidas de la selección principal.** El propietario aclara que no son de escurrimiento permanente y que acceder al agua requeriría perforar. Sus escenarios 10–100 L/s y energía al 80% son sólo referencias matemáticas, sin recurso aprovechable acreditado. No se modelan reserva subterránea, perforaciones ni consumo de bombeo; por tanto no representan producción hidroeléctrica neta disponible. La corrección del diámetro puede mejorar el perfil piezométrico, pero no resuelve esa falta de recurso hídrico acreditado.

Los tramos se separan sólo cuando se interrumpe la cobertura DTM, no al cruzar el deslinde. Cada captación y restitución se mantienen en el mismo cauce; no se suman caudales de cursos diferentes. Los cursos 2 y 3 se incluyen aunque discurran fuera del deslinde. El curso 6 queda visible y pendiente de topografía. Las longitudes de obras exteriores se exportan en `outputs/tramos_fuera_deslinde.geojson`.

## Método SIG y trazado

GeoPandas/Shapely leen SHP y polígonos KML; Rasterio muestrea el DTM nativo de 0,25618 m/píxel. Se usan EPSG:32718 para distancias y EPSG:4326 para los vectores web. El DTM, DSM y ortomosaicos originales están en UTM 18S; no se reescriben los grandes raster originales. Las vistas raster web se reproyectan a Web Mercator con límites WGS84 para Leaflet. La precisión del píxel no equivale a precisión vertical del levantamiento.

En cada tramo continuo del cauce con DTM válido, dentro o fuera del predio, se muestrea a unos 2 m y se busca una pareja alto/bajo ordenada según sentido inferido de las cotas. Se aplica mediana de cinco muestras sólo para localizar extremos; las cotas finales se consultan al DTM. Se ubica una cámara conceptual a 6–30 m de la captación con descenso mínimo de 0,3 m cuando existe. La aducción sigue el cauce entre ambos puntos.

El trazado usa Dijkstra en grilla de 2 m con ocho vecinos, penalizando pendientes e interiores de lotes. Los caminos tienen costo base 1; bandas de 4 m de linderos, 1,3; resto libre, 4; interior de lotes, 25. Se limita la ruta al DTM válido y bajo el nivel de cámara (tolerancia 0,3 m), sin usar el deslinde como barrera. Se revisan cruces de lotes, longitud exterior y línea piezométrica. No se han comprobado servidumbres ni aptitud constructiva. El largo 3D usa el perfil muestreado aproximadamente cada 2 m.

La propuesta se selecciona entre arroyos permanentes con comprobación piezométrica preliminar aceptable, priorizando cruce interior menor de 10 m y luego máximo Hb entre las alternativas candidatas. No se enumeran todas las posiciones posibles ni se demuestra optimalidad global. El perfil supone 1 m de enterramiento; no modela golpe de ariete, inundaciones, geotecnia ni pérdidas particulares de una obra diseñada.

Curvas con intervalo de 1 m, color por Elevation y simplificación web de 0,75 m, sin recorte por deslinde. Se exportan además sin simplificar en `outputs/curvas_completas.geojson`. Los seis cauces de `hidro.shp` se exportan completos. Los ortomosaicos se reducen para web y se muestra por defecto el completo para incluir el norte. El DSM no define niveles hidráulicos: se usa el DTM de terreno.

## Verificación y decisión siguiente

Se verifican independientemente pérdidas/potencias/energía y perfil piezométrico de todas las alternativas, longitud exterior al deslinde, ausencia de cruce interior en la base y KMZ por alternativa con tres puntos y dos líneas. La regresión exige conservar los seis cauces y las 512 curvas completas, incluir más de 600 m del arroyo norte con DTM y dejar quebradas en última prioridad. El navegador se prueba con caudales, selección y descargas. El HTML incorpora vectores, imágenes y descargas; las bibliotecas y fondos externos requieren Internet.

Para decidir inversión: aforos en estiaje y serie estacional, niveles de agua y perfil topográfico independiente, alineación real de los cauces, caudal derivable, sedimentos, crecidas, restitución, emplazamiento de sala en margen segura y acceso. Revisar situación de uso del agua y autorizaciones aplicables con los antecedentes del proyecto. Sin estas comprobaciones no se confirma factibilidad técnica ni económica.

## Referencias

- [EPA, EPANET](https://www.epa.gov/water-research/epanet): metodología de pérdidas distribuidas y locales; plástico nuevo C 140–150.
- [DOE, Types of Hydropower Turbines](https://www.energy.gov/cmei/water/types-hydropower-turbines): relación entre salto, caudal y familias de turbina. La elección final debe contrastarse con fabricante.

## Archivos y reproducción

Abrir `index.html` en un navegador con Internet. Las descargas KMZ/CSV del mapa corresponden a la **alternativa seleccionada**. La exportación `outputs/la_cantina_propuesta.kmz` corresponde a la nueva base **C2-1-1**. Hay KMZ por candidato, `outputs/escenarios_todas_alternativas.csv`, `outputs/inventario_cauces.json`, resultados en `outputs/results.json` y rutas en `outputs/alternativas.geojson`.

Con Python 3.12 y los insumos originales en la carpeta del proyecto:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-lock.txt
.venv/Scripts/python analyze.py
.venv/Scripts/python build_viewer.py
.venv/Scripts/python verify_outputs.py
node --check outputs/viewer-scripts.js
```

También se admite `pip install geopandas rasterio shapely pyproj folium scipy matplotlib` para reconstrucción con versiones compatibles. No se requiere licencia pagada ni API key. Los nombres de los insumos deben conservarse. Los KML se leen con parser XML que conserva los polígonos de estos archivos; no está pensado como lector universal de todos los tipos KML/KMZ.
