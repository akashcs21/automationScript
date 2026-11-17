# JIGYASA LAB — Daily AI Reel Automation

A complete, free-first, cloud-based system that automatically creates and
publishes one vertical Facebook Reel per day to your Facebook Page using the
Meta Graph API. Runs in **GitHub Actions** — your PC never needs to stay on.

Brand: **JIGYASA LAB** — *Explore Everything. Question Everything.*

## Project structure

```
jigyasa-lab-automation/
├── app/
│   ├── main.py              # Orchestrator — runs all stages
│   ├── config.py            # Configuration from env vars
│   ├── logger.py            # Structured logging (secrets redacted)
│   ├── ai_writer.py         # Gemini script generation + validation
│   ├── fact_checker.py      # Fact-checking quality gate
│   ├── topic_manager.py     # Topic history + dedupe
│   ├── voice_generator.py   # Offline narration (eSpeak NG / Piper)
│   ├── visual_generator.py  # Original animated visuals (Pillow)
│   ├── subtitle_generator.py# SRT subtitles + highlight track
│   ├── video_editor.py      # FFmpeg render + quality validation
│   └── facebook_publisher.py# Meta Graph API two-stage Reels publishing
├── assets/
│   └── logo.png             # Brand logo
├── music/                   # Optional custom music (procedural audio used by default)
├── sounds/                  # Optional custom SFX (procedural SFX used by default)
├── data/
│   ├── topics.json          # Topic history (created on first run)
│   └── published.json       # Publishing log
├── output/                  # Rendered MP4, narration, SRT, logs (gitignored)
├── .github/workflows/daily-reel.yml
├── requirements.txt
├── .env.example             # Copy to .env locally; never commit real values
├── .gitignore
└── README.md
```

## Free-first technology stack

| Layer | Tool | Cost |
|---|---|---|
| Language | Python 3.11+ | Free |
| AI script | Gemini API (free-tier model) | Free tier |
| HTTP client | Python `requests` | Free |
| Rendering | FFmpeg | Free |
| Graphics | Pillow | Free |
| Narration | eSpeak NG / Piper (offline) | Free |
| Scheduling | GitHub Actions | Free |
| Publishing | Meta Graph API | Free |
| Storage | JSON files | Free |

No paid APIs, paid stock footage, paid hosting, or permanent server. No
copyrighted music or downloaded video — all visuals are drawn with Pillow and
all audio is synthesized procedurally.

## Prerequisites

- Python 3.11+
- FFmpeg (for rendering/encoding)
- eSpeak NG (offline narration) — `sudo apt-get install espeak-ng` on Ubuntu
- A Gemini API key (Google AI Studio)
- A Meta Developer app + Facebook Page access token

## Credentials you must configure

