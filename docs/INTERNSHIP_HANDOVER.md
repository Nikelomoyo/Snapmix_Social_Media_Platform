# SnapMix internship handover

SnapMix is a local, working Django social network. This document maps the brief to its implementation and gives an assessor a repeatable demonstration. Read `README.md` for installation and startup commands.

Update, 24 October 2026: the app now includes **Mix Missions**, with collaborative challenges, protected invite-only collections, invitations, contributions, reactions, discussion and deadline reveals. Read `MIX_MISSIONS.md` for the feature's data model, permissions, demo steps and tests. Include `missions/` and its migrations in submissions, and exclude `private_media/` along with ordinary personal uploads.

## Feature accountability

| Requirement | Implementation | Verification |
|---|---|---|
| Sign up, login, logout, hashed passwords | Django auth, `accounts/forms.py`, `config/views.py`, CSRF-protected logout POST | `accounts.tests.PlatformTests.test_anonymous_authentication_and_signup` |
| Profiles, avatar, bio, location, edit own profile | `accounts/models.py`, `ProfileForm`, profile/edit views and templates | `accounts.test_submission.SubmissionTests.test_profile_and_image_post_round_trip_and_escaping` |
| Counts, followers/following lists, user search | Profile annotations, connections/search views, `social/models.py` | Platform page rendering, social toggle and discovery tests |
| Text/photo posts, following feed, Explore, pagination | `posts/models.py`, `posts/forms.py`, feed/detail/edit/delete views | Platform ownership, feed, pagination and discovery tests |
| Comments and accurate counts | Comment model, detail/edit/delete views, database count queries | Platform ownership and feed/comment tests |
| AJAX likes and follows | `static/app.js`, authenticated POST endpoints, database uniqueness and self-follow constraints | Platform social toggles and database guard tests |
| Private persistent one-to-one chat | `chat/models.py`, `chat/consumers.py`, `config/asgi.py`, chat template and JS | `chat.tests.SocketTests`, `chat.test_reliability.ReliabilityTests` |
| Chat unread counts, history, reconnect | Visible-page read frames, bounded cursors, latest 30/older 30 and catch-up 100-message pages | Chat HTTP/read/catch-up tests and browser send/reload check |
| Notifications and read actions | Notification model, recipient-scoped view, date grouping and filters | Platform notification ownership and personalization notification tests |
| Interests and recommendations | `accounts/topics.py`, profile preferences, `posts/recommendations.py` | `accounts/test_personalization.py` |
| Responsive desktop/mobile layout | Django templates, six CSS files, desktop sidebar/mobile bottom navigation | Manual checklist below; current audit browser inspection used desktop |
| Authentication, ownership, CSRF, escaping, image validation | Django middleware/forms, recipient/author/membership scoped queries, DOM `textContent` | Permission, CSRF, upload, escaping and real ASGI session/origin tests |
| Basic abuse limits | `accounts/middleware.py`, consumer message limit | Helper and HTTP middleware integration tests |
| Schema, constraints, migrations, seeded content | Each app's migrations; `seed_demo` / `enrich_demo` | Fresh SQLite migration and repeated demo seeding |
| HTML/CSS/vanilla JS and Django | Templates/static assets, Django ORM/session backend, Channels | No frontend build or external frontend framework needed |

Django REST Framework is not needed for this version: the brief allows it where useful, and the few JSON endpoints use Django `JsonResponse`.

## Architecture and data

Browser → Django templates/HTTP actions → Django ORM → SQLite. Chat uses a session-authenticated, origin-checked WebSocket → Channels consumer → ORM persistence → channel-layer broadcast to the two participants.

The local channel layer and rate-limit cache are in memory. A single `runserver` process supports HTTP and WebSockets through Daphne. Redis is documented for multi-process broadcasts; a shared cache is separately required for coordinated rate limits.

| Entity | Relations and safeguards |
|---|---|
| User → Profile | One-to-one; Django password hashing; profile created on signup |
| Post | Author FK, optional image/topic, creation timestamp |
| Comment | Author + post FKs; timestamp; ownership enforced in edit/delete views |
| Like | User + post; unique pair |
| Follow | Source + target; unique pair; self-follow forbidden |
| Conversation | Two ordered distinct user IDs; unique pair |
| Message | Conversation + sender; timestamp/read flag; optional retry UUID unique per conversation/sender |
| Notification | Recipient + actor + optional post; timestamp/read flag |

Deleting a user/post cascades through related database rows as defined in the models. Uploaded files are not automatically purged when records are deleted or images replaced; storage cleanup is a known limitation. Database backups alone do not include uploaded media: preserve the `media` directory too.

