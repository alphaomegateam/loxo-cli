# Changelog

## [0.4.1]

### Fixed

- `loxo deals list` no longer fails with HTTP 422 (`Invalid parameters:
  [:per_page]`). The deals endpoint rejects `per_page` — it scroll_id-paginates
  with a server-fixed page size — so the command no longer sends a page-size
  parameter and the `--per-page` flag is dropped from `deals list` (it never
  worked). `--all` still walks every page via the scroll cursor. `paginate()`
  gained support for `per_page=None` to suppress the parameter.

## [0.4.0]

### Changed

- `loxo ref hierarchies` now returns a hierarchy field's **own** options
  (name + id) instead of the agency-wide taxonomy. It previously called
  `GET dynamic_fields/{id}/hierarchies`, which ignored the id and returned the
  global hierarchy tree (~1130 rows) for every field; it now reads the field
  detail (`GET dynamic_fields/{id}`) and emits its embedded `hierarchies`.

### Added

- `loxo ref hierarchies` accepts a field **key** (e.g. `custom_hierarchy_4`) in
  place of the numeric id, plus `--object/-o` to disambiguate. Because the same
  key is reused across objects (Person/Company/Deal each have their own
  `custom_hierarchy_4`), an ambiguous key without `--object` errors with the
  matching `item_type`/id pairs; an unknown key or a key absent from the chosen
  object also errors.

## [0.3.0]

### Added

- `loxo ref custom-fields` gains `--object/-o` and `--custom-only`. `--object`
  filters to one object's fields by matching `item_type` case-insensitively
  (e.g. `--object deal`); an unknown value errors with the available object
  types. `--custom-only` hides built-in fields, leaving just the agency-defined
  ones. The table now shows `key`, `name`, and `type` (plus `item_type` when
  unfiltered) instead of `id`/`name`, so the opaque keys (`custom_text_3`) map to
  their plain-language names at a glance. `--json` carries the full field record
  plus a derived flat `type`.

## [0.2.3]

### Changed

- `loxo activities list` drops the `--job-id` filter and gains `--company-id`.
  Loxo's `person_events` endpoint rejects `job_id` as a query parameter (HTTP
  422 `Invalid parameters: [:job_id]`), so the flag never worked. `person_id`
  and `company_id` are the only server-side filters the endpoint accepts.
  (`activities add --job-id` is unaffected — there `job_id` is a request-body
  field, not a query parameter.)

## [0.2.2]

### Fixed

- `loxo ref custom-fields` (and `job-types`, `person-types`) no longer hammer the
  API into rate-limiting (HTTP 429). These reference endpoints return their full
  list in one response and ignore the `after_id` cursor, so the keyset paginator
  looped forever. The paginator now stops when the cursor stops advancing, and
  these endpoints are fetched in a single request.
- `loxo ref activity-types` no longer fails: the `activity_types` endpoint
  rejects `after_id` with HTTP 422, so it is now fetched without a cursor.
- `loxo ref lists` now works. It targets the correct `person_lists` endpoint
  (the previous `lists` path returned 404).

## [0.2.1]

### Fixed

- `loxo --version` now reports the actual installed version (derived from package
  metadata) instead of a hardcoded string that could drift. (0.2.0 misreported
  itself as 0.1.0.)

## [0.2.0]

### Added

- `loxo configure --api-key-cmd "<command>"` to store a key-resolving command
  (e.g. a secrets-manager call) non-interactively instead of a literal key.

### Fixed

- Page-scheme pagination (`jobs --all`, `loxo api --all`) no longer stops after
  the first page when a response omits `total_count`; it now pages until the
  result set is empty.

### Changed

- CI/publish workflows updated to `actions/checkout@v7` and `astral-sh/setup-uv@v8`
  (off the deprecated Node 20 runner).

## [0.1.0]

### Added

- Initial release of `loxo-cli`.
- Credential profiles via `loxo configure` (flags > env > `~/.config/loxo/config.toml`),
  including `api_key_cmd` for pulling the key from a secrets manager.
- Typed command groups: `people`, `jobs`, `companies`, `deals`, `candidates`,
  `activities`, `webhooks`, and `ref` (reference data and custom fields).
- Generic `loxo api METHOD PATH` escape hatch for any endpoint, with `--all`
  auto-pagination.
- Scheme-aware pagination (`scroll_id`, `page`, `after_id`) with `--all`.
- TTY tables plus `--json`/`--jq` for scripting; tolerant models that preserve
  custom/dynamic fields.
- Documented exit codes (auth, not-found, rate-limited, server, timeout/network).
