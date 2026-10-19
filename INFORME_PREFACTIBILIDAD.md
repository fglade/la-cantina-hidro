# La Cantina — Prefactibilidad hidroeléctrica geoespacial

Fecha: 19 de octubre de 2026. Estudio preliminar con herramientas gratuitas y datos proporcionados por el propietario. Sin presupuesto de obras ni estudio de rentabilidad.

## Resultado principal

Se identifica la alternativa **C1-2-1 en el arroyo 1**, reportado como permanente por el propietario. Presenta **13,23 m de salto bruto**, 6,0 m de aducción y **30,0 m de tubería de presión 3D** (27,5 m en planta). La ruta sigue la banda junto al deslinde y no cruza interiores de lotes a más de 4 m del lindero. El tramo está junto al borde del levantamiento; las cotas y la geometría requieren verificación de campo. No es un emplazamiento de obra aprobado ni una solución óptima global.

La subdivisión contiene diez lotes y un camino vehicular, con 14,49 ha de lotes. El deslinde original abarca 104,57 ha. La cobertura DTM calculada a 2 m alcanza **50,6% del deslinde**. No se extrapola potencial al sector sin DTM.

## Coordenadas de referencia (EPSG:4326)

| Elemento | Latitud | Longitud | Cota terreno DTM (m) |
|---|---:|---:|---:|
| Bocatoma | -46.0675860 | -72.5910013 | 447,49 |
| Cámara de carga | -46.0676075 | -72.5910724 | 445,78 |
| Turbina / restitución | -46.0677040 | -72.5913469 | 434,26 |

Las coordenadas indican referencias conceptuales sobre el cauce. La casa de máquinas debe desplazarse y replantearse en una margen segura frente a crecidas, conservando la posibilidad de restitución. Las cotas de terreno se usan como aproximación de los niveles hidráulicos; no son niveles de agua medidos y el datum vertical no está certificado.

## Escenarios de generación de la propuesta base

| Q (L/s) | D interior (pulg.) | hf (m) | hm (m) | H neto (m) | P (kW) | kWh/mes medio | kWh/año |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 4,0 | 0,432 | 0,233 | 10,86 | 0,69 | 404 | 4.851 |
| 25 | 6,0 | 0,327 | 0,287 | 10,91 | 1,74 | 1.015 | 12.185 |
| 50 | 8,0 | 0,291 | 0,363 | 10,87 | 3,46 | 2.023 | 24.280 |
| 100 | 10,0 | 0,354 | 0,596 | 10,57 | 6,74 | 3.937 | 47.240 |

Los diámetros son **interiores idealizados de cálculo**, no diámetros nominales comerciales. Cada caudal usa un diámetro distinto: no son cuatro condiciones de una misma instalación. La energía supone factor de planta 80%, equivalente a 7.008 horas anuales a potencia nominal. La energía mensual es anual/12, no una predicción mensual. Los caudales 10/25/50/100 L/s se consideran disponibles en turbina; aún no hay aforos que acrediten caudal derivable o permanente.

Familia sugerida para la base: **Michell-Banki / Crossflow**, por el salto neto del orden de 11 m y el rango de caudal analizado. La selección es una inferencia de prefactibilidad, pendiente de curvas de fabricante y rendimiento a carga parcial. Pelton/Turgo se muestran como familias posibles en las alternativas de mayor salto. Francis no es la primera opción propuesta para esta escala y caudal incierto, sin excluir una evaluación específica de proveedor.

## Balance hidráulico

- Hb = cota captación − cota turbina = 13,23 m.
- Salto cámara–turbina = 11,52 m.
- El descenso captación–cámara (1,71 m) se descuenta: la cámara de lámina libre interrumpe la carga de captación.
- hf = 10,67 × L × Q^1,852 / (C^1,852 × D^4,8704), en SI.
- C = 145 para plástico nuevo; K accesorios = 3 supuesto.
- hm = K × v² / (2g); Hn = Hb − descenso de aducción − hf − hm.
- P = 9,81 × Q × Hn × 0,65; E anual = P × 8.760 × 0,80.

Se elige el menor diámetro de la serie 2 a 24 pulgadas interiores que limita hf a 10% de Hb, hf+hm a 10% del salto cámara–turbina y velocidad a 3 m/s. Es un dimensionamiento hidráulico preliminar, no una optimización de costo. Para HDPE/PVC se debe seleccionar diámetro exterior/SDR/PN y recalcular con el diámetro interior comercial. Falta diseñar la aducción, cámara/desarenador, válvulas, anclajes y presión transitoria.

## Alternativas revisadas

