# Inventario Manizales aproximadas — geometría oficial NOMENCLATURA PREDIAL

**CSV canónico no modificado.** Coordenadas finales propuestas salen del Geoportal (o interpolación municipal documentada), no del geocodificador secundario.

Servicio: `https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10`

## Tabla final

| ID | Dirección RUNT | Actual | Secundaria | Geoportal/interpolación | Tipo | OBJECTIDs | Estado recomendado | Motivo |
|---|---|---|---|---|---|---|---|---|
| `-cda-caldas-el-bosque-a730920403` | CALLE 12 # 30 32 | 5.06231775,-75.52377055 | 5.061935,-75.5238599 | 5.0619511,-75.5239771 | `exact` | 32634 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `manizales-cda-socicar-7acac31f0f` | AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS | 5.0694483,-75.5235525 | — | — | `insufficient` | — | `keep_approximate_insufficient_evidence` | Sin evidencia de punto exacto. |
| `co-automotor-motolina-0ce021ad5c` | CARRERA 24 # 32 - 49 BRR FUNDADORES | 5.0667186,-75.5111711 | 5.066789,-75.5108139 | 5.0668589,-75.5108467 | `exact` | 52874 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `ovilistica-caldas-sas-12d613c393` | CARRERA 23 NRO 53A 25 | 5.062466632954545,-75.49477705814394 | — | — | `insufficient` | — | `keep_approximate_bad_commercial_poi` | POI comercial del centro mal georreferenciado; no usar. |
| `utomovilistica-piloto-177f760536` | CARRERA 21 NO. 15-40 | 5.0681641,-75.5221452 | 5.0682222,-75.5217211 | 5.0680482,-75.5217908 | `interpolated` | 80394,80393 | `candidate_approximate_or_address_via_municipal_interpolation` | Interpolación entre placas 38 y 44 sobre K 21 15 (no existe predio exacto 15-40). |
| `car-del-eje-manizales-71a9a35cf0` | CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER | 5.05390085,-75.47652575000001 | 5.0517,-75.4844 | 5.0506212,-75.4836742 | `interpolated` | 96475,52515 | `approximate_not_confirmed_with_corrected_municipal_interpolation` | Interpolación municipal hacia 70-59; mantener approximate_not_confirmed salvo predio exacto. Verificar sector Alta Suiza. |
| `-automovilistica-cald-3e6c3b1930` | CRA 24 53-20 | 5.0630767,-75.4962899 | 5.062863,-75.4961049 | 5.062791,-75.4962457 | `exact` | 14593 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `atencion-rutas-de-col-e89cbc963e` | CALLE 21 # 19 - 27 CENTRO | 5.069294909977283,-75.51837825910042 | 5.069402,-75.5182809 | 5.0693862,-75.5180932 | `exact` | 27405 | `candidate_for_confirmed_address_using_geoportal_geometry` | Geometría centroide del predio oficial con dirección coincidente. |
| `atencion-eje-cafetero-3000df8047` | CARRERA 20 NO.21-40 | 5.069090011353712,-75.51802856550218 | 5.0689636,-75.5181746 | — | `insufficient` | — | `keep_approximate_not_confirmed` | insufficient_bracketing_predios |
| `cimyc-manizales-s-a-s-498175000a` | CARRERA 19 #64A-19A | 5.05813485,-75.48422695 | — | — | `insufficient` | — | `keep_approximate_insufficient_evidence` | Sin evidencia de punto exacto. |
| `iento-de-conductores--dfb8fe156d` | CALLE 22 NO. 18-29 PISO 2 | 5.0702978,-75.5177831 | 5.070056,-75.5177019 | — | `documentation_only` | — | `operational_status_requires_review_no_coord_change` | Sin cambio de coordenadas/estado. RUNT directorio clásico: Calle 22 #18-29 piso 2; ausente en RUNT 2.0 actores activos/certificando 2026 (hallazgo auditoría). |
| `ertificamos-agustinos-98839ab670` | CRA 19 18-27 LC 3/3-1 | 5.069385,-75.5203143 | — | — | `insufficient` | — | `keep_approximate_shared_nit_separate_sites` | Comparte NIT con Certificamos Terminal; sedes distintas, no fusionar. |

## 1. CDA CALDAS EL BOSQUE (CDA)

