# Places integrity fix — estado verificable (PR #1)

Fecha: 2026-07-09  
Rama: `feat/places-national-catalog`  
PR: https://github.com/AdministracionHyperion/Civi/pull/1  
Commit HEAD (antes de este update): `11d99b0`  
SHA fuente (blob LF en git): `03df28538959a7d596c92451fecf960073b30df622e55206677faa8dfa3abba7`  
Nota: un checkout Windows con CRLF puede mostrar `457b4fda…` en disco; el contenido JSON es el mismo tras normalizar EOL.

## READY_TO_MERGE=YES

Evidencia remota y local completa para integridad del catálogo + CI + smoke del flujo places.

## Evidencia ejecutada

| Prueba | Resultado |
| --- | --- |
| Colisiones before_fix | 4 → 0 after_fix |
| Dry-run reconciliación | 4107 = 4040+61+6+0; sites 4046; `non_merged_equals_unique_sites=true` |
| Apply SQLite/Postgres #2 | inserted=0, updated=0, unchanged=4046 |
| Migración legacy `places` → `places_sites` | PASSED |
| Búsqueda SQL (municipio + bbox GPS) | PASSED |
| Summary agregaciones SQL | PASSED |
| Rollback CLI `restore_snapshot` | documentado + lifecycle-aware |
| Bot sin asumir municipio | `city_or_coordinates_required` |
| `scripts/verify.ps1` local | PASSED |
| GitHub Actions verify (push) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29058602033 |
| GitHub Actions verify (PR) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29058604337 |
| CI dry-run + Postgres idempotency | PASSED |
| Compose smoke stack places | channel `/health/live`+`/ready` 200; conversation 200; bot 200; places 200; appointment 200 |

## Reconciliación final

- imported_as_site: 4040 · merged_duplicate: 61 · pending_review: 6 · rejected: 0  
- unique_sites: 4046 · unique_entities: 3293  
