# Inventario actualizado — Manizales `approximate_not_confirmed` (12)

**CSV canónico no modificado.** Conteos del scope sin cambiar.

Geoportal consultado: capa `NOMENCLATURA PREDIAL` del SIG Alcaldía de Manizales (`https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10`).

## Tabla resumen

| ID | Decisión | Actual | Candidata | Dist. m | Fuente | Estado CSV | Bloqueo pendiente |
|---|---|---|---|---:|---|---|---|
| `das-el-bosque-a730920403` | `candidate_confirmed_address` | 5.06231775,-75.52377055 | 5.061935,-75.5238599 | 43.7 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Aplicar al CSV solo tras decisión explícita de apply/auditoría. |
| `s-cda-socicar-7acac31f0f` | `keep_approximate_insufficient_evidence` | 5.0694483,-75.5235525 | — | — | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Falta pin comercial/municipal verificable coherente con nombre+dirección. |
| `otor-motolina-0ce021ad5c` | `candidate_confirmed_address` | 5.0667186,-75.5111711 | 5.066789,-75.5108139 | 40.3 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Aplicar al CSV solo tras decisión explícita de apply/auditoría. |
| `ca-caldas-sas-12d613c393` | `keep_approximate_bad_commercial_poi` | 5.062466632954545,-75.49477705814394 | — | — | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Conservar punto actual aproximado hasta evidencia municipal/comercial válida. |
| `istica-piloto-177f760536` | `candidate_confirmed_address` | 5.0681641,-75.5221452 | 5.0682222,-75.5217211 | 47.4 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Aplicar al CSV solo tras decisión explícita; predial exacto 15-40 no hallado. |
| `eje-manizales-71a9a35cf0` | `current_coordinate_inconsistent` | 5.05390085,-75.47652575000001 | 5.0517,-75.4844 | 905.9 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Necesita coordenada municipal o comercial verificable en Alta Suiza antes de confirmar. |
| `ilistica-cald-3e6c3b1930` | `candidate_confirmed_address` | 5.0630767,-75.4962899 | 5.062863,-75.4961049 | 31.4 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Aplicar al CSV solo tras decisión explícita de apply/auditoría. |
| `-rutas-de-col-e89cbc963e` | `candidate_confirmed_address` | 5.069294909977283,-75.51837825910042 | 5.069402,-75.5182809 | 16.1 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Aplicar al CSV solo tras decisión explícita de apply/auditoría. |
| `-eje-cafetero-3000df8047` | `candidate_confirmed_address` | 5.069090011353712,-75.51802856550218 | 5.0689636,-75.5181746 | 21.4 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Aplicar al CSV solo tras decisión explícita; predial exacto 21-40 no hallado. |
| `nizales-s-a-s-498175000a` | `keep_approximate_insufficient_evidence` | 5.05813485,-75.48422695 | — | — | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Falta pin comercial/municipal verificable. |
| `-conductores--dfb8fe156d` | `operational_status_requires_review` | 5.0702978,-75.5177831 | 5.070056,-75.5177019 | 28.4 | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Revisar estado operativo/presencia RUNT 2.0 antes de confirmar o retirar. |
| `mos-agustinos-98839ab670` | `keep_approximate_insufficient_evidence` | 5.069385,-75.5203143 | — | — | Geoportal+auditoría | approximate_not_confirmed (sin cambio) | Falta pin exacto de la sede Agustinos; no fusionar con Terminal. |

## 1. CDA CALDAS EL BOSQUE (CDA)

- **ID:** `cda-manizales-cda-caldas-el-bosque-a730920403`
- **Dirección RUNT:** CALLE 12 # 30 32
- **Coordenadas actuales:** 5.06231775, -75.52377055
- **Candidata:** 5.061935, -75.5238599
- **Distancia actual→candidata:** 43.7 m
- **Decisión:** `candidate_confirmed_address`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.
- **Bloqueo pendiente:** Aplicar al CSV solo tras decisión explícita de apply/auditoría.
- **Evidencia CSV actual:** Se prioriza la dirección RUNT mediante road_intersection:calle 12/carrera 30; el lugar comercial geoapify quedó a 1317 m y no coincidió por teléfono.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "C 12 30 32", "match_quality": "exact_or_equivalent", "nearest_predial_distance_m": 13.1, "detail": "Capa NOMENCLATURA PREDIAL devolvió 'C 12 30 32' a ~13 m del candidato."}
- **Notas de auditoría:**
  - Candidato de dirección propuesto por auditoría externa.

