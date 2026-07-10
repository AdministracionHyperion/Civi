# Inventario — Manizales `approximate_not_confirmed` (12)

Trabajo de auditoría externa. **CSV canónico no modificado.**

Reglas: no inventar coordenadas; no confirmar solo por bbox; evidencia = nombre/dirección/teléfono/NIT/fuente oficial; sin evidencia → conservar punto actual; no usar IA como fuente.

## 1. CDA CALDAS EL BOSQUE (CDA)

- **ID:** `cda-manizales-cda-caldas-el-bosque-a730920403`
- **Dirección RUNT:** CALLE 12 # 30 32
- **Coordenadas actuales:** 5.06231775, -75.52377055
- **Precisión / confianza / provider:** street_intersection / 0.58 / openstreetmap_road_network
- **NIT:** 890805554
- **Teléfono:** 3113549239
- **Evidencia actual:** Se prioriza la dirección RUNT mediante road_intersection:calle 12/carrera 30; el lugar comercial geoapify quedó a 1317 m y no coincidió por teléfono.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada. Hubo candidato comercial lejano o inconsistente respecto al ancla RUNT.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CDA CALDAS EL BOSQUE'.
  - Búsqueda de dirección RUNT en mapas: 'CALLE 12 # 30 32, Manizales, Caldas'.
  - Verificar teléfono RUNT 3113549239 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 890805554 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 2. CDA SOCICAR (CDA)

- **ID:** `cda-manizales-cda-socicar-7acac31f0f`
- **Dirección RUNT:** AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS
- **Coordenadas actuales:** 5.0694483, -75.5235525
- **Precisión / confianza / provider:** street_intersection / 0.62 / openstreetmap_road_network
- **NIT:** 901841847
- **Teléfono:** 3043331591
- **Evidencia actual:** Cruce colombiano carrera 19 con calle 13; separación de vías=0.0 m; no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CDA SOCICAR'.
  - Búsqueda de dirección RUNT en mapas: 'AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS, Manizales, Caldas'.
  - Verificar teléfono RUNT 3043331591 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 901841847 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 3. CENTRO DE DIAGNOSTICO AUTOMOTOR MOTOLINARES (CDA)

- **ID:** `cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c`
- **Dirección RUNT:** CARRERA 24 # 32 - 49 BRR FUNDADORES
- **Coordenadas actuales:** 5.0667186, -75.5111711
- **Precisión / confianza / provider:** street_intersection / 0.58 / openstreetmap_road_network
- **NIT:** 901345789
- **Teléfono:** 3113010474
- **Evidencia actual:** Se prioriza la dirección RUNT mediante road_intersection:carrera 24/calle 32; el lugar comercial overture_maps_2026-06-17 quedó a 1593 m y no coincidió por teléfono.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada. Hubo candidato comercial lejano o inconsistente respecto al ancla RUNT.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CENTRO DE DIAGNOSTICO AUTOMOTOR MOTOLINARES'.
  - Búsqueda de dirección RUNT en mapas: 'CARRERA 24 # 32 - 49 BRR FUNDADORES, Manizales, Caldas'.
  - Verificar teléfono RUNT 3113010474 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 901345789 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 4. ACADEMIA AUTOMOVILISTICA CALDAS SAS (CEA)

- **ID:** `cea-manizales-academia-automovilistica-caldas-sas-12d613c393`
- **Dirección RUNT:** CARRERA 23 NRO 53A 25
- **Coordenadas actuales:** 5.062466632954545, -75.49477705814394
- **Precisión / confianza / provider:** street_interpolation / 0.55 / openstreetmap_local_interpolation
- **NIT:** 900351845
- **Teléfono:** 6068911466
- **Evidencia actual:** Interpolación en carrera 23 entre (49.0, 30.0) y (58.0, 6.0); no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_interpolation' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'ACADEMIA AUTOMOVILISTICA CALDAS SAS'.
  - Búsqueda de dirección RUNT en mapas: 'CARRERA 23 NRO 53A 25, Manizales, Caldas'.
  - Verificar teléfono RUNT 6068911466 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 900351845 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 5. ACADEMIA AUTOMOVILISTICA PILOTO (CEA)