| ID | Régimen declarado | Hb (m) | Tubería 3D (m) | Cruce interior (m) | Revisión piezométrica |
|---|---|---:|---:|---:|---|
| C1-1-1 | arroyo | 4,14 | 203,2 | 0,0 | Aceptable bajo supuesto de 1 m enterrado |
| C1-2-1 | arroyo | 13,23 | 30,0 | 0,0 | Aceptable bajo supuesto de 1 m enterrado |
| C4-1-1 | quebrada | 180,17 | 728,0 | 2,7 | Requiere ajuste: perfil sobre línea piezométrica |
| C5-1-1 | quebrada | 89,14 | 361,1 | 2,6 | Aceptable bajo supuesto de 1 m enterrado |

Las quebradas presentan mayor salto, pero su caudal bajo y posible circulación subterránea impiden asumir los escenarios como realizables. La alternativa C4 se mantiene exploratoria porque el trazado calculado supera localmente la línea piezométrica, incluso con 1 m de enterramiento supuesto. Debe ajustarse el trazado o la profundidad antes de considerarse viable.

Los tramos se analizan por separado cuando salen del deslinde o de la cobertura DTM. No se conecta una captación y una descarga de cauces diferentes, ni se autorizan pasos fuera del predio. Los cursos 2 y 3 están fuera del deslinde en sus sectores con DTM; el curso 6 no tiene DTM útil para el estudio.

## Método SIG y trazado

GeoPandas/Shapely leen SHP y polígonos KML; Rasterio muestrea el DTM nativo de 0,25618 m/píxel. Se usan EPSG:32718 para distancias y EPSG:4326 para los vectores web. El DTM, DSM y ortomosaicos originales están en UTM 18S; no se reescriben los grandes raster originales. Las vistas raster web se reproyectan a Web Mercator con límites WGS84 para Leaflet. La precisión del píxel no equivale a precisión vertical del levantamiento.

En cada tramo continuo del cauce dentro del predio y con DTM se muestrea a unos 2 m y se busca una pareja alto/bajo ordenada según sentido inferido de las cotas. Se aplica mediana de cinco muestras sólo para localizar extremos; las cotas finales se consultan al DTM. Se ubica una cámara conceptual a 6–30 m de la captación con descenso mínimo de 0,3 m cuando existe. La aducción sigue el cauce entre ambos puntos.

El trazado de presión usa Dijkstra en grilla de 2 m con ocho vecinos, penalizando pendientes e interiores de lotes. Los caminos tienen costo base 1; bandas de 4 m de linderos, 1,3; resto libre, 4; interior de lotes, 25. Se limita la ruta a cobertura DTM dentro del predio y bajo el nivel de cámara (tolerancia 0,3 m). Se revisan posteriormente cruces de lotes y línea piezométrica. No se ha comprobado que las bandas de lindero tengan servidumbre o aptitud constructiva. El largo 3D usa perfil muestreado aproximadamente cada 2 m.

La propuesta se selecciona entre arroyos permanentes con comprobación piezométrica preliminar aceptable, priorizando cruce interior menor de 10 m y luego máximo Hb entre las alternativas candidatas. No se enumeran todas las posiciones posibles ni se demuestra optimalidad global. El perfil supone 1 m de enterramiento; no modela golpe de ariete, inundaciones, geotecnia ni pérdidas particulares de una obra diseñada.

Curvas de nivel con intervalo de 1 m, color por Elevation y simplificación web de 0,75 m. Los ortomosaicos se reducen para visualización; sus originales se conservan. El DSM se inspeccionó como superficie y no se usa para definir niveles hidráulicos, evitando confundir copas/estructuras con terreno.

## Verificación y decisión siguiente

Se verificaron cálculo independiente de pérdidas/potencias/energía, CRS, longitudes, trazado base dentro del deslinde, ausencia de cruce interior de lotes y KMZ con tres puntos y dos líneas. El navegador se prueba con selección de caudales y alternativas. El archivo HTML incorpora vectores, imágenes y descargas; Leaflet/Folium y los fondos externos requieren Internet. El servicio de cartografía puede estar indisponible: las ortofotos propias permiten revisar el sector levantado.

Para decidir inversión: aforos en estiaje y serie estacional, niveles de agua y perfil topográfico independiente, alineación real de los cauces, caudal derivable, sedimentos, crecidas, restitución, emplazamiento de sala en margen segura y acceso. Revisar situación de uso del agua y autorizaciones aplicables con los antecedentes del proyecto. Sin estas comprobaciones no se confirma factibilidad técnica ni económica.

## Referencias

- [EPA, EPANET](https://www.epa.gov/water-research/epanet): metodología de pérdidas distribuidas y locales; plástico nuevo C 140–150.
- [DOE, Types of Hydropower Turbines](https://www.energy.gov/cmei/water/types-hydropower-turbines): relación entre salto, caudal y familias de turbina. La elección final debe contrastarse con fabricante.

## Archivos y reproducción

Abrir `index.html` en un navegador con Internet. La descarga KMZ/CSV desde el mapa siempre corresponde a la **propuesta base C1-2-1**, aunque se explore otra alternativa. Los resultados de todas las alternativas están en `outputs/results.json` y sus rutas en `outputs/alternativas.geojson`.

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
