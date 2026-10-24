# SnapMix

**Make something together.** Mix Missions is SnapMix's core collaborative feature: create a challenge, invite people, add one perspective each, and keep the finished shared collection. Start at `/missions/`. See the [mission walkthrough and implementation](docs/MIX_MISSIONS.md).

A working mini social network built with Django templates, HTML, CSS, vanilla JavaScript and Django Channels. Includes accounts, image profiles/posts, following feed, Explore, user search, post/comment editing and deletion, AJAX likes/follows, notifications, and private persistent one-to-one WebSocket chat with unread counts, reconnect and older-message pagination.

## Run on Windows (Python 3.12 recommended)

```powershell
cd C:\Users\nikel\OneDrive\Documents\Websites\snapmix
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo --password "LocalDemo!742"
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000. Demo usernames: `alex`, `zola`, `kai`, `mia`, `leo`; password: the value you supplied to `seed_demo`. The command creates missing records and leaves existing passwords unchanged. Demo data and bundled stock photography are optional; new accounts work without them. To use the already-created environment here, skip the venv and installation commands.

On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows executable. No Node build is required. Google Fonts are optional; system fonts work offline.

## Tests

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Tests cover authentication, password hashing, CSRF, content ownership, feed filtering, upload validation, social toggles, notifications, private HTTP history, socket rejection/delivery and reconnect. Tests use isolated temporary databases.

## Chat and Redis

`runserver` uses Daphne (first installed app), so HTTP and WebSockets share port 8000. The default in-memory channel layer needs no Redis and is suitable for a single local server process. For multiple ASGI processes, install/start Redis and set `REDIS_URL=redis://127.0.0.1:6379/0` in `.env`. For example, if Docker is installed:

```powershell
docker run --name snapmix-redis -p 127.0.0.1:6379:6379 -d redis:7-alpine
.venv\Scripts\daphne.exe -b 127.0.0.1 -p 8000 config.asgi:application
```

Use `runserver` for local static/media serving; bare Daphne requires a separate static/media server. Messages persist in SQLite regardless of channel layer. Newly opened chats load the latest 30 messages and can load older pages. Reconnecting pages catch up after the last known message in batches of 100, including gaps larger than one page. Unread counts update on page navigation; an open visible chat marks arriving messages as read. The interface shows connection status, not another user's presence. Drafts stay in the composer until the server acknowledges storage. Pending messages retry across reconnects using a UUID and a database uniqueness constraint to avoid duplicates. Validation/rate-limit errors preserve the draft and appear in a toast. Drafts are held only in the current page and are lost on closing/reloading. History GET requests do not change read state; visible chats send bounded read acknowledgements.

## Structure and data

The messenger uses a searchable conversation list, latest-activity ordering, date separators, persistent text bubbles, sent indicators and a fixed composer. On phones, chats open full-screen with a back button. The sent check means the server stored the message; it is not a delivery or read receipt. Posts use a caption-and-photo layout with inline comments, double-tap likes and copy-link sharing. Text-only posts remain supported.

`accounts`: profiles, signup, image validation, rate limiter, demo command. `posts`: posts/comments/forms. `social`: unique likes/follows. `chat`: ordered unique participant pairs, messages, WebSocket consumer. `notifications`: in-app activity records. `config`: settings, routes and page/action views. `templates` and `static`: responsive UI. Django templates provide the HTML and JSON endpoints provide small AJAX actions; a separate REST API is unnecessary for this application.

Migrations enforce unique likes, unique follows, no self-follow and ordered unique conversation pairs. ORM models use PostgreSQL-compatible fields; the supplied development configuration uses SQLite. User text is escaped in templates and chat uses DOM textContent. Images are limited to 5 MB, 20 megapixels and JPEG/PNG/WebP. All write actions use session authentication and CSRF; object ownership and conversation membership are enforced server-side. WebSockets use session authentication and origin validation. Local limits are 15 authentication attempts per IP/minute, 60 HTTP writes per user/minute and 30 chat messages per user/minute.

## Deployment limitations

