#!/usr/bin/env bash
# One-time Google Cloud setup for running the pipeline on Cloud Run, deployed from GitHub.
# Safe to rerun: every step skips or updates what already exists.
#
#   docker compose -f docker-compose.yml -f docker-compose.bigquery.yml run --rm --entrypoint bash gcloud /setup/bootstrap.sh
#
# Creates:
#   - an Artifact Registry repository for the images (keeps the last 3 versions of each)
#   - service accounts, each with only what it needs:
#       pipeline-runner  runs the jobs: writes the warehouse, reads the API keys, writes memos
#       metrics-reader   runs the API and the dashboard: reads the metrics views only
#       github-deployer  used by GitHub Actions to push images, deploy and run jobs
#   - Workload Identity Federation so GitHub Actions in lqf2b8/llm-market-metrics (and no
#     other repository) can act as github-deployer without any stored key
#   - Secret Manager secrets for the OpenRouter and Anthropic keys, copied from your .env
#     (values are never printed)
#   - a Cloud Storage bucket for memo drafts
set -euo pipefail

: "${GCP_PROJECT:?Set GCP_PROJECT in .env}"
REGION="${GCP_REGION:-us-central1}"
REPO_SLUG="lqf2b8/llm-market-metrics"
AR_REPO="llm-market-metrics"
BUCKET="${GCP_PROJECT}-memos"
WRITE_DATASETS=(raw staging intermediate reference marts metrics analysis)
P="$GCP_PROJECT"
sa() { echo "$1@$P.iam.gserviceaccount.com"; }

step() { printf '\n== %s\n' "$*"; }

gcloud config set project "$P" --quiet >/dev/null
NUMBER="$(gcloud projects describe "$P" --format='value(projectNumber)')"

step "APIs"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  storage.googleapis.com bigquery.googleapis.com --quiet

step "Artifact Registry ($REGION)"
if ! gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPO" --repository-format=docker \
    --location="$REGION" --description="LLM market metrics images" --quiet
fi
cat > /tmp/cleanup.json <<'JSON'
[{"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}},
 {"name": "delete-old", "action": {"type": "Delete"}, "condition": {"olderThan": "604800s"}}]
JSON
gcloud artifacts repositories set-cleanup-policies "$AR_REPO" --location="$REGION" \
  --policy=/tmp/cleanup.json --no-dry-run --quiet >/dev/null
echo "images: $REGION-docker.pkg.dev/$P/$AR_REPO"

step "Service accounts"
for name in pipeline-runner metrics-reader github-deployer; do
  if ! gcloud iam service-accounts describe "$(sa $name)" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --quiet
  fi
  echo "ok: $(sa $name)"
done
sleep 10  # new accounts take a moment to appear in policies

bind_project() {  # bind_project <member> <role>
  gcloud projects add-iam-policy-binding "$P" --member="$1" --role="$2" \
    --condition=None --quiet >/dev/null
}
grant_dataset() {  # grant_dataset <dataset> <role WRITER|READER> <email>
  local tmp entry
  tmp="$(mktemp)"
  entry="{\"role\": \"$2\", \"userByEmail\": \"$3\"}"
  bq --project_id="$P" show --format=prettyjson "$P:$1" > "$tmp"
  if python3 /setup/add_access.py "$tmp" "$entry"; then
    bq --project_id="$P" update --source "$tmp" "$P:$1" >/dev/null
  fi
  rm -f "$tmp"
}

# bigquery.user: run queries and list datasets (dbt checks its schemas exist before building).
bind_project "serviceAccount:$(sa pipeline-runner)" roles/bigquery.user
for ds in "${WRITE_DATASETS[@]}"; do grant_dataset "$ds" WRITER "$(sa pipeline-runner)"; done
echo "pipeline-runner: runs queries, writes the ${#WRITE_DATASETS[@]} warehouse datasets"

bind_project "serviceAccount:$(sa metrics-reader)" roles/bigquery.jobUser
grant_dataset metrics READER "$(sa metrics-reader)"
echo "metrics-reader: runs queries, reads the metrics dataset only"

for role in roles/run.admin roles/artifactregistry.writer; do
  bind_project "serviceAccount:$(sa github-deployer)" "$role"
done
for name in pipeline-runner metrics-reader; do
  gcloud iam service-accounts add-iam-policy-binding "$(sa $name)" \
    --member="serviceAccount:$(sa github-deployer)" --role=roles/iam.serviceAccountUser \
    --quiet >/dev/null
done
echo "github-deployer: pushes images, deploys services and jobs, runs jobs"

step "Workload Identity Federation for $REPO_SLUG"
if ! gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create github --location=global \
    --display-name="GitHub Actions" --quiet
fi
if ! gcloud iam workload-identity-pools providers describe github-oidc --location=global \
    --workload-identity-pool=github >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc github-oidc --location=global \
    --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '$REPO_SLUG'" --quiet
fi
gcloud iam service-accounts add-iam-policy-binding "$(sa github-deployer)" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$REPO_SLUG" \
  --quiet >/dev/null
echo "only $REPO_SLUG can act as github-deployer"

step "Secrets"
put_secret() {  # put_secret <name> <value>
  if ! gcloud secrets describe "$1" >/dev/null 2>&1; then
    gcloud secrets create "$1" --replication-policy=automatic --quiet >/dev/null
  fi
  if [ -n "$2" ]; then
    printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=- --quiet >/dev/null
    echo "stored a new version of $1 (value not shown)"
  else
    echo "WARNING: $1 is empty in .env; add it there and rerun"
  fi
  gcloud secrets add-iam-policy-binding "$1" --member="serviceAccount:$(sa pipeline-runner)" \
    --role=roles/secretmanager.secretAccessor --quiet >/dev/null
}
put_secret openrouter-api-key "${OPENROUTER_API_KEY:-}"
put_secret anthropic-api-key "${ANTHROPIC_API_KEY:-}"

step "Memo bucket"
if ! gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" --location="$REGION" \
    --uniform-bucket-level-access --quiet
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$(sa pipeline-runner)" --role=roles/storage.objectAdmin \
  --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$(sa github-deployer)" --role=roles/storage.objectViewer \
  --quiet >/dev/null
echo "memo drafts: gs://$BUCKET (GitHub Actions reads them to open a review PR)"

step "Done. Add these as GitHub repository variables (Settings > Secrets and variables >"
echo "Actions > Variables). None of them is a secret."
echo "  GCP_PROJECT   $P"
echo "  GCP_REGION    $REGION"
echo "  WIF_PROVIDER  projects/$NUMBER/locations/global/workloadIdentityPools/github/providers/github-oidc"
