# Places integrity fix — estado verificable (PR #1)

Fecha: 2026-07-09  
Rama: `feat/places-national-catalog`  
PR: https://github.com/AdministracionHyperion/Civi/pull/1  
Commit HEAD: `a3736e9`  
SHA fuente (blob LF en git): `03df28538959a7d596c92451fecf960073b30df622e55206677faa8dfa3abba7`  
Nota: un checkout Windows con CRLF puede mostrar `457b4fda…` en disco; el contenido JSON es el mismo tras normalizar EOL.

## READY_TO_MERGE=NO

Motivo: falta smoke Compose del **stack completo** de servicios Civi (hoy hay smoke parcial: `postgres`+`redis`+`places-service` live/ready = 200). CI remoto sí está verde.

## Evidencia ejecutada

| Prueba | Resultado |
| --- | --- |
| Colisiones before_fix | 4 identificadas (`site_id_collisions_before_fix.json`) |
| Dry-run reconciliación | 4107 = 4040+61+6+0; sites 4046; `non_merged_equals_unique_sites=true` |
| Colisiones after_fix | 0 |
| Apply SQLite #1/#2 | 2ª: inserted=0, updated=0, unchanged=4046 |
| Apply PostgreSQL #1/#2 | idempotente (`postgresql_validation_report.json`) |
| Migración legacy `places` → `places_sites` | PASSED |
| Búsqueda SQL filtrada (municipio + bbox GPS) | PASSED |
| Summary por agregaciones SQL | PASSED |
| Rollback CLI `restore_snapshot` | documentado + lifecycle-aware |
| Bot sin asumir municipio | mensaje `city_or_coordinates_required` |
| `scripts/verify.ps1` local | PASSED (180+) |
| GitHub Actions verify (push) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29058602033 |
| GitHub Actions verify (PR) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29058604337 |
| CI dry-run + Postgres idempotency | PASSED en el mismo job |
| Compose smoke parcial | `places-service` `/health/live` y `/health/ready` = 200 |

## Reconciliación final

- imported_as_site: 4040  
- merged_duplicate: 61  
- pending_review: 6  
- rejected: 0  
- unique_sites: 4046  
- unique_entities: 3293  

## Pendiente para READY_TO_MERGE=YES

1. Smoke Compose del stack completo (channel → conversation → bot → places → appointment, health OK).  
2. (Opcional) re-validar rollback restore E2E con snapshot anterior en Postgres del stack.
