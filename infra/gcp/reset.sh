#!/usr/bin/env bash
# Delete every dataset this project created, so setup.sh can recreate them cleanly.
# Everything in BigQuery is rebuilt from your local raw files, so nothing is lost.
#
#   docker compose -f docker-compose.yml -f docker-compose.bigquery.yml run --rm --entrypoint bash gcloud /setup/reset.sh
set -euo pipefail
: "${GCP_PROJECT:?Set GCP_PROJECT in .env}"
DATASETS=(raw staging intermediate reference marts metrics analysis)

echo "This deletes these datasets and all their tables in $GCP_PROJECT:"
printf '  %s\n' "${DATASETS[@]}"
read -r -p "Type the project id to confirm: " answer
[ "$answer" = "$GCP_PROJECT" ] || { echo "Not confirmed; nothing deleted."; exit 1; }

for ds in "${DATASETS[@]}"; do
  bq --project_id="$GCP_PROJECT" rm -r -f -d "$GCP_PROJECT:$ds" && echo "deleted $ds"
done
echo "Next: rerun setup (docker compose ... run --rm gcloud), then copy-local."
