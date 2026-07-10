# Inventario Manizales aproximadas — geometría oficial NOMENCLATURA PREDIAL

> **CSV canónico actualizado** en ix/manizales-geocode-quality: 5 confirmed_address + 3 interpolaciones; quedan 7 pproximate_not_confirmed. Conteos 19/18/7.


**CSV canónico no modificado.** Punto representativo = centroide de área (shoelace) o `point_on_surface` si el centroide cae fuera.

Servicio: `https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10`
Consulta: `2026-07-10T20:19:46Z`

Privacidad: solo OBJECTID, dirección, geometría mínima, coordenada representativa, `derivation_method`, consulta, fecha, distancias y fórmula. Sin `outFields=*`.

## Conteos hipotéticos (si se aplicaran propuestas)

```json
{
  "current_csv_counts": {
    "approximate_not_confirmed": 12,
    "confirmed_address": 13,
    "confirmed_business": 19
  },
  "proposals_on_approximate_12": {
    "confirmed_address": 5,
    "approximate_not_confirmed": 7
  },
  "hypothetical_after_apply_proposals_only": {
    "confirmed_address": 18,
    "approximate_not_confirmed": 7,
    "confirmed_business": 19,
    "note": "Hipotético; CSV canónico no modificado."
  }
}
```

## Tabla final

| ID | Anterior | Recalculada | Δ m | Dentro polígono | OBJECTIDs | proposed_status | proposed_precision | Motivo |
|---|---|---|---:|---|---|---|---|---|
| `cda-manizales-cda-caldas-el-bosque-a730920403` | 5.0619511,-75.5239771 | 5.0619543,-75.5239713 | 0.73 | True | 32634 | `confirmed_address` | `building` | Predio oficial exacto; punto representativo verificado dentro del polígono. |
| `cda-manizales-cda-socicar-7acac31f0f` | 5.069587,-75.5231293 | 5.0695891,-75.5231314 | 0.33 | — | 80316,80293 | `approximate_not_confirmed` | `address_interpolation` | Interpolación K 19 13 41→45 47 hacia placa 44 documentada, pero sin evidencia oficial reproducible de que Avenida 19 RUNT ≡ K 19; proposed=approximate_not_confirmed. |
| `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c` | 5.0668589,-75.5108467 | 5.0668747,-75.5108309 | 2.48 | True | 52874 | `confirmed_address` | `building` | Predio oficial exacto; punto representativo verificado dentro del polígono. |
| `cea-manizales-academia-automovilistica-caldas-sas-12d613c393` | 5.0626837,-75.4949458 | 5.0627089,-75.4949577 | 3.1 | True | 26301 | `confirmed_address` | `building` | OBJECTID 26301 K 23 53A 25 27 incluye placa RUNT 25; punto representativo derivation_method=polygon_area_centroid, inside=True. |
| `cea-manizales-academia-automovilistica-piloto-177f760536` | 5.0680482,-75.5217908 | 5.0680434,-75.5217931 | 0.59 | — | 80394,80393 | `approximate_not_confirmed` | `address_interpolation` | Interpolación entre puntos representativos de placas 38 y 44 sobre K 21 15; t=0.333333 en [0,1]. Sin predio exacto 15-40. |
| `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0` | 5.0518408,-75.4841049 | 5.0518489,-75.4840936 | 1.54 | — | 105038,105040 | `approximate_not_confirmed` | `address_interpolation` | Interpolación OBJECTID 105038→105040; t=0.20. Mantener approximate_not_confirmed salvo predio exacto. Descartados 96475/52515. |
| `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930` | 5.062791,-75.4962457 | 5.0627826,-75.4962432 | 0.97 | True | 14593 | `confirmed_address` | `building` | Predio oficial exacto; punto representativo verificado dentro del polígono. |
| `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e` | 5.0693862,-75.5180932 | 5.0694094,-75.5181173 | 3.71 | True | 27405 | `confirmed_address` | `building` | Predio oficial exacto; punto representativo verificado dentro del polígono. |
| `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047` | 5.0692599,-75.5179778 | 5.0692235,-75.5179797 | 4.05 | — | 27319,27346 | `approximate_not_confirmed` | `address_interpolation` | Interpolación OBJECTID 27319 (K 20 21 35) → 27346 (K 20 21 51); t=0.3125. |
| `cia-manizales-cimyc-manizales-s-a-s-498175000a` | — | — | — | — | — | `approximate_not_confirmed` | `nearby_address_landmark` | Sin evidencia de punto exacto en esta ronda. |
| `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d` | 5.0700727,-75.5176819 | 5.0700864,-75.517688 | 1.67 | — | 27245,68601 | `approximate_not_confirmed` | `address` | Dirección: OBJECTID 27245/68601 incluyen placa 29. Operación: revisión RUNT 2.0 pendiente → proposed approximate_not_confirmed. |
| `crc-manizales-certificamos-agustinos-98839ab670` | 5.0700344,-75.5198595 | 5.0700367,-75.5198939 | 3.82 | — | 81323,81326,81333,81334 | `approximate_not_confirmed` | `nearby_address_landmark` | Edificio/dirección base K 19 18 27 confirmada (OBJECTID 81323–81334); local RUNT distinto y sin fusión. proposed=approximate_not_confirmed. |