## 2. CDA SOCICAR (CDA)

- **ID:** `cda-manizales-cda-socicar-7acac31f0f`
- **Dirección RUNT:** AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS
- **Coordenadas actuales:** 5.0694483, -75.5235525
- **Candidata:** —
- **Distancia actual→candidata:** —
- **Decisión:** `keep_approximate_insufficient_evidence`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Continúa aproximado por falta de evidencia de punto exacto.
- **Bloqueo pendiente:** Falta pin comercial/municipal verificable coherente con nombre+dirección.
- **Evidencia CSV actual:** Cruce colombiano carrera 19 con calle 13; separación de vías=0.0 m; no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "queried": false, "detail": "No se consultó candidato nuevo."}
- **Notas de auditoría:**
  - Sin candidato fuerte de dirección en esta ronda.

## 3. CENTRO DE DIAGNOSTICO AUTOMOTOR MOTOLINARES (CDA)

- **ID:** `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c`
- **Dirección RUNT:** CARRERA 24 # 32 - 49 BRR FUNDADORES
- **Coordenadas actuales:** 5.0667186, -75.5111711
- **Candidata:** 5.066789, -75.5108139
- **Distancia actual→candidata:** 40.3 m
- **Decisión:** `candidate_confirmed_address`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.
- **Bloqueo pendiente:** Aplicar al CSV solo tras decisión explícita de apply/auditoría.
- **Evidencia CSV actual:** Se prioriza la dirección RUNT mediante road_intersection:carrera 24/calle 32; el lugar comercial overture_maps_2026-06-17 quedó a 1593 m y no coincidió por teléfono.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "CR 24 32 49", "match_quality": "exact_or_equivalent", "nearest_predial_distance_m": 8.6, "detail": "NOMENCLATURA PREDIAL: 'CR 24 32 49' a ~8.6 m del candidato (coincide con RUNT)."}
- **Notas de auditoría:**
  - Candidato de dirección propuesto por auditoría externa.

## 4. ACADEMIA AUTOMOVILISTICA CALDAS SAS (CEA)

- **ID:** `cea-manizales-academia-automovilistica-caldas-sas-12d613c393`
- **Dirección RUNT:** CARRERA 23 NRO 53A 25
- **Coordenadas actuales:** 5.062466632954545, -75.49477705814394
- **Candidata:** —
- **Distancia actual→candidata:** —
- **Decisión:** `keep_approximate_bad_commercial_poi`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** POI comercial encontrado está mal georreferenciado en el centro; no usarlo.
- **Bloqueo pendiente:** Conservar punto actual aproximado hasta evidencia municipal/comercial válida.
- **Evidencia CSV actual:** Interpolación en carrera 23 entre (49.0, 30.0) y (58.0, 6.0); no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "queried": false, "detail": "Sin candidato nuevo a validar."}
- **Notas de auditoría:**
  - Registrar POI comercial del centro como mal georreferenciado.
  - No adoptar esas coordenadas.
  - Conservar lat/lng actuales del CSV.

## 5. ACADEMIA AUTOMOVILISTICA PILOTO (CEA)

- **ID:** `cea-manizales-academia-automovilistica-piloto-177f760536`
- **Dirección RUNT:** CARRERA 21 NO. 15-40
- **Coordenadas actuales:** 5.0681641, -75.5221452
- **Candidata:** 5.0682222, -75.5217211
- **Distancia actual→candidata:** 47.4 m
- **Decisión:** `candidate_confirmed_address`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.
- **Bloqueo pendiente:** Aplicar al CSV solo tras decisión explícita; predial exacto 15-40 no hallado.
- **Evidencia CSV actual:** Cruce colombiano carrera 21 con calle 15; separación de vías=0.0 m; no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "K 21 15 38 (cercano; no existe 'K 21 15 40' exacto)", "match_quality": "nearby_same_block", "nearest_predial_distance_m": 8.9, "detail": "Predios en K 21 15 38 / 44-48 / 60 cerca del candidato; sin ficha exacta 15-40."}
- **Notas de auditoría:**
  - Candidato de dirección propuesto por auditoría externa.

