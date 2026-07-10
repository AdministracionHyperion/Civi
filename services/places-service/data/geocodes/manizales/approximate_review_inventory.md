# Inventario Manizales aproximadas — geometría oficial NOMENCLATURA PREDIAL

**CSV canónico no modificado.** Coordenadas finales propuestas salen del Geoportal (o interpolación municipal documentada), no del geocodificador secundario.

Servicio: `https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10`
Consulta: `2026-07-10T19:50:10Z`

Privacidad del extracto: solo OBJECTID, dirección, geometría mínima (centroide), coordenada representativa, consulta, fecha, distancias y fórmula.

## Tabla final

| ID | Dirección RUNT | Actual | Secundaria | Geoportal/interpolación | Tipo | OBJECTIDs | Estado recomendado | Motivo |
|---|---|---|---|---|---|---|---|---|
| `cda-manizales-cda-caldas-el-bosque-a730920403` | CALLE 12 # 30 32 | 5.06231775,-75.52377055 | 5.061935,-75.5238599 | 5.0619511,-75.5239771 | `exact` | 32634 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `cda-manizales-cda-socicar-7acac31f0f` | AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS | 5.0694483,-75.5235525 | — | 5.069587,-75.5231293 | `interpolated` | 80316,80293 | `candidate_approximate_or_address_via_municipal_interpolation` | Av. 19 RUNT = K 19 municipal. Interpolación OBJECTID 80316 (K 19 13 41) → 80293 (K 19 13 45 47) hacia placa 44; t=(44-41)/(45-41)=0.75. Locales no confirmados. |
| `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c` | CARRERA 24 # 32 - 49 BRR FUNDADORES | 5.0667186,-75.5111711 | 5.066789,-75.5108139 | 5.0668589,-75.5108467 | `exact` | 52874 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `cea-manizales-academia-automovilistica-caldas-sas-12d613c393` | CARRERA 23 NRO 53A 25 | 5.062466632954545,-75.49477705814394 | — | 5.0626837,-75.4949458 | `exact_range_includes_plate` | 26301 | `candidate_for_confirmed_address_using_geoportal_geometry` | OBJECTID 26301 dirección municipal K 23 53A 25 27 incluye la placa RUNT 25; punto representativo del predio. |
| `cea-manizales-academia-automovilistica-piloto-177f760536` | CARRERA 21 NO. 15-40 | 5.0681641,-75.5221452 | 5.0682222,-75.5217211 | 5.0680482,-75.5217908 | `interpolated` | 80394,80393 | `candidate_approximate_or_address_via_municipal_interpolation` | Interpolación entre placas 38 y 44 sobre K 21 15 (no existe predio exacto 15-40). |
| `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0` | CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER | 5.05390085,-75.47652575000001 | 5.0517,-75.4844 | 5.0518408,-75.4841049 | `interpolated` | 105038,105040 | `approximate_not_confirmed_with_corrected_municipal_interpolation` | Interpolación forzada OBJECTID 105038 (K 23 70 55) → 105040 (K 23 70 75); t=(59-55)/(75-55)=0.20. Descartados 96475/52515. Mantener approximate_not_confirmed salvo predio exacto. |
| `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930` | CRA 24 53-20 | 5.0630767,-75.4962899 | 5.062863,-75.4961049 | 5.062791,-75.4962457 | `exact` | 14593 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e` | CALLE 21 # 19 - 27 CENTRO | 5.069294909977283,-75.51837825910042 | 5.069402,-75.5182809 | 5.0693862,-75.5180932 | `exact` | 27405 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047` | CARRERA 20 NO.21-40 | 5.069090011353712,-75.51802856550218 | 5.0689636,-75.5181746 | 5.0692599,-75.5179778 | `interpolated` | 27319,27346 | `candidate_approximate_or_address_via_municipal_interpolation` | Interpolación OBJECTID 27319 (K 20 21 35) → 27346 (K 20 21 51); t=(40-35)/(51-35)=0.3125. |
| `cia-manizales-cimyc-manizales-s-a-s-498175000a` | CARRERA 19 #64A-19A | 5.05813485,-75.48422695 | — | — | `insufficient` | — | `keep_approximate_insufficient_evidence` | Sin evidencia de punto exacto en esta ronda. |
| `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d` | CALLE 22 NO. 18-29 PISO 2 | 5.0702978,-75.5177831 | 5.070056,-75.5177019 | 5.0700727,-75.5176819 | `exact_range_includes_plate` | 27245,68601 | `address_confirmed_operational_review_pending_no_coord_change` | Dirección: OBJECTID 27245/68601 C 22 18 23 29 incluye placa 29. Operación: revisión de vigencia RUNT 2.0 pendiente; no cambiar coords/estado CSV. |
| `crc-manizales-certificamos-agustinos-98839ab670` | CRA 19 18-27 LC 3/3-1 | 5.069385,-75.5203143 | — | 5.0700344,-75.5198595 | `building_address_confirmed_local_not_confirmed` | 81323,81326,81333,81334 | `building_address_confirmed_local_and_merge_not_confirmed` | OBJECTID 81323/81326/81333/81334 confirman edificio/dirección base K 19 18 27; RUNT usa otro local (LC 3/3-1 vs L COMERCIAL 7). No confirmar local ni fusionar establecimientos. |

