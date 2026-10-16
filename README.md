# Facebook Posting Prototype (Python 3.11)

A local-first prototype for managing one post across multiple destinations.

## What it does

- Stores Facebook Page and Group destinations in SQLite.
- Lets you compose one post and select multiple destinations.
- Publishes due text posts to Facebook Pages using Meta Graph API, provided you have valid Page access tokens and the required permissions.
- Places Group destinations into a manual publishing queue.
- Tracks pending, published, failed, and manually marked-done statuses.
- Can be run manually or by Windows Task Scheduler / cron.

## Important platform limitation

Meta removed the Facebook Groups API, `publish_to_groups`, and `groups_access_member_info` on April 22, 2024. This app therefore does **not** attempt to publish to Groups through a nonexistent official endpoint, and does not use browser automation to bypass that restriction. Group items require manual publication. Page publishing is only for Pages you are authorized to manage.

Reference: Meta Graph API v19.0 changelog, Groups API section:
https://developers.facebook.com/docs/graph-api/changelog/version19.0/

## Run on Windows

1. Install Python 3.11.
2. Extract this folder and open PowerShell inside it.
3. Create a virtual environment:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and set a long random `FLASK_SECRET_KEY`.
5. Configure `FB_PAGE_TOKENS_JSON` in `.env` as a JSON object mapping Page IDs to Page access tokens. Example:
   ```dotenv
   FB_PAGE_TOKENS_JSON={"123456789012345":"YOUR_PAGE_ACCESS_TOKEN"}
   ```
   Do not share or commit your token. Use only tokens obtained through Meta's official authorization flow.
6. Start the local dashboard:
   ```powershell
   python app.py
   ```
7. Open `http://127.0.0.1:5000`.

## First test

- Add one Facebook Page destination using its Page ID.
- Add one Group destination (Group ID is optional because publishing is manual).
- Compose a harmless test post and select only the Page you control.
- Click **Process queue now**. If permissions/token are wrong, the error is recorded instead of silently claiming success.
- Open **Group Manual Queue** to copy the post text for manual publishing.

## Worker scheduling

The dashboard's **Process queue now** button runs the worker once. For recurring processing, configure Windows Task Scheduler to run:

Program/script:
`<project-folder>\.venv\Scripts\python.exe`

Arguments:
`<project-folder>\worker.py`

Start in:
`<project-folder>`

Use a sensible interval such as every 5–15 minutes. The worker will process due items. Do not expose the local dashboard to the public internet.

On Linux, cron can run the same worker:
```cron
*/10 * * * * cd /path/to/facebook_posting_prototype && .venv/bin/python worker.py >> worker.log 2>&1
```

## Scheduling format

Enter a timestamp with a timezone offset, for example:
`2026-10-17T15:30:00+05:30`

If no schedule is entered, the worker treats the post as due immediately.

## Security and scope notes

- The `.env` file contains secrets and must not be committed.
- This prototype currently supports text posts only. Image/video uploads, Stories, personal-profile publishing, and automated Group publishing are not implemented.
- Do not use a personal-account password or session-cookie scraping.
- A manually marked Group post is not verified by Facebook; it is only a note in this local database.
- Before production use, add CSRF protection, authentication, stronger input validation, retries/backoff, and audit logging.
