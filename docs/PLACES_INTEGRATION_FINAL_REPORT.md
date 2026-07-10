# Informe final — integración catálogo nacional places (Civi)

Fecha: 2026-07-09  
Repo: `civi-restructurado` (AdministracionHyperion/Civi)  
Entrada: `places_colombia_sin_coords.json` (preservado + copia en `services/places-service/data/raw/places_colombia_original.json`)

## 1. Resumen ejecutivo

Se integró de punta a punta el catálogo nacional CDA/CEA/CIA/CRC en `places-service`: modelo normalizado (entidades/sedes/contactos/source records), importador idempotente, búsqueda sin fallback nacional, geocoding desactivado por defecto, validación de agendamiento en `appointment-service`, bot que solo agenda `is_bookable=true`, y admin que consume estadísticas por HTTP. `scripts/verify.ps1` pasó (177 tests). Docker Compose config válida; smoke de contenedores no ejecutado en esta sesión.

## 2. Arquitectura encontrada

Usuario → channel-gateway → conversation → bot-orchestrator → places-service → (opcional) appointment-service. Ownership exclusivo de lugares en `places-service`; integraciones por HTTP interno.

## 3. Problemas en el archivo fuente

Documentos repetidos / multi-sede; `runt_actor_id` a menudo = documento; todos “activos” en origen; nombres con RETIRADO; direcciones incompletas; teléfonos nulos/ficticios; DV NIT inconsistente; ciudad compuesta municipio–centro poblado; coordenadas vacías; `source_updated_at` = extracción.

## 4. Problemas del runtime anterior

Modelo `Place` simple; `lat`/`lng` NOT NULL; catálogo demo de 5 sitios; fallback nacional silencioso; citas sin validar bookable; seed automático confuso con producción.

## 5. Modelo de datos

Tablas: `places_entities`, `places_sites`, `places_contacts`, `places_source_records`, `places_import_runs`, `places_duplicate_candidates`, legacy `places`. `lat`/`lng` nullable.

## 6–7. Archivos creados / modificados (principales)

Creados: pipeline (`normalize`, `catalog_builder`), CLI `import_catalog`, domain models, geocoding adapter, endpoints get/eligibility/summary, docs `PLACES_*.md`, reportes en `data/reports/`, tests `test_catalog_pipeline.py`.  
Modificados: nearest (sin fallback), appointment places client + guard, bot bookable/informative, admin summary client, compose/env, OpenAPI places 0.2.0, offline core flow.

## 8–14. Conteos

| Métrica | Valor |
| --- | ---: |
| Registros fuente | **4107** (CDA 989, CEA 1552, CIA 772, CRC 794) |
| Titulares únicos | **3293** |
| Sedes únicas | **4046** |
| Fusionados exactos | **61** |
| Candidatos duplicado (revisión) | **2815** |
| Rechazados | **0** |
| Pending review (procesamiento) | **6** |
| Reconciliación | 4040+61+6+0 = **4107** ✓ |

## 15–18. Calidad

Documentos válidos 3264 / inválidos-atípicos 29; direcciones válidas 3762, parciales 280, inválidas 2; teléfonos válidos 3882 / inválidos 169; estados: unknown 4038, retired 6; aliados 0; agendables 0 tras import.

## 19–21. Cobertura

Geocoding: 0% (modo `disabled`); pendiente 3974; dirección insuficiente 70. Territorial: resolutor + `territorial_review.json`; DIVIPOLA oficial no reconciliado en esta corrida (sin inventar códigos).

## 22–26. Cambios de API / servicios

- places: `nearest` + campos opcionales; `GET .../{id}`, `.../booking-eligibility`, `.../catalog/summary`
- bot: solo agenda bookable; modo `places_informative_only`; vacío con `no_results_reason`
- appointment: valida eligibility; 422 `place_not_bookable`; persiste canónicos
- admin: `places_catalog` en dashboard vía HTTP

## 27. Migración SQL

Schema nuevo + tabla legacy; seed sample explícito (`PLACES_BOOTSTRAP_MODE`); import CLI para dataset.

## 28–29. Pruebas / resultados

- places + appointment + bot + admin + offline: OK  
- dry-run + apply ×2 (idempotente: 2º apply `inserted=0`, `updated=7340`): OK  
- `scripts/verify.ps1`: **PASSED**  
- `docker compose ... config`: OK  
- Smoke containers: **no ejecutado** (daemon disponible; no se levantó stack completo)

## 30–31. Riesgos / externos pendientes

- 2815 candidatos de duplicado para revisión humana  
- Sin geocoding ni `source_updated_at` oficial  
- DIVIPOLA / estado RUNT no verificados online en esta fase  
- `manual_review` ~1980 sedes (territorio/dirección/doc)  
- No gastar cuota Google hasta OK explícito

## 32. Comandos

Ver `docs/PLACES_IMPORT_PIPELINE.md` y `docs/PLACES_OPERATIONS_RUNBOOK.md`.

## 33. Estado del producto (verificable)

| Capacidad | Estado |
| --- | --- |
| Reconciliación 4107 | 100% |
| Sin fallback nacional | Sí |
| No active por defecto | Sí |
| No bookable sin alianza | Sí (0 bookable post-import) |
| Idempotencia import | Sí |
| verify.ps1 | Sí |
| Geocoding operativo | 0% (disabled a propósito) |
| Cobertura GPS | 0% coords |