- **ID:** `cea-manizales-academia-automovilistica-piloto-177f760536`
- **Dirección RUNT:** CARRERA 21 NO. 15-40
- **Coordenadas actuales:** 5.0681641, -75.5221452
- **Precisión / confianza / provider:** street_intersection / 0.62 / openstreetmap_road_network
- **NIT:** 17171839
- **Teléfono:** 8828184
- **Evidencia actual:** Cruce colombiano carrera 21 con calle 15; separación de vías=0.0 m; no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'ACADEMIA AUTOMOVILISTICA PILOTO'.
  - Búsqueda de dirección RUNT en mapas: 'CARRERA 21 NO. 15-40, Manizales, Caldas'.
  - Verificar teléfono RUNT 8828184 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 17171839 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 6. CEA PRACTICAR DEL EJE - MANIZALES (CEA)

- **ID:** `cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0`
- **Dirección RUNT:** CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER
- **Coordenadas actuales:** 5.05390085, -75.47652575000001
- **Precisión / confianza / provider:** street_intersection / 0.58 / openstreetmap_road_network
- **NIT:** 901247003
- **Teléfono:** 3138836685
- **Evidencia actual:** Se prioriza la dirección RUNT mediante road_intersection:carrera 23/calle 70; el lugar comercial openstreetmap_local_interpolation quedó a 891 m y no coincidió por teléfono.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada. Hubo candidato comercial lejano o inconsistente respecto al ancla RUNT.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CEA PRACTICAR DEL EJE - MANIZALES'.
  - Búsqueda de dirección RUNT en mapas: 'CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER, Manizales, Caldas'.
  - Verificar teléfono RUNT 3138836685 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 901247003 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 7. CENTRO DE ENSEÑANZA AUTOMOVILISTICA CALDAS (CEA)

