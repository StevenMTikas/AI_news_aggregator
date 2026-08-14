# ☁️ Deployment Guide for Google Cloud Run

This guide deploys the AI News Aggregator to Google Cloud Run as a **private**, free
(at this app's usage level), Docker-based deployment using the same `Dockerfile` built for
this project — no code changes needed.

## Why Cloud Run (and how "free" works here)

Cloud Run's Always Free tier includes 2 million requests, 180,000 vCPU-seconds, and 1 GiB of
egress per month — far more than a personal blog-generator tool will use. Unlike Vercel or
plain serverless platforms, Cloud Run supports request timeouts up to 60 minutes and (with one
flag) lets background work keep running after the HTTP response is sent, which this app relies
on for its 1–5 minute blog generation.

⚠️ **Free tier requires a billing account on file.** Google won't charge you as long as you
stay under the free quota, but you do need a credit card attached to your GCP account to enable
billing at all — this is a Google account-level requirement, not something specific to this app.

⚠️ **Free tier only applies in specific regions**: `us-central1`, `us-east1`, or `us-west1`.
Deploying elsewhere will incur charges from the first request.

## Prerequisites

1. ✅ A [Google Cloud account](https://console.cloud.google.com/) with billing enabled (free — see above)
2. ✅ The [`gcloud` CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud init`)
3. ✅ An [OpenAI API key](https://platform.openai.com/api-keys) and a [Serper API key](https://serper.dev/api-key)

## 🌐 Deployment Steps

### Step 1: Create/select a project and enable required APIs

```bash
gcloud projects create ai-news-aggregator-<your-suffix>   # or: gcloud config set project <existing-project-id>
gcloud config set project ai-news-aggregator-<your-suffix>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
```

### Step 2: Store your API keys in Secret Manager

Keeps the keys out of shell history, logs, and the deploy command itself:

```bash
printf "%s" "sk-your-openai-key" | gcloud secrets create OPENAI_API_KEY --data-file=-
printf "%s" "your-serper-key" | gcloud secrets create SERPER_API_KEY --data-file=-
```

(Secret names in this project are `OPENAI_API_KEY`/`SERPER_API_KEY` — matching the env var
names directly rather than the lowercase-hyphenated convention, which is equally valid in
Secret Manager. The `--set-secrets` flag below matches these names.)

### Step 3: Deploy

From the project root (where the `Dockerfile` lives):

```bash
gcloud run deploy ai-news-aggregator \
  --source . \
  --region us-central1 \
  --port 7860 \
  --no-cpu-throttling \
  --max-instances 1 \
  --no-allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest,SERPER_API_KEY=SERPER_API_KEY:latest
```

What each non-obvious flag does:
- `--source .` — builds directly from the existing `Dockerfile` via Cloud Build; no manual image push needed.
- `--no-cpu-throttling` — keeps CPU allocated after the response is sent, so the background blog-generation task actually finishes instead of stalling. By default Cloud Run only allocates CPU while actively handling a request.
- `--max-instances 1` — pins the service to a single instance, so the app's in-memory task-status dict (used for progress polling) stays consistent. Without this, Cloud Run could route your status-check requests to a different instance than the one running your generation job.
- `--no-allow-unauthenticated` — **this is what makes it private.** Only Google identities you explicitly grant access to can call the service; anonymous requests are rejected. This is the direct equivalent of Hugging Face's "Private" visibility.

This will take a few minutes on first deploy (building the image, installing crewai's dependencies).

### Step 4: Grant yourself access

```bash
gcloud run services add-iam-policy-binding ai-news-aggregator \
  --region us-central1 \
  --member "user:you@example.com" \
  --role "roles/run.invoker"
```

Replace `you@example.com` with the Google account you'll use to access the app.

## 🔍 Accessing Your Private App

Because the service requires authentication, you can't just open the Cloud Run URL in a plain
browser tab — it'll return a 403. Two ways to actually use it:

**Option A — local authenticated proxy (recommended for personal use):**

The first time you run this, it needs the `cloud-run-proxy` gcloud component, which isn't
installed by default. If gcloud is installed under `Program Files`, installing components
requires an elevated terminal — right-click Command Prompt or PowerShell and choose **Run as
Administrator**, then run:

```bash
gcloud components install cloud-run-proxy
```

After that (one-time setup), run this from a normal terminal whenever you want to use the app:

```bash
gcloud run services proxy ai-news-aggregator --region us-central1 --port 8080
```

This opens `http://localhost:8080` on your machine, transparently forwarding requests with your
Google credentials attached. Use the app exactly like you did locally with `start_web.py` — open
it in any browser, no tokens to manage.

**Option B — call it directly with a bearer token** (useful for scripts, not casual browser use):

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" https://<your-service-url>/health
```

## 🔍 Verify Deployment

With the proxy running (Option A above), visit `http://localhost:8080/health` — you should see
the same JSON response as running it locally.

## 🐛 Troubleshooting

**Build fails with a compiler error**
The `Dockerfile` already installs `build-essential` for crewai's native dependencies. Check
Cloud Build logs (`gcloud builds log <BUILD_ID>` or the Cloud Console) for the specific package.

**Blog generation seems to stop partway through / task status never reaches "completed"**
Confirm the deploy included `--no-cpu-throttling` and `--max-instances 1` — without them,
background work can be starved of CPU or answered by a different instance than the one running it.

**403 Forbidden when visiting the service URL directly**
Expected — the service is private. Use the `gcloud run services proxy` command above, or grant
your account `roles/run.invoker` (Step 4) if you haven't.

**"OPENAI_API_KEY is not set" at runtime**
Confirm the secrets exist (`gcloud secrets list`) and that `--set-secrets` was included in the
deploy command with the exact names `OPENAI_API_KEY` and `SERPER_API_KEY`.

## 💰 Cost

- **Hosting**: $0 at this app's usage level, as long as the service stays in a free-tier region
  and under the monthly request/vCPU-second quota.
- **API costs**: unchanged — OpenAI (~$0.01–$0.05/post on gpt-4o-mini) and Serper (2,500
  free searches/month). Since the service is IAM-authenticated, only accounts you've explicitly
  granted `roles/run.invoker` can trigger generation, so your budget is protected the same way
  a private HF Space would have protected it.

## 🔄 Updating Your Deployment

Re-run the same deploy command from Step 3 — Cloud Run builds a new revision and shifts traffic
to it automatically:

```bash
gcloud run deploy ai-news-aggregator --source . --region us-central1
```

(Flags like `--no-cpu-throttling` and `--max-instances` are sticky per-revision settings you set
once; Cloud Run docs recommend repeating them on redeploys if you want to be explicit, but
existing revision settings otherwise carry forward.)
