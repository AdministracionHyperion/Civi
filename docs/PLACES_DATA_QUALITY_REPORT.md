# Places data quality report

Snapshot: `places_colombia_original.json`  
SHA-256: `457b4fda1f29096f29b385c9b47c92596ec9658f2509009af14fb3f64c25c634`

## Baseline source rows

| Actor | Count |
| --- | ---: |
| CDA | 989 |
| CEA | 1.552 |
| CIA | 772 |
| CRC | 794 |
| **Total source records** | **4.107** |

These are source records / potential establishments, not unique companies.

## After normalization (dry-run / apply)

| Metric | Value |
| --- | ---: |
| Source records reconciled | 4.107 |
| Imported as site | 4.042 |
| Merged exact duplicates | 59 |
| Pending review | 6 |
| Rejected | 0 |
| Unique entities (titulares) | 3.293 |
| Unique sites (sedes) | 4.044 |
| Duplicate candidates (review) | 2.815 |
| Operational unknown | 4.038 |
| Operational retired (name inference) | 6 |
| Partners / bookable after import | 0 / 0 |
| Geocoded | 0 |
| Valid addresses | 3.762 |
| Partial addresses | 280 |
| Invalid addresses | 2 |
| Valid phones | 3.882 |
| Invalid / fake phones | 169 |
| Valid documents | 3.264 |
| Invalid / atypical documents | 29 |

Reconciliation identity: `imported_as_site + merged_duplicate + pending_review + rejected = 4107`.

## External verification pending

- Official RUNT actor status field (not present in snapshot → status stays `unknown`)
- DIVIPOLA codes for unresolved municipality strings → `territorial_review.json`
- Geocoding (mode disabled; no Google spend in this phase)
- Published `source_updated_at` from open-data portal (snapshot extraction date ≠ official update)

Regenerate metrics with the import CLI `--dry-run`.
