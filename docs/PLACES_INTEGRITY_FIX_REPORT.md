# Places integrity fix — estado verificable (PR #1)

Fecha: 2026-07-09  
Rama: `feat/places-national-catalog`  
PR: https://github.com/AdministracionHyperion/Civi/pull/1  
SHA fuente: `457b4fda1f29096f29b385c9b47c92596ec9658f2509009af14fb3f64c25c634`

## READY_TO_MERGE=NO

Motivo: falta evidencia remota de CI verde en el PR tras este push, y smoke Compose del stack completo (no solo `postgres`/`redis` + `config --quiet`).

## Evidencia ejecutada

| Prueba | Resultado |
| --- | --- |
| Colisiones before_fix | 4 identificadas (`site_id_collisions_before_fix.json`) |
| Dry-run reconciliación | 4107 = 4040+61+6+0; sites 4046; `non_merged_equals_unique_sites=true` |
| Colisiones after_fix | 0 |
| Apply SQLite #1 | inserted=4046 |
| Apply SQLite #2 | inserted=0, updated=0, unchanged=4046 |
| Apply PostgreSQL #1/#2 | second: inserted=0, updated=0, unchanged=4046 (`postgresql_validation_report.json`) |
| Migración legacy `places` → `places_sites` | PASSED (`test_legacy_migration.py`) |
| Búsqueda SQL filtrada (municipio + bbox GPS) | PASSED |
| Summary por agregaciones SQL | PASSED |
| Rollback CLI `restore_snapshot` | documentado + delega a import lifecycle |
| Bot sin asumir municipio | mensaje para `city_or_coordinates_required` |
| Migraciones | v1_baseline + v2_national_catalog |
| `scripts/verify.ps1` | PASSED (180 tests) |
| Docker Compose config | PASSED |
| Compose `postgres`+`redis` up | PASSED |

## Reconciliación final

- imported_as_site: 4040  
- merged_duplicate: 61  
- pending_review: 6  
- rejected: 0  
- unique_sites: 4046  
- unique_entities: 3293  

## Correcciones en este tramo

- Migración legacy incluye columnas NOT NULL (`status_inferred_from_name`, presencia).
- `search_nearest` filtra en SQL (municipio / bbox) — no carga catálogo completo.
- `catalog_summary` por agregaciones SQL + `by_source_presence_status`.
- CLI `restore_snapshot` + runbook.
- CI: PyYAML, dry-run reconciliación, job Postgres idempotency.
- Bot: razones `city_or_coordinates_required` / `coordinates_outside_colombia`.

## Pendiente para READY_TO_MERGE=YES

1. Workflow GitHub Actions verde en el PR remoto (tras push).  
2. Smoke Compose completo del stack Civi (health de servicios de app).  
3. Confirmar CI Postgres idempotency en Actions.
