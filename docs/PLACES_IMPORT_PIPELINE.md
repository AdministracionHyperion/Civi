# Places import pipeline

## Input

Preserve the original snapshot. Canonical copy:

`services/places-service/data/raw/places_colombia_original.json`

Do not overwrite `data/places/places_colombia_sin_coords.json`.

## Commands

Dry-run (metrics + reports, no DB writes):

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
python -m places_service.cli.import_catalog `
  --input services/places-service/data/raw/places_colombia_original.json `
  --dry-run `
  --report-dir services/places-service/data/reports
```

Apply (idempotent upsert):

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
$env:PLACES_DATABASE_URL="sqlite+pysqlite:///services/places-service/data/processed/places_catalog.sqlite"
python -m places_service.cli.import_catalog `
  --input services/places-service/data/raw/places_colombia_original.json `
  --apply `
  --skip-geocoding `
  --report-dir services/places-service/data/reports
```

Re-run `--apply` on the same SHA-256: no duplicate sites/entities; partner/bookable flags are preserved.

## Pipeline steps

1. Validate JSON list + SHA-256
2. Normalize documents, territory, addresses, phones, operational status
3. Exact-merge duplicates; keep multi-sede and ambiguous cases
4. Write reports under `services/places-service/data/reports/`
5. Upsert into `places_*` tables (optional `--apply`)

Geocoding defaults to `PLACES_GEOCODING_MODE=disabled`. No external calls in tests.

## Bootstrap modes

| Mode | Behavior |
| --- | --- |
| `PLACES_BOOTSTRAP_MODE=none` | Empty DB until explicit import |
| `sample` | Seeds 5 local fixtures only |
| `dataset` | Reserved; use CLI import, not silent container start |

Legacy `PLACES_AUTO_SEED_CATALOG=true` maps to `sample`.

## Manual geocode import (`import_geocodes`)

CSV columns: `site_id,lat,lng,confidence,provider,precision`.

```powershell
python -m places_service.cli.import_geocodes `
  --input path/to/geocodes.csv `
  --apply --database-url $env:PLACES_DATABASE_URL `
  --report-path services/places-service/data/reports/geocode_import_report.json
```

### Default: strict atomic

Validate all rows (CSV + DB rules) first. On any rejection, abort with **no writes** (`atomic_aborted=true`).

Flags:

- `--allow-partial` — apply valid rows; skip/reject others
- `--force` — overwrite when incoming confidence is lower than existing
- `--force-manual` — overwrite sites with `geocode_status=manual`

### Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | Success (all applicable rows OK) |
| 1 | Validation / blocked rows in strict mode (no write) |
| 2 | Partial apply (`--allow-partial` with some rejects) |
| 3 | Infrastructure error (DB/IO) |