## 1. CDA CALDAS EL BOSQUE (CDA)

- **ID:** `cda-manizales-cda-caldas-el-bosque-a730920403`
- **Dirección RUNT:** CALLE 12 # 30 32
- **Actual:** 5.06231775, -75.52377055
- **Secundaria:** {'lat': 5.061935, 'lng': -75.5238599}
- **Geoportal/interpolación:** 5.0619511, -75.5239771
- **Tipo:** `exact`
- **OBJECTIDs:** [32634]
- **Fórmula:** None
- **Dist. a actual:** 46.7 m
- **Dist. a secundaria:** 13.1 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27C+12+30+32%27']

## 2. CDA SOCICAR (CDA)

- **ID:** `cda-manizales-cda-socicar-7acac31f0f`
- **Dirección RUNT:** AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS
- **Actual:** 5.0694483, -75.5235525
- **Secundaria:** None
- **Geoportal/interpolación:** 5.069587, -75.5231293
- **Tipo:** `interpolated`
- **OBJECTIDs:** [80316, 80293]
- **Fórmula:** (44-41)/(45-41)=0.75
- **Dist. a actual:** 49.3 m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `candidate_approximate_or_address_via_municipal_interpolation`
- **Motivo:** Av. 19 RUNT = K 19 municipal. Interpolación OBJECTID 80316 (K 19 13 41) → 80293 (K 19 13 45 47) hacia placa 44; t=(44-41)/(45-41)=0.75. Locales no confirmados.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID+IN+%2880316%2C80293%29', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+19+13+41%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+19+13+45+47%27']

## 3. CENTRO DE DIAGNOSTICO AUTOMOTOR MOTOLINARES (CDA)

- **ID:** `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c`
- **Dirección RUNT:** CARRERA 24 # 32 - 49 BRR FUNDADORES
- **Actual:** 5.0667186, -75.5111711
- **Secundaria:** {'lat': 5.066789, 'lng': -75.5108139}
- **Geoportal/interpolación:** 5.0668589, -75.5108467
- **Tipo:** `exact`
- **OBJECTIDs:** [52874]
- **Fórmula:** None
- **Dist. a actual:** 39.2 m
- **Dist. a secundaria:** 8.6 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27CR+24+32+49%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+24+32+49%27']

## 4. ACADEMIA AUTOMOVILISTICA CALDAS SAS (CEA)

- **ID:** `cea-manizales-academia-automovilistica-caldas-sas-12d613c393`
- **Dirección RUNT:** CARRERA 23 NRO 53A 25
- **Actual:** 5.062466632954545, -75.49477705814394
- **Secundaria:** None
- **Geoportal/interpolación:** 5.0626837, -75.4949458
- **Tipo:** `exact_range_includes_plate`
- **OBJECTIDs:** [26301]
- **Fórmula:** None
- **Dist. a actual:** 30.5 m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** OBJECTID 26301 dirección municipal K 23 53A 25 27 incluye la placa RUNT 25; punto representativo del predio.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+23+53A+25+27%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID+IN+%2826301%29']

## 5. ACADEMIA AUTOMOVILISTICA PILOTO (CEA)

- **ID:** `cea-manizales-academia-automovilistica-piloto-177f760536`
- **Dirección RUNT:** CARRERA 21 NO. 15-40
- **Actual:** 5.0681641, -75.5221452
- **Secundaria:** {'lat': 5.0682222, 'lng': -75.5217211}
- **Geoportal/interpolación:** 5.0680482, -75.5217908
- **Tipo:** `interpolated`
- **OBJECTIDs:** [80394, 80393]
- **Fórmula:** (40-38)/(44-38)=0.3333
- **Dist. a actual:** 41.3 m
- **Dist. a secundaria:** 20.8 m
- **Estado recomendado:** `candidate_approximate_or_address_via_municipal_interpolation`
- **Motivo:** Interpolación entre placas 38 y 44 sobre K 21 15 (no existe predio exacto 15-40).
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID+IN+%2880394%2C80393%29', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+21+15+38%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27K+21+15+44%25%27&resultRecordCount=20']

## 6. CEA PRACTICAR DEL EJE - MANIZALES (CEA)

- **ID:** `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0`
- **Dirección RUNT:** CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER
- **Actual:** 5.05390085, -75.47652575000001
- **Secundaria:** {'lat': 5.0517, 'lng': -75.4844}
- **Geoportal/interpolación:** 5.0518408, -75.4841049
- **Tipo:** `interpolated`
- **OBJECTIDs:** [105038, 105040]
- **Fórmula:** (59-55)/(75-55)=0.20
- **Dist. a actual:** 870.2 m
- **Dist. a secundaria:** 36.2 m
- **Estado recomendado:** `approximate_not_confirmed_with_corrected_municipal_interpolation`
- **Motivo:** Interpolación forzada OBJECTID 105038 (K 23 70 55) → 105040 (K 23 70 75); t=(59-55)/(75-55)=0.20. Descartados 96475/52515. Mantener approximate_not_confirmed salvo predio exacto.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID+IN+%28105038%2C105040%29', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+23+70+55%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27K+23+70+75%25%27&resultRecordCount=20']

