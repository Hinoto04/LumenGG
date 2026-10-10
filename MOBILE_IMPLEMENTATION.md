# Mobile backend rollout and API

## Deployment order

1. Back up the existing MySQL/MariaDB database using the hosting provider's
   snapshot/backup procedure. Check that the backup can be restored. No production
   migrations or deployments are executed by the implementation task.
2. Install `LumenGG/requirements.txt` and apply migrations during the normal
   deployment window. The deck migration assigns distinct UUIDs to existing
   rows. Collection duplicates are archived in `CollectedDuplicateArchive`
   before retaining the largest original PK and adding the uniqueness constraint.
3. Generate the first catalog once, then start the publisher, HTTP/ASGI servers,
   Redis and event flusher. Keep the existing TLS reverse proxy in front of Nginx.
4. Check the manifest/file endpoints, log in from a preview build, and share a
   calculator between a web viewer and the app. Distribute internal builds before
   store release.

```powershell
cd LumenGG
../.venv/Scripts/python.exe -m pip install -r requirements.txt
../.venv/Scripts/python.exe manage.py migrate
../.venv/Scripts/python.exe manage.py publish_mobile_catalog
# For Docker deployment (a Docker engine is required):
docker compose build
docker compose run --rm server python manage.py migrate
docker compose run --rm server python manage.py collectstatic --noinput
docker compose run --rm server python manage.py publish_mobile_catalog
docker compose up -d
```

Use either host-managed processes or Docker, not both publishers. Existing
database credentials remain in the untracked `SECRET_KEYS.py`. Containers share
the catalog volume and mount existing media under the configured Linux media
path; adapt the host media mount to the existing deployment's source directory.
Docker exposes Redis only within the compose network. Nginx routes `/ws/` to
Daphne and HTTP to Gunicorn. External HTTPS termination remains a deployment
prerequisite; do not use plain HTTP for production account credentials.
On Linux, ensure the existing media/static bind mounts are readable/writable by
the container application UID (10001). Secrets and generated catalogs/media are
excluded from the image build context and supplied as runtime mounts.

## Catalog publishing and recovery

`publish_mobile_catalog --watch` scans every 60 seconds with a shared-volume
process lock. Each scan clears process-local translation caches and reads public
tables in a consistent transaction (repeatable read on MySQL). It validates
references, exports an immutable SQLite snapshot, then atomically updates the
active release row. No content change means no release. Publisher failures keep
the prior release and emit `mobile_catalog_publication_failed` logs.

Images on the existing media volume are hashed when size/mtime changes. For
approved image hosts, remote sources use conditional HTTP and content hashes.
Only configured image hosts are fetched; redirects and oversized/non-image
responses fail publication rather than silently publishing stale images.
Published images have immutable hash-based URLs. Preserve release files and
image files when restoring the publisher volume.

Environment settings:

- `LUMENGG_MOBILE_CATALOG_ROOT`: persistent writable catalog directory.
- `LUMENGG_MOBILE_FETCH_IMAGES`: defaults to true; false is for isolated tests.
- `LUMENGG_REDIS_URL`: shared Channels Redis URL.
- `LUMENGG_BATTLELOG_REDIS_URL`: calculator event-buffer Redis URL.

For a rollback, stop the publisher first (otherwise it republishes the current
source), reactivate a previously validated version, correct source data, then
restart the publisher:

```powershell
docker compose stop catalog-publisher
docker compose run --rm server python manage.py publish_mobile_catalog --activate <release_version>
docker compose up -d catalog-publisher
```

After rollback, older immutable files remain downloadable. Compatibility queries
choose a release supported by the client's schema and minimum app version.
Data-schema/renderer changes require a compatible app release; ordinary data
changes use the publisher. Monitor publisher last-success logs, sync rejection
responses and ASGI/WebSocket connection errors through existing deployment logs.

## HTTP API: `/api/mobile/v1`

