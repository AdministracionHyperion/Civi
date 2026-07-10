# Places production hardening — report

Branch: `fix/places-production-hardening`  
Base commit: `b53a55fba2152d3e75f1c2e6ce068ec4cf91cace`  
Final HEAD: `6686eed0efed82b84dfce49e5a5402eeedd8cfcb`  
PR: https://github.com/AdministracionHyperion/Civi/pull/3  
Started: 2026-07-10

## Historical HEADs (not final)

| HEAD | Role |
| --- | --- |
| `6164377` | Historical — CI green before remaining gaps |
| `c508b6a` | Historical — docs/gaps report; CI green; READY was NO |
| `22f938a` | Intermediate — first push of remaining gaps; legacy/verify failed (boolean DEFAULT + geocode CI) |
| `6686eed` | **Final** — boolean PG fix + legacy coexistence + geocode CI isolation |

## Baseline (before hardening branch)

| Check | Result |
| --- | --- |
| `scripts/verify.ps1` | PASSED (181 tests at branch start) |
| `docker compose … config --quiet` | PASSED |
| Ancestors on main | `952466b` (squash), `b53a55f` (docs) |

## Strategy for legacy `places.lat` / `places.lng`

**ESTRATEGIA A:** alter the legacy `places` table so `lat` and `lng` become nullable on PostgreSQL (and recreate-compatible path on SQLite). National catalog sites without coordinates can then sync to the compatibility table without NOT NULL violations. New consumers continue to use `places_sites`.

PostgreSQL boolean column defaults use `FALSE`/`TRUE` (not `0`/`1`).

## Metrics (canonical post-integrity)

| Metric | Value |
| --- | ---: |
| Source rows | 4107 |
| unique_sites | **4046** |
| merged_duplicate | **61** |
| pending_review | **6** |
| unique_entities | 3293 |
| Second apply | inserted=0 updated=0 unchanged=**4046** |

## Commits on this branch (after main)

1. `365e111` — legacy lat/lng Strategy A + v3  
2. `75f20d8` — appointment 503 + OpenAPI  
3. `f2dc8c9` — import CLI hardening  
4. `37da6be` — presence filter + tri-state docs  
5. `6164377` — CI `fix/**` + docs metrics  
6. `c508b6a` — historical hardening report  
7. `d02d7f4` — PostgreSQL legacy + compose smoke CI gates  
8. `263ecce` — audited `manage_presence` CLI  
9. `9e94232` — HTTP geocoding attempt persistence  
10. `359fe7c` — strict atomic `import_geocodes`  
11. `22f938a` — docs evidence (pre-final)  
12. `6686eed` — PG boolean defaults + legacy coexistence + geocode CI fix  

## Hardening delivered (gaps closed)

| Gap | Status |
| --- | --- |
| PostgreSQL 16 legacy migration CI | **Closed** — job `postgres-legacy-migration` |
| Compose full-stack smoke CI | **Closed** — job `compose-smoke` |
| `manually_preserved` CLI | **Closed** — `manage_presence` + tests |
| HTTP geocode attempt persistence | **Closed** — attempts + sanitization + report |
| `import_geocodes` strict atomic | **Closed** — default abort; `--allow-partial` exit 2 |

Also retained: appointment 404/422/503, presence filtering, tri-state documents, import_catalog hardening, reconciliation 4107/4046/3293/61/6.

## Verification (final HEAD)

| Check | Result |
| --- | --- |
| Local `scripts/verify.ps1` | **208 passed** |
| Local compose `config --quiet` | PASSED |
| Local PostgreSQL legacy gate | PASSED (`postgresql_legacy_migration_report.json`, lat/lng NOT NULL → nullable, second apply 0/0/4046) |
| GitHub Actions push | **PASSED** — https://github.com/AdministracionHyperion/Civi/actions/runs/29063656996 |
| GitHub Actions PR | **PASSED** — https://github.com/AdministracionHyperion/Civi/actions/runs/29063658806 |
| Jobs | `verify` success · `postgres-legacy-migration` success · `compose-smoke` success |
| Historical CI (`c508b6a` / `6164377`) | Green — historical only |
| No deploy / no production apply | Confirmed |

## Remaining risks (non-blocking)

- Compose smoke builds several images; runner time/flakiness possible on future changes.
- HTTP geocoding remains disabled by default; live provider not exercised in CI (MockTransport only).
- Six `pending_review` rows remain unresolved by design.

## READY_TO_MERGE

**YES** — PR #3 open, mergeable, final HEAD `6686eed` with all required jobs green. No merge/deploy performed by this workstream.