## 1. CDA CALDAS EL BOSQUE (CDA)

- **ID:** `cda-manizales-cda-caldas-el-bosque-a730920403`
- **Dirección RUNT:** CALLE 12 # 30 32
- **Actual CSV:** 5.06231775, -75.52377055
- **Anterior auditoría:** {'lat': 5.0619511, 'lng': -75.5239771, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0619543, 'lng': -75.5239713}
- **Desplazamiento:** 0.73 m
- **Tipo:** `exact`
- **OBJECTIDs:** [32634]
- **derivation_method:** polygon_area_centroid
- **inside_official_polygon:** True
- **Fórmula:** None
- **csv_proposed_validation_status:** `confirmed_address`
- **csv_proposed_precision:** `building`
- **Motivo:** Predio oficial exacto; punto representativo verificado dentro del polígono.

## 2. CDA SOCICAR (CDA)

- **ID:** `cda-manizales-cda-socicar-7acac31f0f`
- **Dirección RUNT:** AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS
- **Actual CSV:** 5.0694483, -75.5235525
- **Anterior auditoría:** {'lat': 5.069587, 'lng': -75.5231293, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0695891, 'lng': -75.5231314}
- **Desplazamiento:** 0.33 m
- **Tipo:** `interpolated_audit_only`
- **OBJECTIDs:** [80316, 80293]
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** (44-41)/(45-41)=0.75
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `address_interpolation`
- **Motivo:** Interpolación K 19 13 41→45 47 hacia placa 44 documentada, pero sin evidencia oficial reproducible de que Avenida 19 RUNT ≡ K 19; proposed=approximate_not_confirmed.

## 3. CENTRO DE DIAGNOSTICO AUTOMOTOR MOTOLINARES (CDA)

- **ID:** `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c`
- **Dirección RUNT:** CARRERA 24 # 32 - 49 BRR FUNDADORES
- **Actual CSV:** 5.0667186, -75.5111711
- **Anterior auditoría:** {'lat': 5.0668589, 'lng': -75.5108467, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0668747, 'lng': -75.5108309}
- **Desplazamiento:** 2.48 m
- **Tipo:** `exact`
- **OBJECTIDs:** [52874]
- **derivation_method:** polygon_area_centroid
- **inside_official_polygon:** True
- **Fórmula:** None
- **csv_proposed_validation_status:** `confirmed_address`
- **csv_proposed_precision:** `building`
- **Motivo:** Predio oficial exacto; punto representativo verificado dentro del polígono.

## 4. ACADEMIA AUTOMOVILISTICA CALDAS SAS (CEA)

- **ID:** `cea-manizales-academia-automovilistica-caldas-sas-12d613c393`
- **Dirección RUNT:** CARRERA 23 NRO 53A 25
- **Actual CSV:** 5.062466632954545, -75.49477705814394
- **Anterior auditoría:** {'lat': 5.0626837, 'lng': -75.4949458, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0627089, 'lng': -75.4949577}
- **Desplazamiento:** 3.1 m
- **Tipo:** `exact_range_includes_plate`
- **OBJECTIDs:** [26301]
- **derivation_method:** polygon_area_centroid
- **inside_official_polygon:** True
- **Fórmula:** None
- **csv_proposed_validation_status:** `confirmed_address`
- **csv_proposed_precision:** `building`
- **Motivo:** OBJECTID 26301 K 23 53A 25 27 incluye placa RUNT 25; punto representativo derivation_method=polygon_area_centroid, inside=True.

## 5. ACADEMIA AUTOMOVILISTICA PILOTO (CEA)

- **ID:** `cea-manizales-academia-automovilistica-piloto-177f760536`
- **Dirección RUNT:** CARRERA 21 NO. 15-40
- **Actual CSV:** 5.0681641, -75.5221452
- **Anterior auditoría:** {'lat': 5.0680482, 'lng': -75.5217908, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0680434, 'lng': -75.5217931}
- **Desplazamiento:** 0.59 m
- **Tipo:** `interpolated`
- **OBJECTIDs:** [80394, 80393]
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** (40-38)/(44-38)=0.333333
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `address_interpolation`
- **Motivo:** Interpolación entre puntos representativos de placas 38 y 44 sobre K 21 15; t=0.333333 en [0,1]. Sin predio exacto 15-40.

## 6. CEA PRACTICAR DEL EJE - MANIZALES (CEA)

- **ID:** `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0`
- **Dirección RUNT:** CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER
- **Actual CSV:** 5.05390085, -75.47652575000001
- **Anterior auditoría:** {'lat': 5.0518408, 'lng': -75.4841049, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0518489, 'lng': -75.4840936}
- **Desplazamiento:** 1.54 m
- **Tipo:** `interpolated`
- **OBJECTIDs:** [105038, 105040]
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** (59-55)/(75-55)=0.20
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `address_interpolation`
- **Motivo:** Interpolación OBJECTID 105038→105040; t=0.20. Mantener approximate_not_confirmed salvo predio exacto. Descartados 96475/52515.