Mobile 1.0.5 makes decks read-only in the app. `GET /decks?scope=public&q=...&character_id=...&page=1`
returns public, non-deleted decks in pages of 30; `scope=mine` requires authentication
and includes the owner's private/unlisted decks. `GET /decks/<id>` allows public
or unlisted decks and the owner's private decks. Other private/deleted decks return
404. These endpoints reject POST/PUT/PATCH/DELETE and need no new migration.
The legacy sync contract remains for existing clients; 1.0.5 only submits collection
operations and archives previous unsent deck changes locally. Deploy these new
read endpoints before distributing 1.0.5. Decks already in the account snapshot
and previously viewed decks can still be opened offline.

Authentication uses `Authorization: Bearer <access>` with 5-minute access and
14-day rotating refresh tokens. Password changes revoke existing tokens.

| Method / path | Request / response |
| --- | --- |
| POST `/auth/login` | `username`, `password` → `access`, `refresh` |
| POST `/auth/refresh` | `refresh` → new `access`, `refresh`; old refresh is blacklisted |
| POST `/auth/signup` | `username`, `password`, `email` → tokens |
| POST `/auth/logout` | current account's `refresh` → revoke refresh |
| DELETE `/auth/account` | confirmed `password` → delete existing account |
| GET `/catalog/manifest` | `client_version=1.0.0&schema_version=1` → revision, SHA-256, size, relative download URL; supports ETag/304 |
| GET `/catalog/files/{version}` | immutable public SQLite file |
| GET `/catalog/images/{hash}.{extension}` | immutable public image |
| GET `/sync` | account snapshot |
| POST `/sync` | up to 100 immutable operations → receipts and account snapshot |
| POST `/calculators/` | `player1_character`, `player2_character`, optional player names → view/control tokens and state |
| GET `/calculators/{view_token}/state` | public viewer state; optional `language=ko/en/ja` |
| GET `/calculators/{view_token}/events` | calculator history |
| POST `/calculators/{view_token}/action` | action UUID, expected version, action payload; control header required |

Sync operation example:

```json
{
  "operations": [
    {
      "operation_id": "708e168b-b954-4623-a1f4-a54da6c9cc41",
      "entity": "collection",
      "entity_id": 123,
      "action": "upsert",
      "data": {"amount": 4}
    }
  ]
}
```

Deck operations use `entity="deck"`, a UUID `entity_id`, and `upsert`/`delete`.
The full deck payload contains `name`, `character_id`, `visibility`, optional
`description`/`keyword`/`tags`, and `cards` with `card_id`/`count`/`hand`/`side`.
The server keeps stable numeric DB IDs and derives the existing deck version.
Locked decks reject changes. A repeated operation ID returns its original
receipt; reusing an ID with another payload returns 400. Invalid individual
operations return `ok=false` while valid operations in the batch still apply.
Deletes are soft and participate in arrival order. A server receipt never uses
the client clock. Legacy web writes are serialized with app batches per account.

Calculator actions use `X-Calculator-Control` in HTTP. WebSocket clients connect
to `/ws/mobile/v1/calculators/{view_token}/`, then send `type="authenticate"`
with `control_token` and `language`. Actions use `type="action"`, `request_id`
and `payload` containing `action_id`, `expected_version` and the existing
HP/FP/passive/timer action fields. The server deduplicates action UUIDs, serializes
session mutations and broadcasts to both mobile and existing web subscribers.
An outdated version returns 409 plus the latest state. Viewer responses do not
contain control URLs/tokens or executable passive HTML/JavaScript.

## Checks

```powershell
../.venv/Scripts/python.exe manage.py check --settings=LumenGG.test_settings
../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=LumenGG.test_settings
../.venv/Scripts/python.exe manage.py test mobile_api --settings=LumenGG.test_settings --noinput
```

The repository's full isolated tests additionally require the pinned rulebook
PDF at the path already specified by `battlelog.game.spec`. MariaDB checks use
the existing `compose.test.yml` and `test.ps1 -Database mariadb` workflow; never
use production DB credentials as a disposable test account.

The pinned Expo SDK still inherits npm audit advisories in its build tooling
(including braces/node-forge/xcode). The Markdown runtime is overridden to a
patched current version. Recheck advisories and compatible SDK patches before
store submission; do not apply npm's suggested downgrade of Expo/React Native.
