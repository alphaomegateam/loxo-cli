# loxo-cli

A fast, ergonomic command-line interface for the [Loxo](https://loxo.co) recruiting
ATS/CRM REST API. It offers typed subcommands for the common resources (people, jobs,
companies, deals, candidates, activities, webhooks, reference data) plus a generic
`loxo api` escape hatch that can call any endpoint. Output is human-friendly tables on a
terminal and clean JSON when piped, so it fits both interactive use and scripts.

Unofficial — not affiliated with Loxo, Inc.

## Install

```bash
uvx loxo-cli          # run without installing
pipx install loxo-cli # or install as a user tool
```

## Quickstart

```bash
loxo configure                       # set up a profile
loxo people list --query "engineer"  # human table
loxo people list --json | jq '.'     # JSON for scripts
loxo api GET jobs/123                # raw escape hatch
```

## Configuration

Credentials resolve with the precedence **flags > environment > config file**.

Environment variables:

| Variable | Meaning |
|---|---|
| `LOXO_API_KEY` | API bearer token |
| `LOXO_API_SLUG` | Agency slug (the `{slug}` in every request URL) |
| `LOXO_BASE_URL` | API base URL (default `https://app.loxo.co/api`) |
| `LOXO_PROFILE` | Default profile name to use |

The config file lives at `~/.config/loxo/config.toml` (or `$XDG_CONFIG_HOME/loxo/config.toml`)
and is written with `0600` permissions. Example:

```toml
default_profile = "prod"

[profile.prod]
slug = "acme"
base_url = "https://app.loxo.co/api"
api_key = "your-token"

[profile.staging]
slug = "acme-staging"
# Pull the key from a secrets manager instead of storing it in plaintext:
api_key_cmd = "op read op://Private/loxo-staging/credential"
```

`api_key_cmd` is run on demand and its stdout is used as the key, so the secret never has
to live in the file. Set it without hand-editing the file via
`loxo configure --api-key-cmd "op read op://Private/loxo/credential"`. The key is never
printed by `loxo configure list`, logged, or shown in `--verbose` output.

## Commands

| Group | What it does |
|---|---|
| `people` | List/search, get, create, update people |
| `jobs` | List, get, create, update jobs |
| `companies` | List/search, get, create, update companies |
| `deals` | List, get, create, update deals |
| `candidates` | List/get/add/update candidates under a job |
| `activities` | List and add person events (activities) |
| `webhooks` | Full CRUD for webhooks (with enum validation) |
| `ref` | Reference lookups: job/activity/source/person types, lists, custom fields, hierarchies |
| `api` | Generic escape hatch — call any endpoint directly |
| `configure` | Create and list credential profiles |

Custom (dynamic) fields are supported on writes via repeatable `--field key=value`
(use `key[]=value` to force a list, e.g. hierarchy fields). Discover valid keys with
`loxo ref custom-fields`, which maps each key (`custom_text_3`) to its plain-language
name and type. Filter to one object with `--object deal` (matches the field's
`item_type`, case-insensitive) and hide built-ins with `--custom-only`.

## Output

On a terminal, list and object results render as Rich tables. Pipe the command or pass
`--json` to get machine-readable JSON; `--jq '<path>'` applies a small built-in selector
(e.g. `--jq '.[].id'`) without needing the `jq` binary.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic error |
| 2 | Usage error (bad flags/arguments) |
| 3 | Authentication/authorization failure (401/403) |
| 4 | Not found (404) |
| 5 | Rate limited (429) |
| 6 | Server error (5xx) |
| 7 | Timeout or network failure |

## Pagination

Loxo paginates differently per endpoint: cursor (`scroll_id`), offset (`page`), and keyset
(`after_id`). `loxo-cli` detects and handles all three. List commands fetch a single page by
default; pass `--all` to transparently walk every page. The generic `loxo api ... --all`
auto-detects the scheme (or force it with `--paginate scroll_id|page|after_id`).

## Contributing

```bash
uv sync                 # install dependencies
uv run pytest           # run the test suite (HTTP is mocked; no live calls)
uv run ruff check src tests
uv run black --check src tests
uv run mypy
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## License

MIT. See [LICENSE](LICENSE).
