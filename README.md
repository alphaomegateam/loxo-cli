# loxo-cli

A fast, ergonomic command-line interface for the [Loxo](https://loxo.co) recruiting
ATS/CRM REST API. It offers typed subcommands for the common resources (people, jobs,
companies, deals, candidates, placements, activities, webhooks, reference data) plus a generic
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
| `LOXO_MAX_RETRIES` | Retries for throttled/failed requests (default `3`; `0` disables) |

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
| `placements` | List and get placements (read-only — see note below) |
| `activities` | List and add person events (activities) |
| `webhooks` | Full CRUD for webhooks (with enum validation) |
| `ref` | Reference lookups: job/activity/source/person types, lists, custom fields, hierarchies |
| `api` | Generic escape hatch — call any endpoint directly |
| `configure` | Create and list credential profiles |

Custom (dynamic) fields are supported on writes via repeatable `--field key=value`
(use `key[]=value` to force a list, e.g. hierarchy fields). Discover valid keys with
`loxo ref custom-fields`, which maps each key (`custom_text_3`) to its plain-language
name and type. Filter to one object with `--object deal` (matches the field's
`item_type`, case-insensitive) and hide built-ins with `--custom-only`. For a
hierarchy field, `loxo ref hierarchies custom_hierarchy_4 --object deal` lists
its options (name + id); the FIELD argument also accepts the numeric field id.

### Placements are read-only

`placements` exposes only `list` and `get`. The API's write endpoints accept
`custom_*` parameters — they pass the endpoint's `custom_*` prefix filter — but
never assign them. Any agency that marks a placement custom field **required**
therefore cannot create or update a placement through the API at all: the write
fails validation on a field the API will not let you set. Verified against a
live agency; every encoding returns an identical 422 naming the same fields as
missing (option ids, option names, `{"id","value"}` objects, `_id`-suffixed
keys, a `{"placement": {...}}` wrapper, and a `dynamic_fields` object).

`loxo api POST placements --data @body.json` is still there if your agency marks
no placement custom field required.

`placements list` has three **server-side** filters — `--job`,
`--person-global-status-id`, `--include-related-agencies`. Prefer `--job` over
`--filter job=...`: `--filter` narrows a page after it arrives, while `--job`
narrows on the server, so `--all` walks far fewer pages.

```bash
loxo placements list --job 3406638
loxo placements list --all -q "designer" --json | jq '.[].person.name'
```

## Output

On a terminal, list and object results render as Rich tables. Pipe the command or pass
`--json` to get machine-readable JSON; `--jq '<path>'` applies a small built-in selector
(e.g. `--jq '.results'`, `--jq '.[].id'`, `--jq '.results.0.title'` — the leading `.` is
optional) without needing the `jq` binary.

`--json` output is always plain (never ANSI-colored) so it can be piped straight into
`jq`, `json.loads`, etc. Table color is disabled automatically when stdout is not a
terminal, and can be turned off explicitly with `--no-color` or the
[`NO_COLOR`](https://no-color.org/) environment variable.

## Filtering vs. search

`--query`/`-q` (and `api ... -p query=`) is a **ranked full-text search**, not an exact
filter: the API returns a broad, relevance-ordered set (e.g. `-q "VP of Digital"` also
matches unrelated `VP *` roles further down). To narrow a result set to exact matches, add
`--filter field=value` (repeatable) on list commands — it post-filters the returned records
client-side. Object-valued fields match on their name, so `--filter status=Active` matches a
`status` of `{"id": 70251, "name": "Active"}`. Example:

```bash
loxo jobs list -q "VP of Digital" --filter status=Active
```

## Retries

Retries are **on by default** for every invocation: a throttled (429), 5xx, timed-out, or
connection-refused request is retried up to 3 times with exponential backoff and jitter,
honoring a `Retry-After` header when the server sends one. A 60-second wall-clock budget
caps the accumulated backoff for a single request; because that budget only gates the
*next* sleep, the attempt already in flight still gets its own 30-second timeout, so the
worst case for one request is nearer ~90 seconds. Any wait of a second or more prints a
one-line notice to stderr (stdout stays clean for `--json`); pass `--quiet` to suppress it.
A library consumer can move that one-second bar with `RetryPolicy(notice_threshold=...)`.
Using the client as a library instead? See [Logging](#logging) — there the notice is a log
record, and you decide whether it is shown.

Retries are method-aware: `GET`/`HEAD`/`PUT`/`DELETE`/`OPTIONS` retry on all of the above,
while `POST` retries only when the request provably did not take effect (a 429, or a
connection that was never established), so a timed-out write is never replayed into a
duplicate record.

```bash
loxo --retries 0 jobs list          # fail fast, the pre-0.6.0 behavior
LOXO_MAX_RETRIES=0 loxo jobs list   # same, via the environment
loxo --retries 5 jobs list --all    # more patient
loxo --quiet jobs list --all        # no retry notices on stderr
```

## Logging

Since 0.6.1 the client never writes to stderr itself — it logs, on the `loxo_cli` logger,
and the package carries a `NullHandler` so it stays completely silent until your
application asks for output:

- per-request lines (method and URL, only when the client is built with `verbose=True`) at
  `DEBUG`
- the long-retry notice at `WARNING`, because a retry means the service is degraded
- a *short* retry — one whose wait is under `RetryPolicy.notice_threshold` (default `1.0`
  second) — at `DEBUG`, so it is quiet at a default logging level but never silently
  dropped for someone watching at `DEBUG`

Headers are never logged, so the API key cannot reach a log record.

**Watch the interaction between the two.** A client built with `verbose=True` reports each
retry with the detailed `DEBUG` line *instead of* the `WARNING` notice — they never
double-report the same retry. So a library consumer who sets `verbose=True` but configures
logging only at `WARNING` sees **nothing** for retries. Either leave `verbose=False` and
watch at `WARNING`, or set `verbose=True` and drop the level to `DEBUG`.

```python
import logging

logging.basicConfig(level=logging.WARNING)   # surfaces retry notices
logging.getLogger("loxo_cli").setLevel(logging.DEBUG)  # ...and request lines
```

A service on a request path usually wants *every* retry at `WARNING`, because its policy
is short enough that the computed backoff never reaches a second. Set the threshold to
`0.0` on the policy rather than dropping the whole logger to `DEBUG`:

```python
from loxo_cli.retry import RetryPolicy

RetryPolicy(max_retries=1, max_delay=2.0, max_elapsed=5.0, notice_threshold=0.0)
```

The CLI attaches its own stderr handler, which is why `loxo --verbose` and the retry
notice still appear in a terminal. `--quiet` raises that handler's threshold to errors
only and wins over `--verbose`; neither affects command results on stdout.

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

Since 0.6.0 the retryable codes (5, 6, 7) are reached only after retries are exhausted, so
they are no longer immediate — exit 5 in particular can now take up to ~90 seconds. Pass
`--retries 0` to get the old fail-fast behavior back.

## Pagination

Loxo paginates differently per endpoint: cursor (`scroll_id`), offset (`page`), and keyset
(`after_id`). `loxo-cli` detects and handles all three. List commands fetch a single page by
default; pass `--all` to transparently walk every page. The generic `loxo api ... --all`
auto-detects the scheme (or force it with `--paginate scroll_id|page|after_id`).

## Async

Scripts: `async with` builds a client, runs the work, and closes the pool on exit.

```python
import asyncio

from loxo_cli.client import AsyncLoxoClient
from loxo_cli.config import load_settings
from loxo_cli.pagination import apaginate


async def main() -> None:
    settings = load_settings()
    async with AsyncLoxoClient(settings) as client:
        job = await client.get("jobs/123")
        print(job)

        async for candidate in apaginate(
            client, "jobs/123/candidates", scheme="scroll_id", items_key="candidates"
        ):
            print(candidate["id"])


asyncio.run(main())
```

Long-lived services build **one** client at startup and `aclose()` it at shutdown, so the
connection pool is reused across requests. `AsyncLoxoClient` is safe to share across
concurrent tasks. In FastAPI that is a `lifespan`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from loxo_cli.client import AsyncLoxoClient
from loxo_cli.config import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.loxo = AsyncLoxoClient(load_settings())
    try:
        yield
    finally:
        await app.state.loxo.aclose()


app = FastAPI(lifespan=lifespan)


# Retry notices are WARNING records on the `loxo_cli` logger and are dropped
# until something handles them. Under uvicorn's logging config they show up as
# soon as the level allows; otherwise configure it yourself. See "Logging".


@app.get("/jobs/{job_id}")
async def get_job(job_id: int):
    return await app.state.loxo.get(f"jobs/{job_id}")
```

The retry budget (`max_elapsed`) is **per request**, so `apaginate` gives every page its
own budget: under sustained throttling a large sweep can run for far longer than any
single request's bound. Bound a whole sweep with `asyncio.timeout(...)` rather than
expecting `max_elapsed` to do it.

```python
async def sweep(client: AsyncLoxoClient) -> None:
    async with asyncio.timeout(120):
        async for candidate in apaginate(
            client, "jobs/123/candidates", scheme="scroll_id", items_key="candidates"
        ):
            print(candidate["id"])
```

Retries are on by default. Pass a policy to tune or disable them — a service
answering an HTTP request should be far less patient than a CLI. Three settings work
together, and tuning only the first leaves the other two at CLI defaults:

```python
from loxo_cli.client import AsyncLoxoClient
from loxo_cli.config import load_settings
from loxo_cli.retry import RetryPolicy

client = AsyncLoxoClient(
    load_settings(),
    # One retry, capped backoff, ~5s of total retry budget.
    retry=RetryPolicy(
        max_retries=1,
        max_delay=2.0,
        max_elapsed=5.0,
        # Without this, every retry this policy makes is under the 1.0s
        # default notice threshold and so lands at DEBUG, not WARNING.
        notice_threshold=0.0,
    ),
    # Per-attempt, and the real worst case for a browser waiting on this
    # response: max_elapsed only gates whether a *further* retry is allowed,
    # so a single hung request would otherwise block for the 30s default.
    timeout=5.0,
)
```

`timeout` is available on `LoxoClient`, `AsyncLoxoClient`, `build_client`, and
`build_async_client`, and defaults to `loxo_cli.client.TIMEOUT` (30 seconds).

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