This is a local-development configuration, not a production deployment. Before hosting: set a random SECRET_KEY, DEBUG=False, explicit ALLOWED_HOSTS, HTTPS/WSS and correct trusted origins; configure PostgreSQL, shared cache/rate limits and Redis; run collectstatic; serve static files and uploaded images separately (prefer a separate media origin); configure backups, logging and an ASGI process manager. The default cache and limits are per process and reset on restart. SQLite is intended for modest local use. Image moderation, malware scanning, account recovery/email verification, blocking/reporting and production operational controls are not included. There are no disappearing posts, group chats, voice or video calls. Never reuse demo credentials in production.

Framework references: [Django 5.2](https://docs.djangoproject.com/en/5.2/) and [Channels authentication/security](https://channels.readthedocs.io/en/stable/topics/security.html).

## Photography and richer demo content

Bundled Unsplash photos are credited in `static/demo/credits.json`. Portraits represent fictional demo accounts; the people photographed are not the named characters. Images are stored locally, so the app does not depend on remote image hosts at runtime. `seed_demo` automatically calls `enrich_demo` when the bundled assets exist. To enrich an existing seeded database, run `python manage.py enrich_demo`; it preserves user-created posts and avatars and can be run again without duplicating records. To restore missing image files, run `python scripts/fetch_demo_photos.py` with network access.

Profiles include an automatic cover from the most recent photo, photo collections and grid/feed views. Explore is a photo gallery; the people page shows discovery cards before a search. Empty profiles offer creation links and actual community photos. All counts come from the database.

Discover now includes caption/creator search, photography/thought filters and latest/most-liked ordering. Filter and search choices persist through pagination. The featured photo is drawn from the selected results and also remains in the complete paginated gallery.

## Personalization and connection hubs

After signup, `/interests/` asks the user to choose up to six topics. Existing accounts get a Build my mix invitation and can reopen settings through Your mix in the header, Your interests in the desktop sidebar, or their own profile. Preferences are saved per account. Choosing Browse everything clears topic selections and disables activity learning.

The For you feed and Discover’s For you sort use an explainable Django ranking: each selected topic gets 8 points; when activity learning is enabled, recent likes add 2 points each (capped at 6 per topic), and comments add 3 (also capped at 6). Posts from followed creators get 2 points; posts from the last day get 2 freshness points, or 1 for the last week. Ties use recency. Nonmatching posts stay in the results, and each recommended feed post explains its reason. This is a local, deterministic recommendation system, not a trained AI model. Turning off activity learning ignores likes/comments immediately; saved interests still apply. Following remains chronological. Private messages are never analyzed for recommendations.

Posts have an optional explicit topic. If left blank, a small caption-keyword classifier suggests a topic on save; existing records are backfilled by migration. Image content is not analyzed. Run `python manage.py migrate` when updating an existing installation. No new external service or dependency is required.

Messages includes a responsive connection hub, quick-start contacts, unread filtering, photo inspiration, draft-only conversation starters and an accessible emoji tray. Mobile retains the hub’s inspiration content below conversations. Notifications has date-grouped activity, real seven-day totals, type/unread filters and per-notification read actions with recipient ownership checks. The notification recommendations and people/photo cards remain visible on phones.

Tests cover persisted/invalid topic choices, CSRF/authentication, selected-topic ranking, learning opt-out, caption classification, chronological Following, notification filters/read ownership, and populated/empty hubs.

## Internship assessment

See [feature accountability and demonstration guide](docs/INTERNSHIP_HANDOVER.md) and [verification results](docs/VERIFICATION.md). They distinguish tested local behavior from unverified deployment capabilities.

If this project already exists on your computer, start it with:

```powershell
cd C:\Users\nikel\OneDrive\Documents\Websites\snapmix
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Leave the terminal open. If port 8000 is busy, use `127.0.0.1:8001` and open that port in your browser. If the site cannot be reached, check that the command is still running and that the browser URL matches its printed address. These commands use the existing environment; install dependencies first for a fresh checkout.

Optional `SNAPMIX_DB_PATH` and `SNAPMIX_MEDIA_ROOT` environment variables allow an isolated local test database/media directory; defaults remain `db.sqlite3` and `media/`. The audit's `.qa/` directory is local-only and must not be included in a submission.
