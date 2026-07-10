# Places data quality report

Snapshot: `places_colombia_original.json`  
SHA-256 (LF blob in git): `03df28538959a7d596c92451fecf960073b30df622e55206677faa8dfa3abba7`  
Nota: checkout Windows con CRLF puede mostrar `457b4fda…` en disco; el JSON es el mismo tras normalizar EOL.

## Baseline source rows

| Actor | Count |
| --- | ---: |
| CDA | 989 |
| CEA | 1.552 |
| CIA | 772 |
| CRC | 794 |
| **Total source records** | **4.107** |

These are source records / potential establishments, not unique companies.

## After normalization (dry-run / apply) — post integrity fix

| Metric | Value |
| --- | ---: |
| Source records reconciled | 4.107 |
| Imported as site | 4.040 |
| Merged exact duplicates | 61 |
| Pending review | 6 |
| Rejected | 0 |
| Unique entities (titulares) | 3.293 |
| Unique sites (sedes) | **4.046** |
| Duplicate candidates (review) | ~2.815 |
| Partners / bookable after import | 0 / 0 |
| Geocoded | 0 |

Reconciliation identity: `imported_as_site + merged_duplicate + pending_review + rejected = 4107`  
(`4040 + 61 + 6 + 0 = 4107`).

Document validity is tri-state (`true` / `false` / `null`) with `document_validation_status`
(`valid_with_dv`, `invalid`, `candidate_without_dv`, `ambiguous`, `missing`).

## External verification pending

- Official RUNT actor status field (not present in snapshot → status stays `unknown`)
- DIVIPOLA codes for unresolved municipality strings → `territorial_review.json`
- Geocoding (mode disabled; no Google spend in this phase)
- Published `source_updated_at` from open-data portal (snapshot extraction date ≠ official update)

Regenerate metrics with the import CLI `--dry-run`.
