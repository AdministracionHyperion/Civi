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

## Presence (`source_presence_status`)

| Value | Meaning |
| --- | --- |
| `present` | In latest official snapshot |
| `missing` | Absent from latest snapshot (search/booking suppressed unless overridden) |
| `manually_preserved` | Ops override: remain searchable despite snapshot absence |

Effective search/eligibility uses shared presence rules (present or manually preserved). Preserve does **not** flip `is_partner` / `is_bookable`.

### Presence events (`places_presence_events`)

Audit rows for presence transitions. Notable columns:

- `event_type`: e.g. `first_seen`, `missing`, `reappeared`, `manually_preserved`, `manual_preservation_removed`
- `source`: origin of the change (`import`, `manual_operation`, …)
- `actor` / `reason`: required for manual CLI operations
- `previous_status` / `new_status`

## Geocode attempts (`places_geocode_attempts`)

One row per provider/manual attempt. Key columns:

- `provider`, `status`, `attempt_number`
- `http_status`, `error_code`, `error_message` (HTTP geocoder)
- `lat`, `lng`, `confidence`, `precision`
- `query`, `response_payload`, `attempted_at`, `completed_at`
- optional `import_run_id` / `provider_record_id`

Manual CSV import also writes attempt rows with `status=manual`.

## Public API shape (bot)

`POST /internal/places/nearest` still returns `id`, `name`, `address`, `city`, `department`, `kind`, `distance_km`, plus optional bookable/status fields.
