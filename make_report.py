import json, shutil, zipfile
from pathlib import Path
ROOT=Path(__file__).parent;OUT=ROOT/'outputs';DIST=ROOT/'sites/la-cantina-hidro/dist'
r=json.loads((OUT/'results.json').read_text(encoding='utf8'));c=r['selected']
f=lambda x,n=2:f'{x:,.{n}f}'.replace(',','X').replace('.',',').replace('X','.')
rows='\n'.join(f"| {s['q_ls']} | {f(s['diameter_in'],1)} | {f(s['hf_m'],3)} | {f(s['hm_m'],3)} | {f(s['net_head_m'])} | {f(s['power_kw'])} | {f(s['monthly_kwh'],0)} | {f(s['annual_kwh'],0)} |" for s in r['scenarios'])
points='\n'.join(f"| {name} | {c['points_wgs84'][key][1]:.7f} | {c['points_wgs84'][key][0]:.7f} | {f(c[z])} |" for name,key,z in [('Bocatoma','intake','intake_z'),('Cámara de carga','chamber','chamber_z'),('Turbina / restitución','tail','tail_z')])
alts='\n'.join(f"| {a['id']} | {a['stream_name']} · P{a['priority']} | {f(a['hb'])} | {f(a['length_m'],1)} | {f(a['outside_property_plan_m'],1)} | {f(a['interior_crossing_m'],1)} | {'Aceptable con diámetros corregidos y 1 m enterrado' if a['hgl_ok'] else 'Requiere ajuste de perfil'} |" for a in r['alternatives'])
inventory='\n'.join(f"| {s['stream_id']} | {s['stream_name']} | {s['priority']} | {f(s['total_length_m'],1)} | {f(s['dtm_valid_length_m'],1)} | {f(s['dtm_coverage_pct'],1)}% |" for s in r['stream_inventory'])
text=f'''# La Cantina — Apéndice de potencial hidroeléctrico amplio

Revisión 3 — 19 de octubre de 2026. **Arroyo norte incluido; cauces y curvas sin recorte predial. CAMINOS hipotéticos excluidos del cálculo.** Este apéndice conserva el potencial de mayor salto; la propuesta pequeña recomendada y el acceso nuevo están en [PROPUESTA_ACCESO_MICROHIDRO.md](PROPUESTA_ACCESO_MICROHIDRO.md).

Esta revisión sustituye la selección anterior de 13,23 m de salto. El deslinde se usa como referencia para identificar obras dentro/fuera, no como límite de exclusión del recurso. Se priorizan los arroyos permanentes; las quebradas no permanentes se conservan sólo en última prioridad, según la aclaración del propietario de que acceder al agua requeriría perforar.

## Resultado principal

Se identifica la alternativa **{c['id']} en el {c['stream_name']} (ID {c['stream_id']})**, reportado como permanente por el propietario. Presenta **{f(c['hb'])} m de salto bruto**, {f(c['adduction_length_m'],1)} m de aducción y **{f(c['length_m'],1)} m de tubería de presión 3D** ({f(c['length_plan_m'],1)} m en planta). La ruta prioriza linderos y caminos y no cruza interiores de lotes a más de 4 m del lindero. Las cotas y geometría requieren verificación de campo; no es un emplazamiento de obra aprobado ni una solución óptima global.

**Obras exteriores al deslinde original:** {f(c['outside_property_plan_m'],1)} m de tubería en planta ({f(c['outside_property_pct'],1)}% de la ruta) y {f(c['adduction_outside_property_m'],1)} m de aducción. El visor marca estos tramos en rojo discontinuo; los puntos indican individualmente si quedan dentro o fuera. La propuesta requiere validar acceso y tenencia en esos sectores, además de los antecedentes de uso del agua. Incluirlos en la evaluación no acredita disponibilidad para construir.

La subdivisión contiene diez lotes, con {f(r['metadata']['lots_area_ha'])} ha. El polígono CAMINOS se conserva sólo como insumo original; no se usa ni se muestra como camino existente. El deslinde original abarca {f(r['metadata']['property_area_ha'])} ha. La cobertura DTM calculada a 2 m alcanza **{f(r['metadata']['dem_coverage_pct'],1)}% del deslinde**. El área DTM válida total analizada es {f(r['metadata']['dtm_full_area_ha'])} ha, incluyendo topografía exterior al predio. Se conservan las 512 curvas completas y los seis cauces; no se extrapola potencial donde falta DTM.

## Inventario completo de cauces

| ID | Cauce | Prioridad | Longitud total (m) | Longitud con DTM (m) | Cobertura lineal DTM |
|---:|---|---:|---:|---:|---:|
{inventory}

El arroyo norte corresponde al ID 2. El ID 6 también queda visible y registrado como permanente, pero sin topografía suficiente para calcular salto o potencia. Las longitudes con DTM se estiman en un muestreo de unos 2 m; no indican que todo el cauce esté levantado.

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

Familia sugerida para la base: **{r['scenarios'][2]['turbine']}**, con salto neto de {f(r['scenarios'][2]['net_head_m'])} m a 50 L/s. La selección es una inferencia de prefactibilidad por el alto salto y los caudales analizados, pendiente de curvas de fabricante y rendimiento a carga parcial. No se acredita un caudal de diseño por la sola declaración de permanencia.

## Balance hidráulico

- Hb = cota captación − cota turbina = {f(c['hb'])} m.
- Salto cámara–turbina = {f(c['penstock_head'])} m.
- El descenso captación–cámara ({f(c['hb']-c['penstock_head'])} m) se descuenta: la cámara de lámina libre interrumpe la carga de captación.
- hf = 10,67 × L × Q^1,852 / (C^1,852 × D^4,8704), en SI.
- C = 145 para plástico nuevo; K accesorios = 3 supuesto.
- hm = K × v² / (2g); Hn = Hb − descenso de aducción − hf − hm.
- P = 9,81 × Q × Hn × 0,65; E anual = P × 8.760 × 0,80.

Se elige el menor diámetro de la serie 2 a 24 pulgadas interiores que limita hf a 10% de Hb, hf+hm a 10% del salto cámara–turbina y velocidad a 3 m/s, y que conserva el eje de tubería bajo la línea piezométrica a lo largo del perfil. Para ello se supone enterramiento de 1 m. En la meseta inicial del arroyo norte, el criterio de presión exige diámetros mayores que el límite de pérdidas por sí solo; se verifica cada caudal por separado. La comprobación preliminar distribuye la fricción uniformemente y considera las pérdidas locales al final del balance; no sustituye el modelo hidráulico detallado de accesorios.

La presión estática máxima aproximada sobre el eje enterrado es de **{f(c['max_static_pressure_bar'])} bar**, sin golpe de ariete. Es un dimensionamiento hidráulico preliminar, no una optimización de costo. Para HDPE/PVC se debe seleccionar diámetro exterior/SDR/PN y recalcular con el diámetro interior real, presión de trabajo y transitorios. Faltan aducción, cámara/desarenador, válvulas y anclajes.

## Alternativas revisadas

| ID | Cauce / prioridad | Hb (m) | Tubería 3D (m) | Tubería exterior en planta (m) | Cruce interior (m) | Revisión piezométrica |
|---|---|---:|---:|---:|---:|---|
{alts}

**Las quebradas son de última prioridad y quedan excluidas de la selección principal.** El propietario aclara que no son de escurrimiento permanente y que acceder al agua requeriría perforar. Sus escenarios 10–100 L/s y energía al 80% son sólo referencias matemáticas, sin recurso aprovechable acreditado. No se modelan reserva subterránea, perforaciones ni consumo de bombeo; por tanto no representan producción hidroeléctrica neta disponible. La corrección del diámetro puede mejorar el perfil piezométrico, pero no resuelve esa falta de recurso hídrico acreditado.

Los tramos se separan sólo cuando se interrumpe la cobertura DTM, no al cruzar el deslinde. Cada captación y restitución se mantienen en el mismo cauce; no se suman caudales de cursos diferentes. Los cursos 2 y 3 se incluyen aunque discurran fuera del deslinde. El curso 6 queda visible y pendiente de topografía. Las longitudes de obras exteriores se exportan en `outputs/tramos_fuera_deslinde.geojson`.

## Método SIG y trazado

GeoPandas/Shapely leen SHP y polígonos KML; Rasterio muestrea el DTM nativo de 0,25618 m/píxel. Se usan EPSG:32718 para distancias y EPSG:4326 para los vectores web. El DTM, DSM y ortomosaicos originales están en UTM 18S; no se reescriben los grandes raster originales. Las vistas raster web se reproyectan a Web Mercator con límites WGS84 para Leaflet. La precisión del píxel no equivale a precisión vertical del levantamiento.

En cada tramo continuo del cauce con DTM válido, dentro o fuera del predio, se muestrea a unos 2 m y se busca una pareja alto/bajo ordenada según sentido inferido de las cotas. Se aplica mediana de cinco muestras sólo para localizar extremos; las cotas finales se consultan al DTM. Se ubica una cámara conceptual a 6–30 m de la captación con descenso mínimo de 0,3 m cuando existe. La aducción sigue el cauce entre ambos puntos.

El trazado usa Dijkstra en grilla de 2 m con ocho vecinos, penalizando pendientes e interiores de lotes. Bandas de 4 m de linderos: costo 1,3; resto libre, 4; interior de lotes, 25. CAMINOS hipotéticos no participan del costo ni del trazado. Se limita la ruta al DTM válido y bajo el nivel de cámara (tolerancia 0,3 m), sin usar el deslinde como barrera. Se revisan cruces de lotes, longitud exterior y línea piezométrica. No se han comprobado servidumbres ni aptitud constructiva. El largo 3D usa el perfil muestreado aproximadamente cada 2 m.

La propuesta se selecciona entre arroyos permanentes con comprobación piezométrica preliminar aceptable, priorizando cruce interior menor de 10 m y luego máximo Hb entre las alternativas candidatas. No se enumeran todas las posiciones posibles ni se demuestra optimalidad global. El perfil supone 1 m de enterramiento; no modela golpe de ariete, inundaciones, geotecnia ni pérdidas particulares de una obra diseñada.

Curvas con intervalo de 1 m, color por Elevation y simplificación web de 0,75 m, sin recorte por deslinde. Se exportan además sin simplificar en `outputs/curvas_completas.geojson`. Los seis cauces de `hidro.shp` se exportan completos. Los ortomosaicos se reducen para web y se muestra por defecto el completo para incluir el norte. El DSM no define niveles hidráulicos: se usa el DTM de terreno.

## Verificación y decisión siguiente

Se verifican independientemente pérdidas/potencias/energía y perfil piezométrico de todas las alternativas, longitud exterior al deslinde, ausencia de cruce interior en la base y KMZ por alternativa con tres puntos y dos líneas. La regresión exige conservar los seis cauces y las 512 curvas completas, incluir más de 600 m del arroyo norte con DTM y dejar quebradas en última prioridad. El navegador se prueba con caudales, selección y descargas. El HTML incorpora vectores, imágenes y descargas; las bibliotecas y fondos externos requieren Internet.

Para decidir inversión: aforos en estiaje y serie estacional, niveles de agua y perfil topográfico independiente, alineación real de los cauces, caudal derivable, sedimentos, crecidas, restitución, emplazamiento de sala en margen segura y acceso. Revisar situación de uso del agua y autorizaciones aplicables con los antecedentes del proyecto. Sin estas comprobaciones no se confirma factibilidad técnica ni económica.

## Referencias

- [EPA, EPANET](https://www.epa.gov/water-research/epanet): metodología de pérdidas distribuidas y locales; plástico nuevo C 140–150.
- [DOE, Types of Hydropower Turbines](https://www.energy.gov/cmei/water/types-hydropower-turbines): relación entre salto, caudal y familias de turbina. La elección final debe contrastarse con fabricante.

## Archivos y reproducción

Abrir `index.html` en un navegador con Internet. Las descargas KMZ/CSV del mapa corresponden a la **alternativa seleccionada**. La exportación `outputs/la_cantina_propuesta.kmz` corresponde a la nueva base **{c['id']}**. Hay KMZ por candidato, `outputs/escenarios_todas_alternativas.csv`, `outputs/inventario_cauces.json`, resultados en `outputs/results.json` y rutas en `outputs/alternativas.geojson`.

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
(ROOT/'APENDICE_POTENCIAL.md').write_text(text.replace('prioriza linderos y caminos','prioriza linderos'),encoding='utf8')
shutil.copy2(ROOT/'APENDICE_POTENCIAL.md',DIST/'APENDICE_POTENCIAL.md')
files=['analyze.py','build_viewer.py','hydraulics.py','inspect_data.py','verify_outputs.py','verify_planning.py','make_report.py','viewer_panel.html','planning_panel.html','planning_map.py','planning_finance.py','planning_report.py','small_hydro.py','road_plan.py','fit_rotonda.py','requirements-lock.txt','INFORME_PREFACTIBILIDAD.md','PROPUESTA_ACCESO_MICROHIDRO.md','APENDICE_POTENCIAL.md','README.md','index.html']
with zipfile.ZipFile(ROOT/'la_cantina_estudio.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in files:z.write(ROOT/name,name)
    for p in OUT.iterdir():
        if p.suffix in ['.geojson','.json','.csv','.png','.kmz'] and p.name!='publicacion.json':z.write(p,'outputs/'+p.name)
    for pattern in ('*.kml','*.shp','*.shx','*.dbf','*.prj','*.cpg'):
        for p in ROOT.glob(pattern):z.write(p,p.name)
print('Informe y paquete de estudio generados.')
