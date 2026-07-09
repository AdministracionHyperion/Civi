# Places integrity fix — estado verificable (PR #1)

Fecha: 2026-07-09  
Rama: `feat/places-national-catalog`  
PR: https://github.com/AdministracionHyperion/Civi/pull/1  
SHA fuente: `457b4fda1f29096f29b385c9b47c92596ec9658f2509009af14fb3f64c25c634`

## READY_TO_MERGE=NO

Motivo: el prompt completo exige CI verde en GitHub, smoke Compose del stack Civi, rollback de snapshot y cobertura total de las 74 pruebas listadas. Parte de eso aún no tiene evidencia remota/completa. Lo crítico de integridad local **sí** está demostrado abajo.

## Evidencia ejecutada

| Prueba | Resultado |
| --- | --- |
| Colisiones before_fix | 4 identificadas (`site_id_collisions_before_fix.json`) |
| Dry-run reconciliación | 4107 = 4040+61+6+0; sites 4046; `non_merged_equals_unique_sites=true` |
| Colisiones after_fix | 0 |
| Apply SQLite #1 | inserted=4046 |
| Apply SQLite #2 | inserted=0, updated=0, unchanged=4046 |
| Apply PostgreSQL #1/#2 | second: inserted=0, updated=0, unchanged=4046 (`postgresql_validation_report.json`) |
| Migraciones | v1_baseline + v2_national_catalog |
| `scripts/verify.ps1` | PASSED |
| Docker Compose config | PASSED |
| Places/appointment tests | PASSED (tras ajuste detail) |

## Reconciliación final

- imported_as_site: 4040  
- merged_duplicate: 61  
- pending_review: 6  
- rejected: 0  
- unique_sites: 4046  
- unique_entities: 3293  

## Las 4 colisiones originales

1. Filas 12/160 — misma entidad/dirección, municipios distintos (Apartadó/Turbo) → sedes distintas vía municipio en `site_id`.  
2. Filas 164/166 — misma dirección; nombre con puntuación/sufijo → fusión por `name_core` o IDs distintos.  
3. Filas 420/421 — LTDA vs LIMITADA / DV → fusión o distinción estable.  
4. Filas 832/833 — fija vs línea móvil, misma dirección → distinción por nombre en hash.

## Correcciones incluidas en este push

- Sin overwrite silencioso de `site_id`
- Idempotencia por `content_hash`
- Historial `places_import_source_records`
- Presencia present/missing/reappeared
- `eligible_for_civi_booking` + appointment
- DIVIPOLA 1122 municipios versionado
- Geocoders disabled/http/manual + CLI `import_geocodes`
- Migración versionada (no solo create_all)
- CI workflow `.github/workflows/verify.yml`
- OpenAPI/app version 0.2.0

## Pendiente para READY_TO_MERGE=YES

1. Workflow GitHub Actions verde en el PR remoto.  
2. Smoke Compose completo del stack Civi (no solo `config --quiet`).  
3. Rollback de snapshot documentado y probado end-to-end.  
4. Cobertura explícita de todas las pruebas del §34 (ambigüedad territorial bot, caja GPS SQL, etc.).  
5. Summary SQL con el 100% de métricas del §26.  
6. Migración desde esquema exacto de `main` con datos legacy + citas (parcialmente cubierta; ampliar fixture).
