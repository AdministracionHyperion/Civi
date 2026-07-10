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

## Geocoding

`PLACES_GEOCODING_MODE=disabled|http|manual_import`. Default disabled. Manual CSV import of `site_id,lat,lng,...` is preferred until an approved provider is configured.

## Rollback / restore snapshot

Keep previous snapshot + SHA-256. Restore it through the lifecycle-aware CLI:

```powershell
python -m places_service.cli.restore_snapshot --input <previous-snapshot.json> --apply --database-url <database-url>
```

Use `--dry-run` first when validating a restore. The command creates a new import run,
recalculates snapshot presence (missing sites are marked unavailable), and preserves
existing partner and booking flags.
