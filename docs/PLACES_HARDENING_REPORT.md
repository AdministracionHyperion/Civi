# Places production hardening — report

Branch: `fix/places-production-hardening`  
Base commit: `b53a55fba2152d3e75f1c2e6ce068ec4cf91cace`  
HEAD: `6164377fe931d916bc4bf7144dc80abd0f55bffc`  
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

## Hardening delivered

- Tri-state `document_valid` + `document_validation_status`
- `HttpGeocoder`: rate limit, retry backoff, `low_confidence`, injectable transport
- `places_presence_events` on first_seen / missing / reappeared
- Shared effective presence for nearest / partners / eligibility
- Catalog summary + OpenAPI expanded metrics
- CLI hardening (no implicit SQLite on apply; geocode CSV validation)
- Appointment 404 / 422 / 503 + OpenAPI
- CI: `fix/**` + geocode dry-run smoke + Postgres idempotency

## Verification (HEAD `6164377`)

| Check | Result |
| --- | --- |
| `scripts/verify.ps1` | PASSED (**193** tests) |
| GitHub Actions (push) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29062093955 |
| GitHub Actions (PR) | PASSED — https://github.com/AdministracionHyperion/Civi/actions/runs/29062095583 |
| No deploy / no production apply | Confirmed |

## Remaining gaps (keep READY_TO_MERGE=NO)

1. Dedicated **PostgreSQL 16 legacy container** job (create NOT NULL schema → migrate → import 4107 → second import) is implemented in code/tests helpers but not yet a full remote container gate beyond clean Postgres idempotency.
2. Full Compose stack smoke (channel→appointment) is not a remote CI gate.
3. `manually_preserved` operational CLI/API with mandatory actor/reason is only partially covered via presence model/events.

## READY_TO_MERGE

**NO**
