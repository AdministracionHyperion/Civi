# Places data model

Owner: `places-service` only. Tables use the `places` / `places_` prefix.

## Concepts

| Concept | Table | Meaning |
| --- | --- | --- |
| Source record | `places_source_records` | One row per input JSON line (4107 for the national snapshot) |
| Entity (titular) | `places_entities` | Legal/natural person identified by normalized document when reliable |
| Site (sede) | `places_sites` | Physical establishment (CDA/CEA/CIA/CRC) |
| Contact | `places_contacts` | Phones/emails; not exposed on partner list by default |
| Import run | `places_import_runs` | Idempotent import metadata + SHA-256 |
| Duplicate candidate | `places_duplicate_candidates` | Possible duplicates kept for review (not auto-deleted) |

Legacy table `places` remains for sample bootstrap and transitional reads.

## Site flags (commercial vs official)

- `is_official_actor`: present in official directory snapshot
- `is_partner`: commercial alliance configured in Civi (never inferred from RUNT)
- `is_bookable` + `booking_mode=civi`: only verified partners with Civi booking

Imported official rows start as `is_partner=false`, `is_bookable=false`, `booking_mode=information_only`, `operational_status=unknown` unless name/source evidence says otherwise.

## Coordinates

`lat` / `lng` are nullable. Municipality search works without coordinates. GPS ranking only uses valid Colombia coordinates.

## Public API shape (bot)

`POST /internal/places/nearest` still returns `id`, `name`, `address`, `city`, `department`, `kind`, `distance_km`, plus optional bookable/status fields.
