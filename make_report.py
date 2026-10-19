import json, shutil, zipfile
from pathlib import Path
ROOT=Path(__file__).parent;OUT=ROOT/'outputs';DIST=ROOT/'sites/la-cantina-hidro/dist'
r=json.loads((OUT/'results.json').read_text(encoding='utf8'));c=r['selected']
f=lambda x,n=2:f'{x:,.{n}f}'.replace(',','X').replace('.',',').replace('X','.')
rows='\n'.join(f"| {s['q_ls']} | {f(s['diameter_in'],1)} | {f(s['hf_m'],3)} | {f(s['hm_m'],3)} | {f(s['net_head_m'])} | {f(s['power_kw'])} | {f(s['monthly_kwh'],0)} | {f(s['annual_kwh'],0)} |" for s in r['scenarios'])
points='\n'.join(f"| {name} | {c['points_wgs84'][key][1]:.7f} | {c['points_wgs84'][key][0]:.7f} | {f(c[z])} |" for name,key,z in [('Bocatoma','intake','intake_z'),('Cámara de carga','chamber','chamber_z'),('Turbina / restitución','tail','tail_z')])
alts='\n'.join(f"| {a['id']} | {a['tipo']} | {f(a['hb'])} | {f(a['length_m'],1)} | {f(a['interior_crossing_m'],1)} | {'Aceptable bajo supuesto de 1 m enterrado' if a['hgl_ok'] else 'Requiere ajuste: perfil sobre línea piezométrica'} |" for a in r['alternatives'])
text=f'''# La Cantina — Prefactibilidad hidroeléctrica geoespacial

Fecha: 19 de octubre de 2026. Estudio preliminar con herramientas gratuitas y datos proporcionados por el propietario. Sin presupuesto de obras ni estudio de rentabilidad.

## Resultado principal

Se identifica la alternativa **{c['id']} en el arroyo 1**, reportado como permanente por el propietario. Presenta **{f(c['hb'])} m de salto bruto**, {f(c['adduction_length_m'],1)} m de aducción y **{f(c['length_m'],1)} m de tubería de presión 3D** ({f(c['length_plan_m'],1)} m en planta). La ruta sigue la banda junto al deslinde y no cruza interiores de lotes a más de 4 m del lindero. El tramo está junto al borde del levantamiento; las cotas y la geometría requieren verificación de campo. No es un emplazamiento de obra aprobado ni una solución óptima global.

La subdivisión contiene diez lotes y un camino vehicular, con {f(r['metadata']['lots_area_ha'])} ha de lotes. El deslinde original abarca {f(r['metadata']['property_area_ha'])} ha. La cobertura DTM calculada a 2 m alcanza **{f(r['metadata']['dem_coverage_pct'],1)}% del deslinde**. No se extrapola potencial al sector sin DTM.

## Coordenadas de referencia (EPSG:4326)

| Elemento | Latitud | Longitud | Cota terreno DTM (m) |
|---|---:|---:|---:|
{points}

Las coordenadas indican referencias conceptuales sobre el cauce. La casa de máquinas debe desplazarse y replantearse en una margen segura frente a crecidas, conservando la posibilidad de restitución. Las cotas de terreno se usan como aproximación de los niveles hidráulicos; no son niveles de agua medidos y el datum vertical no está certificado.

## Escenarios de generación de la propuesta base

| Q (L/s) | D interior (pulg.) | hf (m) | hm (m) | H neto (m) | P (kW) | kWh/mes medio | kWh/año |
|---:|---:|---:|---:|---:|---:|---:|---:|
{rows}

Los diámetros son **interiores idealizados de cálculo**, no diámetros nominales comerciales. Cada caudal usa un diámetro distinto: no son cuatro condiciones de una misma instalación. La energía supone factor de planta 80%, equivalente a 7.008 horas anuales a potencia nominal. La energía mensual es anual/12, no una predicción mensual. Los caudales 10/25/50/100 L/s se consideran disponibles en turbina; aún no hay aforos que acrediten caudal derivable o permanente.

Familia sugerida para la base: **Michell-Banki / Crossflow**, por el salto neto del orden de 11 m y el rango de caudal analizado. La selección es una inferencia de prefactibilidad, pendiente de curvas de fabricante y rendimiento a carga parcial. Pelton/Turgo se muestran como familias posibles en las alternativas de mayor salto. Francis no es la primera opción propuesta para esta escala y caudal incierto, sin excluir una evaluación específica de proveedor.

## Balance hidráulico

- Hb = cota captación − cota turbina = {f(c['hb'])} m.
- Salto cámara–turbina = {f(c['penstock_head'])} m.
- El descenso captación–cámara ({f(c['hb']-c['penstock_head'])} m) se descuenta: la cámara de lámina libre interrumpe la carga de captación.
- hf = 10,67 × L × Q^1,852 / (C^1,852 × D^4,8704), en SI.
- C = 145 para plástico nuevo; K accesorios = 3 supuesto.
- hm = K × v² / (2g); Hn = Hb − descenso de aducción − hf − hm.
- P = 9,81 × Q × Hn × 0,65; E anual = P × 8.760 × 0,80.

Se elige el menor diámetro de la serie 2 a 24 pulgadas interiores que limita hf a 10% de Hb, hf+hm a 10% del salto cámara–turbina y velocidad a 3 m/s. Es un dimensionamiento hidráulico preliminar, no una optimización de costo. Para HDPE/PVC se debe seleccionar diámetro exterior/SDR/PN y recalcular con el diámetro interior comercial. Falta diseñar la aducción, cámara/desarenador, válvulas, anclajes y presión transitoria.

## Alternativas revisadas

| ID | Régimen declarado | Hb (m) | Tubería 3D (m) | Cruce interior (m) | Revisión piezométrica |
|---|---|---:|---:|---:|---|
{alts}

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
'''
(ROOT/'INFORME_PREFACTIBILIDAD.md').write_text(text,encoding='utf8')
shutil.copy2(ROOT/'INFORME_PREFACTIBILIDAD.md',DIST/'INFORME_PREFACTIBILIDAD.md')
files=['analyze.py','build_viewer.py','hydraulics.py','inspect_data.py','verify_outputs.py','make_report.py','viewer_panel.html','requirements-lock.txt','INFORME_PREFACTIBILIDAD.md','index.html']
with zipfile.ZipFile(ROOT/'la_cantina_estudio.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in files:z.write(ROOT/name,name)
    for p in OUT.iterdir():
        if p.suffix in ['.geojson','.json','.csv','.png','.kmz','.log'] and '_web' not in p.name:z.write(p,'outputs/'+p.name)
print('Informe y paquete de estudio generados.')