## 7. CENTRO DE ENSEÑANZA AUTOMOVILISTICA CALDAS (CEA)

- **ID:** `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930`
- **Dirección RUNT:** CRA 24 53-20
- **Actual:** 5.0630767, -75.4962899
- **Secundaria:** {'lat': 5.062863, 'lng': -75.4961049}
- **Geoportal/interpolación:** 5.062791, -75.4962457
- **Tipo:** `exact`
- **OBJECTIDs:** [14593]
- **Fórmula:** None
- **Dist. a actual:** 32.1 m
- **Dist. a secundaria:** 17.5 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+24+53+20%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+24+53+20+K+25%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27CR+24+53+20%27']

## 8. CENTRO INTEGRAL DE ATENCION RUTAS DE COLOMBIA (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e`
- **Dirección RUNT:** CALLE 21 # 19 - 27 CENTRO
- **Actual:** 5.069294909977283, -75.51837825910042
- **Secundaria:** {'lat': 5.069402, 'lng': -75.5182809}
- **Geoportal/interpolación:** 5.0693862, -75.5180932
- **Tipo:** `exact`
- **OBJECTIDs:** [27405]
- **Fórmula:** None
- **Dist. a actual:** 33.2 m
- **Dist. a secundaria:** 20.9 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27C+21+19+27%27']

## 9. CENTRO INTEGRAL DE ATENCIÓN EJE CAFETEROS S.A.S (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047`
- **Dirección RUNT:** CARRERA 20 NO.21-40
- **Actual:** 5.069090011353712, -75.51802856550218
- **Secundaria:** {'lat': 5.0689636, 'lng': -75.5181746}
- **Geoportal/interpolación:** 5.0692599, -75.5179778
- **Tipo:** `interpolated`
- **OBJECTIDs:** [27319, 27346]
- **Fórmula:** (40-35)/(51-35)=0.3125
- **Dist. a actual:** 19.7 m
- **Dist. a secundaria:** 39.5 m
- **Estado recomendado:** `candidate_approximate_or_address_via_municipal_interpolation`
- **Motivo:** Interpolación OBJECTID 27319 (K 20 21 35) → 27346 (K 20 21 51); t=(40-35)/(51-35)=0.3125.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID+IN+%2827319%2C27346%29', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27K+20+21+35%25%27&resultRecordCount=20', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+20+21+51%27']

## 10. CIMYC MANIZALES S.A.S (CIA)

- **ID:** `cia-manizales-cimyc-manizales-s-a-s-498175000a`
- **Dirección RUNT:** CARRERA 19 #64A-19A
- **Actual:** 5.05813485, -75.48422695
- **Secundaria:** None
- **Geoportal/interpolación:** None, None
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **Fórmula:** None
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `keep_approximate_insufficient_evidence`
- **Motivo:** Sin evidencia de punto exacto en esta ronda.
- **URLs:** []

## 11. CENTRO DE RECONOCIMIENTO DE CONDUCTORES EVALUANDO MANIZALES (CRC)

- **ID:** `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d`
- **Dirección RUNT:** CALLE 22 NO. 18-29 PISO 2
- **Actual:** 5.0702978, -75.5177831
- **Secundaria:** {'lat': 5.070056, 'lng': -75.5177019}
- **Geoportal/interpolación:** 5.0700727, -75.5176819
- **Tipo:** `exact_range_includes_plate`
- **OBJECTIDs:** [27245, 68601]
- **Fórmula:** None
- **Dist. a actual:** 27.4 m
- **Dist. a secundaria:** 2.9 m
- **Estado recomendado:** `address_confirmed_operational_review_pending_no_coord_change`
- **Motivo:** Dirección: OBJECTID 27245/68601 C 22 18 23 29 incluye placa 29. Operación: revisión de vigencia RUNT 2.0 pendiente; no cambiar coords/estado CSV.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27C+22+18+23+29%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID+IN+%2827245%2C68601%29']

## 12. CERTIFICAMOS AGUSTINOS (CRC)

- **ID:** `crc-manizales-certificamos-agustinos-98839ab670`
- **Dirección RUNT:** CRA 19 18-27 LC 3/3-1
- **Actual:** 5.069385, -75.5203143
- **Secundaria:** None
- **Geoportal/interpolación:** 5.0700344, -75.5198595
- **Tipo:** `building_address_confirmed_local_not_confirmed`
- **OBJECTIDs:** [81323, 81326, 81333, 81334]
- **Fórmula:** None
- **Dist. a actual:** 88.0 m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `building_address_confirmed_local_and_merge_not_confirmed`
- **Motivo:** OBJECTID 81323/81326/81333/81334 confirman edificio/dirección base K 19 18 27; RUNT usa otro local (LC 3/3-1 vs L COMERCIAL 7). No confirmar local ni fusionar establecimientos.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+19+18+27+L+COMERCIAL+7%27']
