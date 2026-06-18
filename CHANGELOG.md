# Changelog

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
