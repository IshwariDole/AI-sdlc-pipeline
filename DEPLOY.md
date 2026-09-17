# Deploying brs2sprint publicly

The dashboard (`dashboard/app.py`) is the right entry point for a public
deployment — the CLI is for you, the dashboard is for anyone. This guide
covers the free path (Streamlit Community Cloud) and the tradeoffs that
matter once other people can actually reach it.

## The one decision that matters: whose API key?

**Don't put your own API key in the server config for a public app.**
Every visitor would draw from the same free-tier quota, and Groq's free tier
caps at 8,000 tokens/minute — two people using the app at the same moment
will rate-limit each other on *your* key.

Instead, the dashboard now asks each visitor for their own key in the
sidebar (a password-masked input). It is:
- used only in-memory for that visitor's run
- passed directly to the provider's SDK
- **never written to disk, logged, or stored anywhere** — not in `.env`,
  not in the SQLite run history, not in Streamlit's own state beyond the
  current session

This means zero cost and zero shared rate-limit risk to you as the host.
The tradeoff is visitors need their own free key (30 seconds at
console.groq.com/keys or aistudio.google.com/apikey) — a fair ask for a
free demo tool, and worth saying so in the page copy if you want to soften
it further.

If you specifically want a low-traffic *private* demo — a handful of known
users, not the open internet — you can set a single shared key via
Streamlit secrets instead (see `.streamlit/secrets.toml.example`). Combine
that with Streamlit Cloud's built-in viewer-restriction (Settings → Sharing
→ restrict to specific emails) so "shared key" doesn't mean "public key".

## Step by step: Streamlit Community Cloud (free)

1. **Push this project to a GitHub repo** (public or private — Streamlit
   Cloud can access either once you connect your GitHub account).

   ```bash
   cd brs2sprint
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<you>/brs2sprint.git
   git push -u origin main
   ```

   `.gitignore` already excludes `.env` and `.streamlit/secrets.toml` — your
   local keys will not be pushed. Double-check with `git status` before your
   first commit if you've already been testing locally.

2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in
   with GitHub.

3. **New app** → select your repo, branch `main`, main file path
   `dashboard/app.py`.

4. **(Optional) Set secrets** — App settings → Secrets — paste the contents
   of `.streamlit/secrets.toml.example` with values filled in (skip the
   provider key unless you're doing the private-demo variant above). At
   minimum, setting `BRS2SPRINT_HOSTED = "true"` turns on the public-facing
   messaging (the "use your own key" banner, the ephemeral-storage notice).

5. **Deploy.** First build takes a few minutes (installing `requirements.txt`).
   You get a URL like `https://<something>.streamlit.app`.

That's the whole deployment. No Dockerfile, no server to manage.

## What changes once it's public

- **Run history is ephemeral.** Streamlit Cloud apps sleep after a period of
  inactivity and their filesystem resets on redeploy. The SQLite-backed
  "load a previous run" feature still works *within* a session/uptime
  window, but don't rely on it as permanent storage. If you need permanent
  history, point `DB_PATH` (in secrets) at a hosted Postgres instance instead
  and adapt `store.py`'s `connect()` — a small change, not done here since it
  adds a paid dependency most demos don't need.
- **File size limits.** Streamlit Cloud caps uploads around 200MB by default
  (configurable via `.streamlit/config.toml`); BRS documents are nowhere
  near that, so no action needed.
- **Concurrent users share the app's compute**, not just API quota — the
  pipeline runs synchronously in-process per Streamlit session, so a very
  large document from one visitor will feel slow for others mid-run on a
  free-tier Streamlit instance. Fine for a portfolio/demo audience; would
  need the FastAPI + background-job path (`api/main.py`, already built) in
  front of a real job queue for genuine multi-tenant production use.
- **Rate limits still apply per visitor's own key.** A visitor hitting
  Groq's per-minute ceiling gets the same clean error message you saw
  locally (`LLM_MAX_TOKENS` guidance, model-not-found guidance, etc.) rather
  than a stack trace — that error handling was written to be shown to a
  non-technical end user directly, and the dashboard now does exactly that.

## Alternatives to Streamlit Cloud

- **Render / Railway** — if you outgrow Streamlit Cloud's limits or want the
  FastAPI backend (`api/main.py`) fronting a separate frontend instead of
  the all-in-one dashboard. Both offer free tiers with a Dockerfile or
  native Python buildpack; point the start command at
  `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.
- **Your own VM / Docker** — full control, no sleep/reset behavior, but now
  you own patching, TLS, and uptime. Not necessary for a demo.

Streamlit Cloud is the right first stop: free, zero ops, and matches this
project's already-free-tier philosophy end to end.
