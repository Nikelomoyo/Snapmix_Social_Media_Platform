# Mix Missions — SnapMix's shared activity feature

Implemented 24 October 2026. Open `/missions/`, or choose Missions in the desktop sidebar/mobile bottom navigation. Successful logins now open the mission board; the home feed also links to it.

## The experience

1. Start a mission with a title, prompt, optional cover, closing time and visibility. Prompt starters can prefill a colour challenge, a good-moment collection or a shared weekend plan.
2. The host is automatically a member. Anyone signed in can join an open mission; invite-only missions need an invitation.
3. Each member adds one photo, text response, or both. They can edit or remove their own contribution until closing. Another member cannot change it.
4. Members appreciate contributions, reply in the discussion and pass an invitation to another registered username. Invitations have accept/decline actions. Repeating an invite does not send duplicate notifications or reinvite someone who declined.
5. At the deadline, the live collection becomes the finished collection. Contributions lock, while appreciation and discussion remain available. The host can finish early after a confirmation. Closing is irreversible through the app.

Contributions are visible while the mission is open. The reveal is the finished shared collection, rather than a hidden-content countdown. The board has In the making, My missions, Invitations and The reveal tabs, search and pagination.

## Interaction and notifications

Appreciation toggles update through CSRF-protected AJAX. Mission pages show a countdown and check for collection/member/discussion changes every 15 seconds while visible. A refresh notice appears when someone contributes or replies; it does not erase an unsent discussion draft automatically. The refresh button warns before clearing that draft.

Invitations notify the recipient. Joining/contributing/replying notify the host, accepting an invitation notifies its sender, and an early finish notifies members. Self-notifications are skipped. Notifications link to the relevant mission and have a Missions filter.

Deadline closing is checked against server time on each request. It works without Redis, a scheduler or a background worker. Automatic deadline closure does not send a background notification; opening the page or using its update check reveals the finished state. Mission discussions are a paginated message board, separate from the existing real-time one-to-one chat.

## Data and code

| Model | Purpose and constraint |
|---|---|
| Mission | Host, prompt, cover, visibility, deadline and optional early-close timestamp |
| Membership | Unique mission/user participation |
| Invitation | Unique mission/recipient, sender, pending/accepted/declined status |
| Contribution | One contribution per mission/author, optional image and text, creation/update timestamps |
| Reaction | Unique appreciation per contribution/user |
| Discussion | Member-written mission replies with timestamps |
| Notification.mission | Optional relation linking existing in-app notifications to missions |

`missions/views.py` scopes every detail, history/update and image request to visible missions. Write views additionally enforce membership, ownership and deadline rules. Relevant mission writes use database transactions; PostgreSQL row locks serialize participant/close actions. SQLite remains intended for modest local development.

`missions/forms.py` validates titles, prompts, 5-minute-to-30-day future deadlines, nonempty contributions and the existing JPEG/PNG/WebP size/pixel limits. A custom image widget supports keeping/replacing/clearing protected images without exposing storage URLs.

`missions/storage.py` stores all mission photos under `private_media/`, outside public `MEDIA_ROOT`. The only photo URLs go through a login/mission-permission checked `FileResponse` with `Cache-Control: private, no-store`. Do not publish this directory as static/public media when hosting. Back up the database, ordinary `media/` and `private_media/` together. Override the protected storage location with `SNAPMIX_MISSION_MEDIA_ROOT` if required.

Open missions are visible to every signed-in account. Invite-only missions, participant lists, discussion and photos are visible to members, the owner and pending invitees. Pending invitees can preview before accepting; declining removes that access unless they were already a member. Any member can invite others, and this policy is stated on the page. There is no invitation revocation, member removal or end-to-end encryption in this version. As with existing uploads, replaced/deleted files are retained in storage until manually cleaned up; deleted contributions no longer have an accessible photo endpoint.

Templates live in `templates/missions/`; the custom form widget lives in `missions/templates/missions/` so Django's form renderer can find it. `static/missions.css` uses the current black/mint palette, and `static/missions.js` handles appreciation and update notices. Other social features remain connected to their original models/routes.

## Setup and demo

No new package dependencies are needed. From the project directory:

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_missions
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

The mission seed command requires the five existing fictional demo accounts. On a fresh installation, run `seed_demo --password "LocalDemo!742"` instead; it creates them and calls `seed_missions`. Existing demo passwords are preserved.

Examples include two open public missions, one finished collection and one invite-only mission with a pending invitation for `alex`. Re-running the command preserves existing missions/contributions and does not duplicate files or rows. Open examples keep their original deadlines; they naturally become finished examples after three days.

## Assessment demonstration

- Sign in as `alex`, open Missions and inspect the three open examples visible to this account. One is a private invitation.
- Open the colour mission, inspect the photo collection, toggle Appreciate and open Edit my part. Keep the attached image while changing its text; verify the collection updates.
- In the invitation tab, preview the private example, accept it, contribute and pass an invitation to another demo account. The recipient sees a linked in-app notification.
- In two separate browser sessions, open the same mission. Submit a reply in one; the other gets an update notice within approximately 15 seconds while visible.
- Open The reveal to inspect the finished weekend collection. Contribution controls are absent; discussion and appreciation still work for its members.
- Create a separate mission for a demonstration of early closing. Finish it as the host, then attempt to contribute: the server rejects the write. Deadline closure is also covered by an automated clock-controlled test.
- At phone width, inspect the single-column board, collection, forms, discussion and six-item bottom navigation.

## Automated coverage

`python manage.py test missions` covers 13 scenarios: creation/date validation; authenticated/idempotent joins; private discovery/detail/update/image access; invitation acceptance/decline and notifications; photo contribution keep/edit/delete ownership; reaction uniqueness; invalid/empty uploads; early finish; automatic deadline reveal; discussion escaping/ownership; CSRF and database guards; filtering/pagination/home entry; repeatable demo seeding.

The full application suite includes the existing account, post, social, recommendation, notification and WebSocket tests. PostgreSQL/Redis, public deployment, physical phone access and multi-worker load are not verified by local tests.