## 6. CEA PRACTICAR DEL EJE - MANIZALES (CEA)

- **ID:** `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0`
- **Dirección RUNT:** CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER
- **Coordenadas actuales:** 5.05390085, -75.47652575000001
- **Candidata:** 5.0517, -75.4844
- **Distancia actual→candidata:** 905.9 m
- **Decisión:** `current_coordinate_inconsistent`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Coordenada actual incoherente (Cerro de Oro/Colseguros, no Alta Suiza). Sector candidato aproximado sobre Av. Santander/Cra 23; sigue approximate.
- **Bloqueo pendiente:** Necesita coordenada municipal o comercial verificable en Alta Suiza antes de confirmar.
- **Evidencia CSV actual:** Se prioriza la dirección RUNT mediante road_intersection:carrera 23/calle 70; el lugar comercial openstreetmap_local_interpolation quedó a 891 m y no coincidió por teléfono.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "queried": false, "detail": "No se validó como confirmed_address; sector aproximado pendiente de nomenclatura exacta 70-59."}
- **Notas de auditoría:**
  - Punto CSV actual cae fuera del sector declarado (Alta Suiza - Av. Santander).
  - Sector candidato 5.0517,-75.4844 es solo aproximación de zona, no confirmación.

## 7. CENTRO DE ENSEÑANZA AUTOMOVILISTICA CALDAS (CEA)

- **ID:** `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930`
- **Dirección RUNT:** CRA 24 53-20
- **Coordenadas actuales:** 5.0630767, -75.4962899
- **Candidata:** 5.062863, -75.4961049
- **Distancia actual→candidata:** 31.4 m
- **Decisión:** `candidate_confirmed_address`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.
- **Bloqueo pendiente:** Aplicar al CSV solo tras decisión explícita de apply/auditoría.
- **Evidencia CSV actual:** Cruce colombiano carrera 24 con calle 53; separación de vías=0.0 m; no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "K 24 53 20 K 25", "match_quality": "exact_or_equivalent", "nearest_predial_distance_m": 7.0, "detail": "NOMENCLATURA PREDIAL: 'K 24 53 20 K 25' a ~7 m (coincide con CRA 24 53-20)."}
- **Notas de auditoría:**
  - Candidato de dirección propuesto por auditoría externa.

## 8. CENTRO INTEGRAL DE ATENCION RUTAS DE COLOMBIA (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e`
- **Dirección RUNT:** CALLE 21 # 19 - 27 CENTRO
- **Coordenadas actuales:** 5.069294909977283, -75.51837825910042
- **Candidata:** 5.069402, -75.5182809
- **Distancia actual→candidata:** 16.1 m
- **Decisión:** `candidate_confirmed_address`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.
- **Bloqueo pendiente:** Aplicar al CSV solo tras decisión explícita de apply/auditoría.
- **Evidencia CSV actual:** Interpolación en calle 21 entre (11.0, 34.0) y (22.0, 39.0); no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "C 21 19 27", "match_quality": "exact_or_equivalent", "nearest_predial_distance_m": 20.9, "detail": "NOMENCLATURA PREDIAL: 'C 21 19 27' a ~21 m del candidato (coincide con RUNT)."}
- **Notas de auditoría:**
  - Candidato de dirección propuesto por auditoría externa.

## 9. CENTRO INTEGRAL DE ATENCIÓN EJE CAFETEROS S.A.S (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047`
- **Dirección RUNT:** CARRERA 20 NO.21-40
- **Coordenadas actuales:** 5.069090011353712, -75.51802856550218
- **Candidata:** 5.0689636, -75.5181746
- **Distancia actual→candidata:** 21.4 m
- **Decisión:** `candidate_confirmed_address`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.
- **Bloqueo pendiente:** Aplicar al CSV solo tras decisión explícita; predial exacto 21-40 no hallado.
- **Evidencia CSV actual:** Interpolación en carrera 20 entre (20.0, 25.0) y (28.0, 40.0); no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "K 20 21 35 (cercano; no existe 'K 20 21 40' exacto)", "match_quality": "nearby_same_block", "nearest_predial_distance_m": 3.9, "detail": "Predios K 20 21 35 y tramos C 21 20 cerca del candidato; sin ficha exacta 21-40."}
- **Notas de auditoría:**
  - Candidato de dirección propuesto por auditoría externa.

