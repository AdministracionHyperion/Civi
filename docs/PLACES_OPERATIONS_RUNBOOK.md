# Places operations runbook

## Update national catalog

1. Place a new snapshot beside the preserved original (do not overwrite original).
2. Dry-run and inspect `services/places-service/data/reports/reconciliation.json`.
3. Confirm `sum_matches_input` and actor counts.
4. Apply against the places DB (`PLACES_DATABASE_URL`).
5. Re-apply once to confirm idempotency.
6. Check `GET /internal/places/catalog/summary` (internal token).

## Configure a partner / bookable site

Never set bookable from the official directory alone. Update `places_sites` (or admin tooling) explicitly:

- `is_partner = true`
- `is_bookable = true`
- `booking_mode = civi`

Subsequent catalog imports preserve these commercial flags.

## Search behavior

- Municipality: filter by municipality / code; empty list + `no_coverage_in_municipality` if none.
- GPS: Haversine within `PLACES_SEARCH_RADIUS_KM` (default 40); no national fallback.
- Retired / inactive / suspended excluded from normal search.

## Appointment guard

`appointment-service` calls `GET /internal/places/{site_id}/booking-eligibility` before create. Non-bookable → HTTP 422 `place_not_bookable`. Canonical name/address/city come from places-service.

## Manually preserved sites

Operational override when a site must remain searchable despite snapshot absence:

```powershell
python -m places_service.cli.manage_presence preserve `
  --site-id <site_id> --actor <ops-user> --reason "<why>" `
  --database-url $env:PLACES_DATABASE_URL

python -m places_service.cli.manage_presence remove-preservation `
  --site-id <site_id> --actor <ops-user> --reason "<why>" `
  --database-url $env:PLACES_DATABASE_URL
```

`--actor` and `--reason` are mandatory (min 3 chars). Preserve does **not** auto-set
`is_partner` / `is_bookable`. Events are written to `places_presence_events` with
`source=manual_operation`.

Event types:

- `preserve` → `event_type=manually_preserved`
- `remove-preservation` → `event_type=manual_preservation_removed`

## Geocoding

`PLACES_GEOCODING_MODE=disabled|http|manual_import`. Default disabled. Manual CSV import of `site_id,lat,lng,...` is preferred until an approved provider is configured.

`import_geocodes` is **strict atomic by default**: any validation error aborts with exit 1 and no writes. Use `--allow-partial` for best-effort apply (exit 2). Exit 0 = OK, 3 = infra. See `PLACES_IMPORT_PIPELINE.md`.

### Manizales validated geocodes (first city rollout)

Input (committed): `services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv`

- 44 establishments (14 CDA, 15 CEA, 8 CIA, 7 CRC)
- Resolves exclusively by official source `id` → `places_sites.source_place_id`
- Validates Colombia / Caldas / Manizales + bbox before any write
- Persists `lat`, `lng`, `confidence`, `provider`, `precision`, `geocode_validation_status`
- `approximate_not_confirmed` is never presented as confirmed (`location_confirmed=false`)
- Does **not** touch other cities; does **not** enable `--force` by default

Dry-run (CSV validation only, no DB):

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
python -m places_service.cli.import_manizales_geocodes `
  --input services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv `
  --dry-run `
  --report-path services/places-service/data/reports/manizales_geocode_import_report.json
```

Apply (after national catalog is already imported so `source_place_id` exists):

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
python -m places_service.cli.import_manizales_geocodes `
  --input services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv `
  --apply --database-url $env:PLACES_DATABASE_URL `
  --report-path services/places-service/data/reports/manizales_geocode_import_report.json
```

Map (local): open `services/places-service/static/manizales_map.html?api=http://127.0.0.1:8085&token=<INTERNAL_SERVICE_TOKEN>`  
GeoJSON: `GET /internal/places/geojson?city=Manizales&department=Caldas`

