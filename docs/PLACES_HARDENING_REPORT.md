# Places production hardening — report

Branch: `fix/places-production-hardening`  
Base commit: `b53a55fba2152d3e75f1c2e6ce068ec4cf91cace`  
Started: 2026-07-10

## Baseline (before code changes)

| Check | Result |
| --- | --- |
| `scripts/verify.ps1` | PASSED (181 tests) |
| `docker compose … config --quiet` | PASSED |
| Ancestors on main | `952466b` (squash), `b53a55f` (docs) |
| `scratch_runt_result.html` | Removed; ignored via `.gitignore` |

## Strategy for legacy `places.lat` / `places.lng`

**ESTRATEGIA A:** alter the legacy `places` table so `lat` and `lng` become nullable on PostgreSQL (and recreate-compatible path on SQLite). National catalog sites without coordinates can then sync to the compatibility table without NOT NULL violations. New consumers continue to use `places_sites`.

## Metrics (canonical post-integrity)

| Metric | Value |
| --- | ---: |
| Source rows | 4107 |
| unique_sites | **4046** |
| merged_duplicate | **61** |
| pending_review | **6** |
| unique_entities | 3293 |

## Hardening delivered in this branch

- Tri-state `document_valid` + `document_validation_status` on Entity / import metrics
- `HttpGeocoder`: rate limit, retry backoff, `low_confidence`, injectable transport
- `places_presence_events` on first_seen / missing / reappeared
- Catalog summary + OpenAPI expanded metrics
- CLI hardening tests; geocode dry-run CI smoke; `fix/**` on verify workflow
- Appointment 404 (`exists=false`) + 503 (`PlacesCatalogUnavailable`)

## READY_TO_MERGE

NO (await CI green on this PR)
