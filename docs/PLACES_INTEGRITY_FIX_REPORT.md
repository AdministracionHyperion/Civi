# Places integrity fix — estado post-merge (PR #1)

Fecha merge: 2026-07-10T00:27:27Z  
PR: https://github.com/AdministracionHyperion/Civi/pull/1  
Rama del PR: `feat/places-national-catalog`  
Commit final del PR (pre-squash): `f4f3635513fc4fb05cfb19d3b996c23d6fabb486`  
Commit squash en `main`: `952466bc6c73180c39504c9447d4d6d24643dd9d`  
Merged by: AdministracionHyperion  

SHA fuente (blob LF en git): `03df28538959a7d596c92451fecf960073b30df622e55206677faa8dfa3abba7`  
Nota: un checkout Windows con CRLF puede mostrar `457b4fda…` en disco; el contenido JSON es el mismo tras normalizar EOL.

## READY_TO_MERGE=YES (histórico) / INTEGRATION_COMPLETE pendiente de informe operativo

## Evidencia pre-merge (commit f4f3635)

| Prueba | Resultado |
| --- | --- |
| Colisiones before_fix | 4 → 0 after_fix |
| Dry-run reconciliación | 4107 = 4040+61+6+0; sites 4046 |
| Apply SQLite/Postgres #2 | inserted=0, updated=0, unchanged=4046 |
| GitHub Actions verify (PR) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29058817184 |
| GitHub Actions verify (push) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29058815223 |
| Compose smoke flujo places | channel/conversation/bot/places/appointment live+ready 200 |

## Evidencia post-merge (commit 952466b en main)

| Prueba | Resultado |
| --- | --- |
| Workflow verify en main | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29060003185 |
| scripts/verify.ps1 en main | PASSED (181 tests) |
| Compose config --quiet | PASSED |
| Dry-run post-merge | 4107 / 4046 / 3293; sum_matches_input=true |
| Apply controlado Postgres #1/#2 | inserted=4046 luego inserted=0 updated=0 unchanged=4046 |
| Migración legacy | PASSED |
| Elegibilidad / rechazo no elegible | PASSED (tests + HTTP 404 appointment) |

## Reconciliación final

- imported_as_site: 4040 · merged_duplicate: 61 · pending_review: 6 · rejected: 0  
- unique_sites: 4046 · unique_entities: 3293  