## Ten-minute assessment demonstration

Use demo accounts on a local development database. Use a second browser/private window for the second account so sessions remain separate.

1. Run migration and demo commands from the README. Start the server, then open `http://127.0.0.1:8000`. Keep the terminal running.
2. Sign up a new account. Select up to six interests. Confirm the For you feed shows recommendation reasons; change interests and verify results change. Switch to Following for chronological posts.
3. Edit the new account's display name, avatar, bio and location. Confirm changes appear on the profile; check its post/follow counts.
4. Find `alex` by username/display name. Follow them, inspect the following list and see their posts in Following. Unfollow and confirm the feed changes. Self-follow should be rejected by the server.
5. Create a text post, then an image post (JPEG/PNG/WebP under 5 MB and 20 megapixels). Open the detail page, edit the caption, add/edit/delete your own comment. Another account must not be able to edit or delete this content.
6. Like/unlike another account's post. Confirm the count updates without reloading. Open the other account's notifications and mark one/all read.
7. Explore: search a caption or creator, switch Photography/Thoughts, sort Most loved and use Load more. Confirm filters stay applied.
8. Start a chat with `alex`. Sign in as `alex` in the second browser. Send both directions and confirm immediate delivery and timestamps. Reload: messages must remain. Open another user's conversation URL with a third account: access must be denied.
9. Leave the recipient's chat closed, send a message and reopen Messages to see an unread count. Opening a visible chat marks loaded messages read. Count badges elsewhere refresh on navigation.
10. Briefly stop/restart your local server while keeping the chat page open. Confirm reconnection, retained pending draft, and one stored message after acknowledgement. Do not refresh/close the tab with an unsent draft: drafts are held only in that page's memory.
11. At phone width (390 px), verify bottom navigation, feed/image sizing, profile, Discover, Messages hub/individual chat, notifications and interest form. Check there is no horizontal overflow; use keyboard Tab/Enter/Escape for forms and emoji tray.

## Verification record — 23 October 2026

Commands are run from the project directory using the existing pinned virtual environment. `manage.py test` builds a separate test database; it does not use your posts or accounts.

- Initial baseline: 19 tests passed.
- Reliability tests added for actual ASGI session/origin handling, malformed socket frames, duplicate retries, long reconnect catch-up, explicit read cursor/CSRF and outsider rejection.
- Submission tests added for persisted profile/photo uploads, escaped profile content and wired HTTP authentication/write rate limits.
- Fresh SQLite database migrated through all app migrations; demo command ran twice. Result: 5 users, 25 posts, 25 comments, 11 follows, 100 likes, 3 conversations, 5 messages; all referenced demo image/avatar files existed.
- Browser check on isolated local instance: demo login, populated feed, Messages hub, connected WebSocket, send acknowledgement, message persistence after reload, and populated Discover.
- Database snapshot saved before schema update in `.qa/pre-audit-backup.sqlite3`; audit data lives under ignored `.qa/`, separate from the normal application database/media.
- Final command results are recorded in `VERIFICATION.md`.

The fresh database check reused the installed dependencies; a new dependency download/install, PostgreSQL, Redis, multiple server workers, HTTPS deployment, exhaustive assistive-technology testing and a physical mobile device were not validated in this audit.

## Honest scope and limitations

- This is internship/local demo software, not a production deployment. Follow the README deployment checklist before public hosting.
- PostgreSQL-compatible ORM fields are used, but the provided configuration is SQLite; PostgreSQL needs a driver/settings and separate integration testing.
- In-app notifications and global unread badges refresh through page navigation; only messages in an open conversation stream in real time. The sent tick means stored by the server, not a recipient read receipt.
- Chat is private by participant access control, without end-to-end encryption. The server stores readable message text. No attachments, groups, voice/video or presence tracking.
- Pending chat messages retry with a unique identifier while the page remains open. Closing/reloading loses unsent drafts; there is no offline queue.
- Recommendation ranking is deterministic and explainable, not machine learning. Caption keywords/explicit topics classify posts; images and private messages are not analyzed.
- Notification history currently displays the latest 100 entries. Feed, discovery and message history are paginated. Large-scale query/performance testing has not been performed.
- Password reset/email verification, blocking/reporting, moderation and file malware scanning are outside this version. Demo identities are fictional; stock-photo credits are in `static/demo/credits.json`.

For submission, include source, `requirements.txt`, migrations, templates/static assets, README and this documentation. Exclude `.venv`, `.env`, `.qa`, your live `db.sqlite3`, uploaded personal `media`, caches and development screenshots. An assessor can regenerate safe demo data with `seed_demo`.
