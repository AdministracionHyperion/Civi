# Geocode dry-run validation evidence (Manizales + Santander)

Isolated local Postgres validation after merging Manizales (#4) and Santander (#5).

## What is kept here

| File | Purpose |
|---|---|
| `manizales_geocode_dry_run_report.json` | Dry-run against ephemeral DB (44/44 resolved) |
| `santander_geocode_dry_run_report.json` | Dry-run against ephemeral DB (153/153 resolved) |
| `validation_summary.json` | Sanitized rollup (no passwords) |
| `snapshot_before.json` / `snapshot_after.json` | Prove dry-run did not write coords |

## What is not kept

- Catalog import dumps (`processed/`, full reconciliation artifacts)
- Temporary database dumps
- URLs with plaintext passwords

## How to reproduce (local only)

```powershell
$env:PYTHONPATH="services/places-service/src;packages/python-common/src"
$env:PLACES_VALIDATION_ADMIN_URL="postgresql+psycopg://USER:***@localhost:5432/postgres"
$env:PLACES_VALIDATION_DATABASE_URL="postgresql+psycopg://USER:***@localhost:5432/civi_geocode_validation_tmp"

python scripts/places-catalog/geocode_validation_tmp.py create
python scripts/places-catalog/geocode_validation_tmp.py migrate

python -m places_service.cli.import_catalog `
  --input services/places-service/data/raw/places_colombia_original.json `
  --apply --skip-geocoding `
  --database-url $env:PLACES_VALIDATION_DATABASE_URL `
  --report-dir services/places-service/data/reports/validation/catalog_import_scratch

python scripts/places-catalog/geocode_validation_tmp.py check-manizales
python scripts/places-catalog/geocode_validation_tmp.py check-santander

python -m places_service.cli.import_manizales_geocodes --dry-run `
  --database-url $env:PLACES_VALIDATION_DATABASE_URL `
  --no-source-records-fallback `
  --report-path services/places-service/data/reports/validation/manizales_geocode_dry_run_report.json

python -m places_service.cli.import_santander_geocodes --dry-run `
  --database-url $env:PLACES_VALIDATION_DATABASE_URL `
  --report-path services/places-service/data/reports/validation/santander_geocode_dry_run_report.json

python scripts/places-catalog/geocode_validation_tmp.py drop
```

Do **not** pass `--apply` / `--force*` on the geocode CLIs for this validation.
Do **not** point the helper at non-localhost hosts.
