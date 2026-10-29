#!/usr/bin/env bash
# One-time BigQuery setup for GCP_PROJECT. Safe to rerun: every step skips what exists.
#
#   docker compose -f docker-compose.yml -f docker-compose.bigquery.yml run --rm gcloud
#
# 1. Signs you in (twice: once for gcloud, once for the credentials the services use).
#    Credentials live in the gcloud-config Docker volume, never in the repo.
# 2. Enables BigQuery and creates the datasets dbt and the services write to.
# 3. Authorizes the `metrics` dataset to read `marts` and `analysis`, so a reader of the
#    metrics views needs no access to anything else.
# 4. Creates the hex-reader service account: it can run queries and read `metrics`, nothing
#    more. Its key is written to ./secrets/hex-reader.json for you to upload to Hex.
set -euo pipefail

: "${GCP_PROJECT:?Set GCP_PROJECT in .env}"
LOCATION="${BQ_LOCATION:-US}"
DATASETS=(raw staging intermediate reference marts metrics analysis)
READER="hex-reader"
READER_EMAIL="${READER}@${GCP_PROJECT}.iam.gserviceaccount.com"
KEY_FILE="/secrets/hex-reader.json"
ADC="${CLOUDSDK_CONFIG}/application_default_credentials.json"

step() { printf '\n== %s\n' "$*"; }

step "Sign in to gcloud"
if [ -z "$(gcloud auth list --filter=status:ACTIVE --format='value(account)')" ]; then
  gcloud auth login --no-launch-browser
fi
gcloud config set project "$GCP_PROJECT" --quiet

step "Credentials for the pipeline services (application default credentials)"
if [ ! -f "$ADC" ]; then
  gcloud auth application-default login --no-launch-browser
fi
gcloud auth application-default set-quota-project "$GCP_PROJECT" --quiet
# The services run as a non-root user and only need to read this file.
chmod 644 "$ADC"

step "Enable APIs"
gcloud services enable bigquery.googleapis.com iam.googleapis.com \
  cloudresourcemanager.googleapis.com --quiet

step "Datasets in $LOCATION"
for ds in "${DATASETS[@]}"; do
  if bq --project_id="$GCP_PROJECT" show --dataset "$GCP_PROJECT:$ds" >/dev/null 2>&1; then
    echo "exists: $ds"
  else
    bq --project_id="$GCP_PROJECT" --location="$LOCATION" mk --dataset "$GCP_PROJECT:$ds"
  fi
done

step "Reader service account"
if ! gcloud iam service-accounts describe "$READER_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$READER" \
    --display-name="Hex: read-only on the metrics dataset" --quiet
  sleep 10  # new service accounts take a moment to be usable in policies
fi
gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member="serviceAccount:$READER_EMAIL" --role=roles/bigquery.jobUser \
  --condition=None --quiet >/dev/null
echo "can run queries: $READER_EMAIL"

step "Dataset access: metrics views may read marts and analysis; hex-reader may read metrics"
grant() {  # grant <dataset> <json access entry>
  local ds="$1" entry="$2" tmp
  tmp="$(mktemp)"
  bq --project_id="$GCP_PROJECT" show --format=prettyjson "$GCP_PROJECT:$ds" > "$tmp"
  if python3 /setup/add_access.py "$tmp" "$entry"; then
    bq --project_id="$GCP_PROJECT" update --source "$tmp" "$GCP_PROJECT:$ds" >/dev/null
    echo "granted on $ds: $entry"
  else
    echo "already granted on $ds"
  fi
  rm -f "$tmp"
}
METRICS_VIEWS="{\"dataset\": {\"dataset\": {\"projectId\": \"$GCP_PROJECT\", \"datasetId\": \"metrics\"}, \"targetTypes\": [\"VIEWS\"]}}"
grant marts "$METRICS_VIEWS"
grant analysis "$METRICS_VIEWS"
grant metrics "{\"role\": \"READER\", \"userByEmail\": \"$READER_EMAIL\"}"

step "Key for Hex"
if [ -f "$KEY_FILE" ]; then
  echo "exists: secrets/hex-reader.json"
else
  gcloud iam service-accounts keys create "$KEY_FILE" --iam-account="$READER_EMAIL" --quiet
  chmod 644 "$KEY_FILE"
  echo "wrote secrets/hex-reader.json: upload it to Hex, then delete it"
fi

step "Done"
echo "Next: docker compose -f docker-compose.yml -f docker-compose.bigquery.yml run --build --rm ingest copy-local"