- **ID:** `cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930`
- **Dirección RUNT:** CRA 24 53-20
- **Coordenadas actuales:** 5.0630767, -75.4962899
- **Precisión / confianza / provider:** street_intersection / 0.62 / openstreetmap_road_network
- **NIT:** 901461969
- **Teléfono:** —
- **Evidencia actual:** Cruce colombiano carrera 24 con calle 53; separación de vías=0.0 m; no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CENTRO DE ENSEÑANZA AUTOMOVILISTICA CALDAS'.
  - Búsqueda de dirección RUNT en mapas: 'CRA 24 53-20, Manizales, Caldas'.
  - Sin teléfono usable en CSV (0/vacío): priorizar NIT + nombre en RUES/RUNT y sitio web oficial si existe.
  - Consulta NIT 901461969 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 8. CENTRO INTEGRAL DE ATENCION RUTAS DE COLOMBIA (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e`
- **Dirección RUNT:** CALLE 21 # 19 - 27 CENTRO
- **Coordenadas actuales:** 5.069294909977283, -75.51837825910042
- **Precisión / confianza / provider:** street_interpolation / 0.55 / openstreetmap_local_interpolation
- **NIT:** 901851594
- **Teléfono:** —
- **Evidencia actual:** Interpolación en calle 21 entre (11.0, 34.0) y (22.0, 39.0); no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_interpolation' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CENTRO INTEGRAL DE ATENCION RUTAS DE COLOMBIA'.
  - Búsqueda de dirección RUNT en mapas: 'CALLE 21 # 19 - 27 CENTRO, Manizales, Caldas'.
  - Sin teléfono usable en CSV (0/vacío): priorizar NIT + nombre en RUES/RUNT y sitio web oficial si existe.
  - Consulta NIT 901851594 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 9. CENTRO INTEGRAL DE ATENCIÓN EJE CAFETEROS S.A.S (CIA)

- **ID:** `cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047`
- **Dirección RUNT:** CARRERA 20 NO.21-40
- **Coordenadas actuales:** 5.069090011353712, -75.51802856550218
- **Precisión / confianza / provider:** street_interpolation / 0.55 / openstreetmap_local_interpolation
- **NIT:** 900455427
- **Teléfono:** 7550531
- **Evidencia actual:** Interpolación en carrera 20 entre (20.0, 25.0) y (28.0, 40.0); no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_interpolation' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CENTRO INTEGRAL DE ATENCIÓN EJE CAFETEROS S.A.S'.
  - Búsqueda de dirección RUNT en mapas: 'CARRERA 20 NO.21-40, Manizales, Caldas'.
  - Verificar teléfono RUNT 7550531 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 900455427 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 10. CIMYC MANIZALES S.A.S (CIA)

- **ID:** `cia-manizales-cimyc-manizales-s-a-s-498175000a`
- **Dirección RUNT:** CARRERA 19 #64A-19A
- **Coordenadas actuales:** 5.05813485, -75.48422695
- **Precisión / confianza / provider:** street_intersection / 0.5 / openstreetmap_road_network
- **NIT:** 901447764
- **Teléfono:** —
- **Evidencia actual:** Cruce colombiano carrera 19 con calle 64a; separación de vías=112.5 m; no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CIMYC MANIZALES S.A.S'.
  - Búsqueda de dirección RUNT en mapas: 'CARRERA 19 #64A-19A, Manizales, Caldas'.
  - Sin teléfono usable en CSV (0/vacío): priorizar NIT + nombre en RUES/RUNT y sitio web oficial si existe.
  - Consulta NIT 901447764 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 11. CENTRO DE RECONOCIMIENTO DE CONDUCTORES EVALUANDO MANIZALES (CRC)

- **ID:** `crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d`
- **Dirección RUNT:** CALLE 22 NO. 18-29 PISO 2
- **Coordenadas actuales:** 5.0702978, -75.5177831
- **Precisión / confianza / provider:** street_intersection / 0.62 / openstreetmap_road_network
- **NIT:** 900094432
- **Teléfono:** 8830561
- **Evidencia actual:** Cruce colombiano calle 22 con carrera 18; separación de vías=0.0 m; no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CENTRO DE RECONOCIMIENTO DE CONDUCTORES EVALUANDO MANIZALES'.
  - Búsqueda de dirección RUNT en mapas: 'CALLE 22 NO. 18-29 PISO 2, Manizales, Caldas'.
  - Verificar teléfono RUNT 8830561 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 900094432 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.

## 12. CERTIFICAMOS AGUSTINOS (CRC)

- **ID:** `crc-manizales-certificamos-agustinos-98839ab670`
- **Dirección RUNT:** CRA 19 18-27 LC 3/3-1
- **Coordenadas actuales:** 5.069385, -75.5203143
- **Precisión / confianza / provider:** street_intersection / 0.62 / openstreetmap_road_network
- **NIT:** 900697302
- **Teléfono:** 3008149289
- **Evidencia actual:** Cruce colombiano carrera 19 con calle 18; separación de vías=0.0 m; no confirma el negocio.
- **Por qué sigue aproximada:** El geocoder solo ancló vía/cruce o interpolación; no hubo match comercial verificable (nombre/teléfono). Precisión actual 'street_intersection' no es rooftop/business/address confirmada.
- **Fuentes / búsquedas necesarias:**
  - Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.
  - Búsqueda de nombre comercial exacto + Manizales: 'CERTIFICAMOS AGUSTINOS'.
  - Búsqueda de dirección RUNT en mapas: 'CRA 19 18-27 LC 3/3-1, Manizales, Caldas'.
  - Verificar teléfono RUNT 3008149289 en Google/Maps/páginas del negocio (no usar IA como fuente).
  - Consulta NIT 900697302 en RUES / Cámara de Comercio (razón social y domicilio).
  - Street View / foto de fachada o pin de Google Business Profile solo si el nombre/dirección coinciden de forma inequívoca.
  - Si no hay evidencia suficiente: conservar lat/lng actuales y mantener approximate_not_confirmed.