- **ID:** `cda-manizales-cda-caldas-el-bosque-a730920403`
- **Dirección RUNT:** CALLE 12 # 30 32
- **Actual:** 5.06231775, -75.52377055
- **Secundaria:** {'lat': 5.061935, 'lng': -75.5238599}
- **Geoportal/interpolación:** 5.0619511, -75.5239771
- **Tipo:** `exact`
- **OBJECTIDs:** [32634]
- **Dist. a actual:** 46.7 m
- **Dist. a secundaria:** 13.1 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27C+12+30+32%27']

## 2. CDA SOCICAR (CDA)

- **ID:** `cda-manizales-cda-socicar-7acac31f0f`
- **Dirección RUNT:** AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS
- **Actual:** 5.0694483, -75.5235525
- **Secundaria:** None
- **Geoportal/interpolación:** None, None
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `keep_approximate_insufficient_evidence`
- **Motivo:** Sin evidencia de punto exacto.
- **URLs:** []

## 3. CENTRO DE DIAGNOSTICO AUTOMOTOR MOTOLINARES (CDA)

- **ID:** `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c`
- **Dirección RUNT:** CARRERA 24 # 32 - 49 BRR FUNDADORES
- **Actual:** 5.0667186, -75.5111711
- **Secundaria:** {'lat': 5.066789, 'lng': -75.5108139}
- **Geoportal/interpolación:** 5.0668589, -75.5108467
- **Tipo:** `exact`
- **OBJECTIDs:** [52874]
- **Dist. a actual:** 39.2 m
- **Dist. a secundaria:** 8.6 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27CR+24+32+49%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+24+32+49%27']

## 4. ACADEMIA AUTOMOVILISTICA CALDAS SAS (CEA)

- **ID:** `cea-manizales-academia-automovilistica-caldas-sas-12d613c393`
- **Dirección RUNT:** CARRERA 23 NRO 53A 25
- **Actual:** 5.062466632954545, -75.49477705814394
- **Secundaria:** None
- **Geoportal/interpolación:** None, None
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `keep_approximate_bad_commercial_poi`
- **Motivo:** POI comercial del centro mal georreferenciado; no usar.
- **URLs:** []

## 5. ACADEMIA AUTOMOVILISTICA PILOTO (CEA)

- **ID:** `cea-manizales-academia-automovilistica-piloto-177f760536`
- **Dirección RUNT:** CARRERA 21 NO. 15-40
- **Actual:** 5.0681641, -75.5221452
- **Secundaria:** {'lat': 5.0682222, 'lng': -75.5217211}
- **Geoportal/interpolación:** 5.0680482, -75.5217908
- **Tipo:** `interpolated`
- **OBJECTIDs:** [80394, 80393]
- **Dist. a actual:** 41.3 m
- **Dist. a secundaria:** 20.8 m
- **Estado recomendado:** `candidate_approximate_or_address_via_municipal_interpolation`
- **Motivo:** Interpolación entre placas 38 y 44 sobre K 21 15 (no existe predio exacto 15-40).
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25K+21+15%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25CR+21+15%25%27&resultRecordCount=100']

## 6. CEA PRACTICAR DEL EJE - MANIZALES (CEA)

- **ID:** `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0`
- **Dirección RUNT:** CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER
- **Actual:** 5.05390085, -75.47652575000001
- **Secundaria:** {'lat': 5.0517, 'lng': -75.4844}
- **Geoportal/interpolación:** 5.0506212, -75.4836742
- **Tipo:** `interpolated`
- **OBJECTIDs:** [96475, 52515]
- **Dist. a actual:** 871.7 m
- **Dist. a secundaria:** 144.4 m
- **Estado recomendado:** `approximate_not_confirmed_with_corrected_municipal_interpolation`
- **Motivo:** Interpolación municipal hacia 70-59; mantener approximate_not_confirmed salvo predio exacto. Verificar sector Alta Suiza.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25C+70+23%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25CL+70+23%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25K+23+70%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25CR+23+70%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25AV+23+70%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25C+70%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&geometry=%7B%22xmin%22%3A+-75.48602794513216%2C+%22ymin%22%3A+5.0500783783783785%2C+%22xmax%22%3A+-75.48277205486782%2C+%22ymax%22%3A+5.053321621621622%2C+%22spatialReference%22%3A+%7B%22wkid%22%3A+4326%7D%7D&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects']