## 10. CIMYC MANIZALES S.A.S (CIA)

- **ID:** `cia-manizales-cimyc-manizales-s-a-s-498175000a`
- **Dirección RUNT:** CARRERA 19 #64A-19A
- **Coordenadas actuales:** 5.05813485, -75.48422695
- **Candidata:** —
- **Distancia actual→candidata:** —
- **Decisión:** `keep_approximate_insufficient_evidence`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Continúa aproximado por falta de evidencia de punto exacto.
- **Bloqueo pendiente:** Falta pin comercial/municipal verificable.
- **Evidencia CSV actual:** Cruce colombiano carrera 19 con calle 64a; separación de vías=112.5 m; no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "queried": false, "detail": "No se consultó candidato nuevo."}
- **Notas de auditoría:**
  - Sin candidato fuerte de dirección en esta ronda.

## 11. CENTRO DE RECONOCIMIENTO DE CONDUCTORES EVALUANDO MANIZALES (CRC)

- **ID:** `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d`
- **Dirección RUNT:** CALLE 22 NO. 18-29 PISO 2
- **Coordenadas actuales:** 5.0702978, -75.5177831
- **Candidata:** 5.070056, -75.5177019
- **Distancia actual→candidata:** 28.4 m
- **Decisión:** `operational_status_requires_review`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** RUNT aún muestra Calle 22 #18-29 piso 2; no aparece en RUNT 2.0 actores activos/certificando 2026. Coordenada de referencia registrada; CSV sin cambio.
- **Bloqueo pendiente:** Revisar estado operativo/presencia RUNT 2.0 antes de confirmar o retirar.
- **Evidencia CSV actual:** Cruce colombiano calle 22 con carrera 18; separación de vías=0.0 m; no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "matched_predial_address": "C 22 18 23 29", "match_quality": "exact_or_equivalent", "nearest_predial_distance_m": 2.8, "detail": "NOMENCLATURA PREDIAL: 'C 22 18 23 29' a ~2.8 m de la referencia (cubre 18-29)."}
- **Notas de auditoría:**
  - Dirección RUNT vigente en directorio clásico: Calle 22 #18-29 piso 2.
  - Ausente del conjunto RUNT 2.0 activos/certificando 2026 (hallazgo de auditoría).
  - Coordenada de referencia 5.0700560,-75.5177019 (no aplicada al CSV).

## 12. CERTIFICAMOS AGUSTINOS (CRC)

- **ID:** `crc-manizales-certificamos-agustinos-98839ab670`
- **Dirección RUNT:** CRA 19 18-27 LC 3/3-1
- **Coordenadas actuales:** 5.069385, -75.5203143
- **Candidata:** —
- **Distancia actual→candidata:** —
- **Decisión:** `keep_approximate_insufficient_evidence`
- **Estado CSV:** `approximate_not_confirmed` (sin cambio)
- **Nota:** Continúa aproximado por falta de evidencia de punto exacto. Comparte NIT con Certificamos Terminal; son dos sedes RUNT distintas (no fusionar).
- **Bloqueo pendiente:** Falta pin exacto de la sede Agustinos; no fusionar con Terminal.
- **Evidencia CSV actual:** Cruce colombiano carrera 19 con calle 18; separación de vías=0.0 m; no confirma el negocio.
- **Geoportal:** {"layer": "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/2020_consulta_POT_urbano_web_v10_2/MapServer/10", "layer_name": "NOMENCLATURA PREDIAL", "accessible": true, "queried": false, "detail": "No se consultó candidato nuevo."}
- **Notas de auditoría:**
  - NIT compartido con Certificamos Terminal.
  - Dos sedes RUNT diferentes: no fusionar registros ni coordenadas.