| Secret / Env var | Where to get it | Required for |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio (https://aistudio.google.com) — get an API key | Script generation |
| `GEMINI_MODEL` | e.g. `gemini-1.5-flash` (free tier) | Script generation |
| `FB_PAGE_ID` | Your Facebook Page ID (Meta Business Suite / Graph API Explorer) | Publishing |
| `FB_PAGE_ACCESS_TOKEN` | Page access token (see below) | Publishing |
| `GRAPH_API_VERSION` | e.g. `v27.0` | Publishing |
| `PUBLISH_ENABLED` | `true` or `false` | Publishing safety switch |
| `BRAND_NAME` | `JIGYASA LAB` | Branding |

**Never commit real values.** Locally, copy `.env.example` to `.env` and fill
it in. On GitHub, add the values to **Repository → Settings → Secrets and
variables → Actions**. Secret values are never printed in logs.

## 1. Install dependencies locally

```bash
git clone <your-repo>
cd jigyasa-lab-automation

# System tools (Ubuntu/Debian)
sudo apt-get update -y
sudo apt-get install -y ffmpeg espeak-ng

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Local env (fill in your own values)
cp .env.example .env
# edit .env with your GEMINI_API_KEY, etc. (PUBLISH_ENABLED=false to start)
```

## 2. Obtain a Gemini API key

1. Go to https://aistudio.google.com (Google AI Studio).
2. Sign in with your Google account.
3. Click **Get API key** → **Create API key**.
4. Copy the key and set it as `GEMINI_API_KEY` (`.env` locally / GitHub secret in CI).
5. Choose a free-tier model, e.g. `gemini-1.5-flash`, and set `GEMINI_MODEL`.

The script asks Gemini for structured JSON and retries safely if the response is
invalid. No script is published unless it validates completely.

## 3. Create a Meta Developer app

1. Go to https://developers.facebook.com/ and log in.
2. **My Apps → Create App** → choose **Business** (or similar) and complete
   verification steps as prompted.
3. In your app dashboard, add products if needed and note your **App ID**.
4. You will need a **Page access token** for the page you want to publish to.

## 4. Obtain a Page access token

The simplest path is the Graph API Explorer:

1. Go to https://developers.facebook.com/tools/explorer/
2. Select your Meta app from the **Application** dropdown.
3. Click **Get Token → Get User Access Token**, and grant these permissions:
   - `pages_manage_posts`
   - `pages_show_list`
   - `pages_read_engagement` (helpful for diagnostics)
   - `instagram_basic` (only if you also cross-post)
4. In **User or Page → Page**, select your Facebook Page, then click
   **Get Page Access Token**.
5. Copy the token → `FB_PAGE_ACCESS_TOKEN`.
6. Get your Page ID from your Page settings or from the `/me/accounts` endpoint
   → `FB_PAGE_ID`.

Tokens expire. See **Troubleshooting** below for refreshing them.

> Page access tokens are short-lived unless your app has gone through Business
> Verification and you exchange for a long-lived token. For daily automation,
> set up long-lived tokens or re-rotate the token before expiry.

## 5. Configure GitHub repository secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New
repository secret**. Add:

| Secret name | Value |
|---|---|
| GEMINI_API_KEY | your Gemini key |
| GEMINI_MODEL | `gemini-1.5-flash` |
| FB_PAGE_ID | your Page ID |
| FB_PAGE_ACCESS_TOKEN | your Page access token |
| GRAPH_API_VERSION | `v27.0` |
| PUBLISH_ENABLED | `false` (start here) |
| DRY_RUN | `true` (start here) |
| BRAND_NAME | `JIGYASA LAB` |

The workflow `.github/workflows/daily-reel.yml` reads these as `secrets.*` and
never prints them. The schedule is `30 12 * * *` UTC = **18:00 IST daily**,
plus `workflow_dispatch` for manual runs.

## 6. Run the first Reel in DRY_RUN mode

```bash
source venv/bin/activate
# .env must have PUBLISH_ENABLED=false (and DRY_RUN=true)
python app/main.py
```

What happens:
1. Gemini picks a fresh topic (not in `data/topics.json`).
2. Writes a 75–100 word script with scenes, subtitles, caption, hashtags,
   claims + sources.
3. Fact-checks claims (source URLs must be reachable).
4. Synthesizes narration with eSpeak NG.
5. Draws original animated frames with Pillow.
6. Renders a 1080×1920 MP4 (H.264/AAC, 30 FPS, 35–45 s) with crossfades,
   burned subtitles, procedural music + SFX.
7. Runs quality checks: container, resolution, duration, audio, decodability,
   no placeholder text, file size.
8. Saves `output/jigyasa_lab_reel_*.mp4` and logs. **Does not publish.**

Inspect `output/run.log` and play the MP4. Once you are happy with the result,
flip `PUBLISH_ENABLED=true` (and `DRY_RUN=false`) to publish for real.

## 7. Test Facebook publishing manually

```bash
source venv/bin/activate
# In .env: PUBLISH_ENABLED=true, DRY_RUN=false
python app/main.py
```

Or trigger from GitHub: **Actions → JIGYASA LAB — Daily Reel Automation → Run
workflow**.

The publisher uses Meta's official two-stage flow:
1. `POST /{PAGE_ID}/video_reels?upload_phase=START` → video_id + upload_url
2. `POST {upload_url}` with the MP4 binary (OAuth header)
3. `POST /{PAGE_ID}/video_reels?upload_phase=FINISH` with `video_id`,
   `description`, `is_ai_generated=true`

The result (`video_id`, `post_id`) is recorded in `data/published.json`.
No browser automation, no passwords ever stored.

## 8. Enable automatic daily publishing

1. Set `PUBLISH_ENABLED=true` and `DRY_RUN=false` in GitHub secrets.
2. Verify at least one DRY_RUN output looks good first.
3. The workflow runs daily at 18:00 IST (12:30 UTC cron).
4. Manually trigger anytime via the **Run workflow** button.

One Reel per daily run is enforced. Topic history prevents repetition.

## 9. Troubleshooting API errors and expired tokens

| Symptom | Likely cause | Fix |
|---|---|---|
| `GEMINI_API_KEY is not set` | Missing secret | Add to GitHub secrets / `.env` |
| Gemini invalid JSON after retries | Model output glitch | Re-run; prompt is retried up to 3× |
| Fact-check failed: source unreachable | Bad/inaccessible URL | Re-run picks a new topic |
| Error code 190 / 102 | Expired or invalid token | Get a fresh Page access token |
| Error code 200 | Missing permissions | Re-grant `pages_manage_posts` |
| Rate limit (code 4, 613, 803) | Meta throttling | Wait, then re-run; no blind retry |
| Publish "uncertain state" | Network/timeout mid-upload | Check `data/published.json` before re-running |

Expired token — quick refresh:
1. Graph API Explorer → get a new short-lived user token.
2. Exchange for long-lived: `GET /oauth/access_token?grant_type=fb_exchange_token&fb_exchange_token={SHORT}&client_id={APP_ID}&client_secret={APP_SECRET}`
3. Use it to get a new Page token → update `FB_PAGE_ACCESS_TOKEN` secret.

Logs live in `output/run.log`; failures write `output/error_report.json`.
Secrets are redacted (`****`) in all logs.

## Safety & publishing controls

- **DRY_RUN mode**: generate + validate, never publish (default).
- `PUBLISH_ENABLED=true` is required for real publishing.
- Quality gates block publishing on any failure.
- Fact-checking blocks publishing on unverifiable claims.
- Topic history + content hash prevent duplicate or near-identical Reels.
- Maximum one Reel per daily run; no blind retries of uncertain publishes.
- Logs are kept; MP4s and API keys are never committed (`.gitignore`).

## Development stages (as built)

1. AI script generation (`app/ai_writer.py`)
2. Narration + visual generation (`voice_generator.py`, `visual_generator.py`)
3. Video rendering (`video_editor.py`)
4. Quality validation (`video_editor.validate_reel`)
5. Facebook publishing (`facebook_publisher.py`)
6. GitHub Actions scheduling (`.github/workflows/daily-reel.yml`)

Each stage was implemented and wired into `app/main.py` with explicit stop-on-
failure behaviour between stages.