## 7. CENTRO DE ENSEÑANZA AUTOMOVILISTICA CALDAS (CEA)

- **ID:** `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930`
- **Dirección RUNT:** CRA 24 53-20
- **Actual CSV:** 5.0630767, -75.4962899
- **Anterior auditoría:** {'lat': 5.062791, 'lng': -75.4962457, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0627826, 'lng': -75.4962432}
- **Desplazamiento:** 0.97 m
- **Tipo:** `exact`
- **OBJECTIDs:** [14593]
- **derivation_method:** polygon_area_centroid
- **inside_official_polygon:** True
- **Fórmula:** None
- **csv_proposed_validation_status:** `confirmed_address`
- **csv_proposed_precision:** `building`
- **Motivo:** Predio oficial exacto; punto representativo verificado dentro del polígono.

## 8. CENTRO INTEGRAL DE ATENCION RUTAS DE COLOMBIA (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e`
- **Dirección RUNT:** CALLE 21 # 19 - 27 CENTRO
- **Actual CSV:** 5.069294909977283, -75.51837825910042
- **Anterior auditoría:** {'lat': 5.0693862, 'lng': -75.5180932, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0694094, 'lng': -75.5181173}
- **Desplazamiento:** 3.71 m
- **Tipo:** `exact`
- **OBJECTIDs:** [27405]
- **derivation_method:** polygon_area_centroid
- **inside_official_polygon:** True
- **Fórmula:** None
- **csv_proposed_validation_status:** `confirmed_address`
- **csv_proposed_precision:** `building`
- **Motivo:** Predio oficial exacto; punto representativo verificado dentro del polígono.

## 9. CENTRO INTEGRAL DE ATENCIÓN EJE CAFETEROS S.A.S (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047`
- **Dirección RUNT:** CARRERA 20 NO.21-40
- **Actual CSV:** 5.069090011353712, -75.51802856550218
- **Anterior auditoría:** {'lat': 5.0692599, 'lng': -75.5179778, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0692235, 'lng': -75.5179797}
- **Desplazamiento:** 4.05 m
- **Tipo:** `interpolated`
- **OBJECTIDs:** [27319, 27346]
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** (40-35)/(51-35)=0.3125
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `address_interpolation`
- **Motivo:** Interpolación OBJECTID 27319 (K 20 21 35) → 27346 (K 20 21 51); t=0.3125.

## 10. CIMYC MANIZALES S.A.S (CIA)

- **ID:** `cia-manizales-cimyc-manizales-s-a-s-498175000a`
- **Dirección RUNT:** CARRERA 19 #64A-19A
- **Actual CSV:** 5.05813485, -75.48422695
- **Anterior auditoría:** None
- **Recalculada:** None
- **Desplazamiento:** None m
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** None
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `nearby_address_landmark`
- **Motivo:** Sin evidencia de punto exacto en esta ronda.

## 11. CENTRO DE RECONOCIMIENTO DE CONDUCTORES EVALUANDO MANIZALES (CRC)

- **ID:** `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d`
- **Dirección RUNT:** CALLE 22 NO. 18-29 PISO 2
- **Actual CSV:** 5.0702978, -75.5177831
- **Anterior auditoría:** {'lat': 5.0700727, 'lng': -75.5176819, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0700864, 'lng': -75.517688}
- **Desplazamiento:** 1.67 m
- **Tipo:** `exact_range_includes_plate`
- **OBJECTIDs:** [27245, 68601]
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** None
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `address`
- **Motivo:** Dirección: OBJECTID 27245/68601 incluyen placa 29. Operación: revisión RUNT 2.0 pendiente → proposed approximate_not_confirmed.

## 12. CERTIFICAMOS AGUSTINOS (CRC)

- **ID:** `crc-manizales-certificamos-agustinos-98839ab670`
- **Dirección RUNT:** CRA 19 18-27 LC 3/3-1
- **Actual CSV:** 5.069385, -75.5203143
- **Anterior auditoría:** {'lat': 5.0700344, 'lng': -75.5198595, 'note': 'vertex_mean_from_commit_b78dcd6'}
- **Recalculada:** {'lat': 5.0700367, 'lng': -75.5198939}
- **Desplazamiento:** 3.82 m
- **Tipo:** `building_address_confirmed_local_not_confirmed`
- **OBJECTIDs:** [81323, 81326, 81333, 81334]
- **derivation_method:** None
- **inside_official_polygon:** None
- **Fórmula:** None
- **csv_proposed_validation_status:** `approximate_not_confirmed`
- **csv_proposed_precision:** `nearby_address_landmark`
- **Motivo:** Edificio/dirección base K 19 18 27 confirmada (OBJECTID 81323–81334); local RUNT distinto y sin fusión. proposed=approximate_not_confirmed.
