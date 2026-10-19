"""Cálculos SI de prefactibilidad. Los diámetros son INTERIORES, no nominales."""
from math import pi

ETA = 0.65
CAPACITY_FACTOR = 0.80
HW_C = 145.0  # Plástico nuevo: rango EPANET 140–150; valor intermedio.
MINOR_K = 3.0  # Hipótesis para entrada, codos y válvula; verificar diseño.
INTERNAL_DIAMETERS_IN = (2, 2.5, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 24)

def hazen_williams(q_m3s, diameter_m, length_m, c=HW_C):
    return 10.67 * length_m * q_m3s**1.852 / (c**1.852 * diameter_m**4.8704)

def scenario(q_ls, gross_head_m, penstock_head_m, length_m,
             terrain_profile=None, chamber_elevation_m=None, burial_depth_m=1.0):
    q = q_ls / 1000.0
    if min(gross_head_m, penstock_head_m, length_m) <= 0:
        raise ValueError('Se requieren salto y longitud positivos.')
    first_hydraulic=None
    for inches in INTERNAL_DIAMETERS_IN:
        d = inches * 0.0254
        velocity = 4 * q / (pi * d*d)
        hf = hazen_williams(q, d, length_m)
        hm = MINOR_K * velocity**2 / (2*9.81)
        # También limita pérdidas totales y velocidad para no presentar un
        # diámetro de fricción aceptable pero hidráulicamente inconveniente.
        if hf <= .10*gross_head_m and hf+hm <= .10*penstock_head_m and velocity <= 3:
            if first_hydraulic is None:first_hydraulic=(inches,d,velocity,hf,hm)
            # La pérdida total aceptable no basta: comprueba presión en cada
            # punto del perfil, incluidas las mesetas iniciales del arroyo norte.
            if terrain_profile is None:break
            if chamber_elevation_m is None:raise ValueError('Falta cota de cámara para comprobar perfil.')
            end=terrain_profile[-1]['distance_m']
            clear=min(chamber_elevation_m-hf*p['distance_m']/end-(p['terrain_m']-burial_depth_m) for p in terrain_profile)
            if clear>=0:break
    else:
        if first_hydraulic is None:raise ValueError('Ampliar la serie de diámetros interiores.')
        # Conserva un escenario explícitamente condicionado si ningún diámetro
        # de la serie resuelve el perfil: no lo declara viable.
        inches,d,velocity,hf,hm=first_hydraulic
    clearance=None
    if terrain_profile is not None:
        end=terrain_profile[-1]['distance_m']
        clearance=min(chamber_elevation_m-hf*p['distance_m']/end-(p['terrain_m']-burial_depth_m) for p in terrain_profile)
    hn = penstock_head_m - hf - hm
    power = 9.81*q*hn*ETA
    turbine = ('Pelton / Turgo' if hn >= 50 else
               'Turgo / Michell-Banki' if hn >= 30 else 'Michell-Banki (Crossflow)')
    return dict(q_ls=q_ls,diameter_in=inches,diameter_mm=d*1000,
                velocity_ms=velocity,hf_m=hf,hm_m=hm,
                adduction_drop_m=gross_head_m-penstock_head_m,
                gross_head_m=gross_head_m,penstock_head_m=penstock_head_m,
                net_head_m=hn,loss_pct=100*(hf+hm)/penstock_head_m,
                power_kw=power,annual_kwh=power*8760*CAPACITY_FACTOR,
                monthly_kwh=power*8760*CAPACITY_FACTOR/12,turbine=turbine,
                min_hgl_clearance_m=clearance,profile_ok=clearance is None or clearance>=0,
                burial_depth_m=burial_depth_m if terrain_profile is not None else None)

if __name__ == '__main__':
    # Verificaciones numéricas con comportamiento físico, independientes del SIG.
    h = hazen_williams(.05, .2, 300)
    assert hazen_williams(.10,.2,300) > 3.5*h
    assert abs(hazen_williams(.05,.2,600)-2*h) < 1e-10
    assert hazen_williams(.05,.4,300) < h/25
    for q in (10,25,50,100):
        s=scenario(q,80,79.5,500)
        assert 0 < s['net_head_m'] < 79.5
        assert s['loss_pct'] <= 10
        assert abs(s['annual_kwh']-s['monthly_kwh']*12) < 1e-7
    plateau=[dict(distance_m=0,terrain_m=180),dict(distance_m=125,terrain_m=180),dict(distance_m=700,terrain_m=10)]
    plain=scenario(100,170,170,700)
    constrained=scenario(100,170,170,700,plateau,180)
    assert constrained['diameter_in']>plain['diameter_in']
    assert constrained['profile_ok'] and constrained['min_hgl_clearance_m']>=0
    print('Verificaciones hidráulicas correctas.')
