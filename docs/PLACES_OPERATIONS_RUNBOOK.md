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
