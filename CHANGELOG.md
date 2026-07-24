# Changelog

## [0.6.0]

### Added

- `AsyncLoxoClient`, an async twin of `LoxoClient` over `httpx.AsyncClient`,
  plus `build_async_client()`. Mirrors the sync client method-for-method
  (`request`/`get`/`post`/`put`/`delete` are coroutines, `close()` becomes
  `aclose()`). Safe for concurrent use from many tasks; long-lived services
  should build one at startup and `aclose()` it at shutdown so the connection
  pool is reused.
- `apaginate()`, the async counterpart of `paginate()`. Both now drive the same
  per-scheme state machines, so the `after_id` non-advancing-cursor guard and
  the missing-`total_count` guard behave identically in sync and async.
- Automatic retry with exponential backoff and jitter, honoring `Retry-After`
  (both integer-seconds and HTTP-date forms). Retries are **on by default**.
- `--retries N` and `LOXO_MAX_RETRIES` to control or disable retrying.
- `LoxoError.is_rate_limited`, `.retry_after`, and `.attempts`.

### Changed

- **Behavior change for scripts.** A throttled or failing request that
  previously returned immediately is now retried up to 3 times before
  surfacing the same error and the same exit code. A sustained 429 that used
  to exit 5 within a second can now take much longer: a 60-second wall-clock
  budget caps how much accumulated backoff a request may still sleep through,
  but that budget only gates the *next* sleep — the attempt already in flight
  when it's hit still gets its own request timeout, so the worst case is
  nearer ~90 seconds. Under a sustained `Retry-After: 30`, only 2 of the 3
  configured retries actually run before the budget cuts off the third. Pass
  `--retries 0` or set `LOXO_MAX_RETRIES=0` to restore the old fail-fast
  behavior.
- Retries are method-aware. `GET`/`HEAD`/`PUT`/`DELETE`/`OPTIONS` retry on 429,
  5xx, timeouts, and connection failures. `POST` retries only when the request
  provably did not take effect — a 429, or a connection that was never
  established — so a timed-out write is never replayed into a duplicate record.
  Note that a `DELETE` whose first attempt times out after committing will
  return 404 on retry and surface as exit 4, for an operation that succeeded.

### Fixed

- The `page` scheme no longer raises `TypeError` when a response reports
  `total_count` without a `per_page` and the caller passed `per_page=None`. It
  now falls through to the empty-page stop instead.

## [0.5.1]

### Fixed

- `LoxoSettings` no longer prints the API key in its `repr()`. The `api_key`
  field is now `repr=False`, so an incidental `repr()` (an unhandled exception
  with the settings object in a traceback local, a pytest assertion dump, a
  debug print) can no longer surface the live key. (#13)
- `loxo configure` now writes valid TOML for any value. Config serialization
  was hand-rolled with unescaped f-strings, so an `api_key_cmd` containing
  quotes or backslashes — or a profile name containing `.`/`]` — produced a
  file that `tomllib` rejected on the next invocation, bricking the profile.
  Serialization now goes through `tomli-w`. (#14)
- `--data` now rejects well-formed JSON that isn't an object (e.g. `[1,2]`,
  `"str"`, `42`) with a clean `--data must be a JSON object` error instead of
  letting it through to fail later as an uncaught `TypeError`. The guard covers
  all three input paths (inline, `@file`, and stdin). (#15)

## [0.5.0]

### Fixed

- `loxo jobs list` no longer crashes with a Pydantic `ValidationError`: the
  Loxo API returns `status` as a nested object (`{"id", "name"}`), not a string,
  so `Job.status` now accepts an object (a bare string still validates too).
  Tables show the object's `name` (e.g. `Active`) instead of raw JSON. (#6)
- `--json` output is no longer ANSI-colorized. Rich was forcing color into
  pipes whenever `FORCE_COLOR` was set, wrapping the JSON in escape codes and
  breaking `json.loads`/`--jq`. JSON is now always emitted plain. Table color is
  also disabled when stdout is not a TTY, and `--no-color` / `NO_COLOR` are
  honored. (#7)
- `--jq` now accepts bare key paths (`results`, `results.0.title`) in addition
  to leading-dot paths (`.results`), supports numeric list indexes, and reports
  a clean `Error:` message instead of a raw `ValueError` traceback on an
  unusable expression. (#8)
- `loxo api ... --all` no longer sends `per_page` to scroll (`scroll_id`)
  endpoints, which rejected it with HTTP 422 (e.g. `companies`). (#9)

### Added

- `--filter field=value` (repeatable) on list commands post-filters the
  returned records client-side by exact match. Object-valued fields match on
  their `name`, so `--filter status=Active` works. This complements `--query`,
  which is a ranked full-text search rather than an exact filter. (#10)

### Changed

- `--query`/`-q` help now states it is a ranked full-text search, not a filter;
  the README documents the query-vs-`--filter` distinction. (#10)
- `api --raw` help text corrected: it is a no-op, and raw JSON requires the
  global `--json` flag (without it the response renders as a table). (#11)

## [0.4.2]

### Fixed

- `loxo companies list` and `loxo companies search` no longer fail with HTTP 422
  (`Invalid parameters: [:per_page]`) — the same issue fixed for deals in 0.4.1.
  The companies endpoint rejects `per_page` (it scroll_id-paginates with a
  server-fixed page size), so the commands no longer send a page-size parameter
  and the `--per-page` flag is dropped from both. `--all` still walks every page
  via the scroll cursor.

  Audited every other supported endpoint: `people`, `jobs`, `person_events`
  (activities), and `jobs/{id}/candidates` all accept `per_page`; `webhooks`
  rejects it but the CLI never sends it there. No other commands are affected.

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