## 7. CENTRO DE ENSEÑANZA AUTOMOVILISTICA CALDAS (CEA)

- **ID:** `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930`
- **Dirección RUNT:** CRA 24 53-20
- **Actual:** 5.0630767, -75.4962899
- **Secundaria:** {'lat': 5.062863, 'lng': -75.4961049}
- **Geoportal/interpolación:** 5.062791, -75.4962457
- **Tipo:** `exact`
- **OBJECTIDs:** [14593]
- **Dist. a actual:** 32.1 m
- **Dist. a secundaria:** 17.5 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+24+53+20%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27K+24+53+20+K+25%27', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27CR+24+53+20%27']

## 8. CENTRO INTEGRAL DE ATENCION RUTAS DE COLOMBIA (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e`
- **Dirección RUNT:** CALLE 21 # 19 - 27 CENTRO
- **Actual:** 5.069294909977283, -75.51837825910042
- **Secundaria:** {'lat': 5.069402, 'lng': -75.5182809}
- **Geoportal/interpolación:** 5.0693862, -75.5180932
- **Tipo:** `exact`
- **OBJECTIDs:** [27405]
- **Dist. a actual:** 33.2 m
- **Dist. a secundaria:** 20.9 m
- **Estado recomendado:** `candidate_for_confirmed_address_using_geoportal_geometry`
- **Motivo:** Geometría centroide del predio oficial con dirección coincidente.
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+%3D+%27C+21+19+27%27']

## 9. CENTRO INTEGRAL DE ATENCIÓN EJE CAFETEROS S.A.S (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047`
- **Dirección RUNT:** CARRERA 20 NO.21-40
- **Actual:** 5.069090011353712, -75.51802856550218
- **Secundaria:** {'lat': 5.0689636, 'lng': -75.5181746}
- **Geoportal/interpolación:** None, None
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `keep_approximate_not_confirmed`
- **Motivo:** insufficient_bracketing_predios
- **URLs:** ['https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25K+20+21%25%27&resultRecordCount=100', 'https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?f=json&outFields=CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev%2CCATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio&returnGeometry=true&outSR=4326&where=CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion+LIKE+%27%25CR+20+21%25%27&resultRecordCount=100']

## 10. CIMYC MANIZALES S.A.S (CIA)

- **ID:** `cia-manizales-cimyc-manizales-s-a-s-498175000a`
- **Dirección RUNT:** CARRERA 19 #64A-19A
- **Actual:** 5.05813485, -75.48422695
- **Secundaria:** None
- **Geoportal/interpolación:** None, None
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `keep_approximate_insufficient_evidence`
- **Motivo:** Sin evidencia de punto exacto.
- **URLs:** []

## 11. CENTRO DE RECONOCIMIENTO DE CONDUCTORES EVALUANDO MANIZALES (CRC)

- **ID:** `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d`
- **Dirección RUNT:** CALLE 22 NO. 18-29 PISO 2
- **Actual:** 5.0702978, -75.5177831
- **Secundaria:** {'lat': 5.070056, 'lng': -75.5177019}
- **Geoportal/interpolación:** None, None
- **Tipo:** `documentation_only`
- **OBJECTIDs:** []
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `operational_status_requires_review_no_coord_change`
- **Motivo:** Sin cambio de coordenadas/estado. RUNT directorio clásico: Calle 22 #18-29 piso 2; ausente en RUNT 2.0 actores activos/certificando 2026 (hallazgo auditoría).
- **URLs:** []

## 12. CERTIFICAMOS AGUSTINOS (CRC)

- **ID:** `crc-manizales-certificamos-agustinos-98839ab670`
- **Dirección RUNT:** CRA 19 18-27 LC 3/3-1
- **Actual:** 5.069385, -75.5203143
- **Secundaria:** None
- **Geoportal/interpolación:** None, None
- **Tipo:** `insufficient`
- **OBJECTIDs:** []
- **Dist. a actual:** None m
- **Dist. a secundaria:** None m
- **Estado recomendado:** `keep_approximate_shared_nit_separate_sites`
- **Motivo:** Comparte NIT con Certificamos Terminal; sedes distintas, no fusionar.
- **URLs:** []