### Santander validated geocodes (prioritized metro)

Input (committed): `services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv`

- 153 establishments (37 CDA, 56 CEA, 25 CIA, 35 CRC)
- Municipalities: Bucaramanga 81, Floridablanca 29, Girón 23, Piedecuesta 20
- Validation mix: 65 `confirmed_business` / 30 `confirmed_address` / 58 `approximate_not_confirmed`
- Resolves by official source `id` → `places_sites.source_place_id` (no `source_records` fallback in routine apply)
- Validates each row against **its municipality bbox** (Girón stays `-73.18`…`-73.15`; do not widen)
- Aborts if aggregate counts diverge from the scope contract (153; 81/29/23/20; 37/56/25/35; 65/30/58)
- Shared engine: `validated_geocode_import` + `geocode_scopes` (Manizales remains a thin wrapper)
- Does **not** modify Manizales rows; does **not** enable `--force` by default
- Resolves `source_place_id` with exactly one DB hit (`unknown_site` / `duplicate_source_place_id`); re-checks department, municipality, kind and protections inside the write transaction

Prerequisites before apply:

1. Schema v5 migrated (`source_place_id`, `geocode_validation_status`)
2. National catalog imported/reconciled so CSV ids resolve via `places_sites.source_place_id`
3. Staging dry-run with DB, then manual apply **without** `--force`

Dry-run (CSV validation only, no DB):

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
python -m places_service.cli.import_santander_geocodes `
  --input services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv `
  --dry-run `
  --report-path services/places-service/data/reports/santander_geocode_import_report.json
```

Apply (staging / explicit ops only — not production from this PR):

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
python -m places_service.cli.import_santander_geocodes `
  --input services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv `
  --apply --database-url $env:PLACES_DATABASE_URL `
  --report-path services/places-service/data/reports/santander_geocode_import_report.json
```

Map (local): open `services/places-service/static/santander_map.html?api=http://127.0.0.1:8085&token=<INTERNAL_SERVICE_TOKEN>`  
GeoJSON (one call per municipality):  
`GET /internal/places/geojson?city=Bucaramanga&department=Santander` (also Floridablanca, Giron, Piedecuesta)

### Ephemeral dry-run validation evidence

Sanitized dry-run reports (Manizales 44/44 + Santander 153/153 against an isolated local Postgres copy of the national catalog) live under:

`services/places-service/data/reports/validation/`

Reproduce with `scripts/places-catalog/geocode_validation_tmp.py` (localhost-only; credentials via env). See that folder’s `README.md`. Never use `--apply` / `--force*` on geocode CLIs for this check.

## Local CI gates (Postgres legacy + compose smoke)

PostgreSQL legacy nullable lat/lng + re-apply idempotency:

```powershell
$env:PLACES_DATABASE_URL="postgresql+psycopg://civi:civi@localhost:5432/civi"
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
python scripts/places-catalog/validate_postgres_legacy.py
# exit 0 + report passed=true under services/places-service/data/reports/
```

Compose smoke (places nearest A–C/E/F, appointment G422/G201/H, channel→bot→places hop):

```powershell
$env:INTERNAL_SERVICE_TOKEN="change-me-local-only"
python scripts/places-catalog/compose_smoke.py
# exit 0 when all required cases pass; report: compose_smoke_report.json
# Seed failure fails the gate (F/G never skip-as-pass)
```

Both scripts are also wired in `.github/workflows/verify.yml` (`postgres-legacy-migration`, `compose-smoke`).

## Rollback / restore snapshot

Keep previous snapshot + SHA-256. Restore it through the lifecycle-aware CLI:

```powershell
python -m places_service.cli.restore_snapshot --input <previous-snapshot.json> --apply --database-url <database-url>
```

Use `--dry-run` first when validating a restore. The command creates a new import run,
recalculates snapshot presence (missing sites are marked unavailable), and preserves
existing partner and booking flags.
