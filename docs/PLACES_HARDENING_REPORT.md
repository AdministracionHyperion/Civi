# Places production hardening — report

Branch: `fix/places-production-hardening`  
Base commit: `b53a55fba2152d3e75f1c2e6ce068ec4cf91cace`  
HEAD: `c508b6a` (+ uncommitted WIP closing remaining gaps)  
PR: https://github.com/AdministracionHyperion/Civi/pull/3  
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
| Second apply | inserted=0 updated=0 unchanged=**4046** |

## Hardening delivered

- Tri-state `document_valid` + `document_validation_status`
- `HttpGeocoder`: rate limit, retry backoff, `low_confidence`, injectable transport + attempt persistence
- `places_presence_events` on first_seen / missing / reappeared (+ `source` column)
- Shared effective presence for nearest / partners / eligibility
- Catalog summary + OpenAPI expanded metrics
- CLI hardening (no implicit SQLite on apply; geocode CSV validation)
- Appointment 404 / 422 / 503 + OpenAPI
- CI: `fix/**` + geocode dry-run smoke + Postgres idempotency

## Work in progress (closing remaining gaps — uncommitted / pending commit)

| Gap | Status |
| --- | --- |
| PostgreSQL 16 legacy migration CI job | Implemented: `postgres-legacy-migration` + `scripts/places-catalog/validate_postgres_legacy.py` |
| Compose stack smoke CI job | Implemented: `compose-smoke` + `scripts/places-catalog/compose_smoke.py` (seed required; F/G422/G201/H + channel hop) |
| `manually_preserved` CLI | Implemented: `places_service.cli.manage_presence` + tests (`manual_preservation_removed`) |
| HTTP geocode attempt persistence | Implemented: schema extras + `HttpGeocoder` attempt records + tests |
| `import_geocodes` strict atomic default | Implemented: validate-all → single txn; `--allow-partial`; exit 0/1/2/3 |
| Geocode force / force-manual CI steps | Implemented in `verify.yml` after allow-partial |

Pending commits (not yet created): compose smoke hardening, geocode force CI steps, manage_presence + docs updates.

## Verification

| Check | Result |
| --- | --- |
| Local `scripts/verify.ps1` / focused pytest | **208 passed** (local) |
| Prior GitHub Actions (push) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29062093955 |
| Prior GitHub Actions (PR) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29062095583 |
| New CI gates on this WIP | **Pending remote CI** (postgres-legacy, compose-smoke, geocode force steps) |
| No deploy / no production apply | Confirmed |

## READY_TO_MERGE

**NO** — keep NO until remote CI is green for the new jobs (`postgres-legacy-migration`, `compose-smoke`, geocode manual/force steps) on the PR.
