#!/usr/bin/env bash

# Get the presigned url
set -euo pipefail

# Check the following env vars are set
if [[ ! -v HOSTNAME_SSM_PARAMETER_NAME ]]; then
  echo "Error: HOSTNAME_SSM_PARAMETER_NAME is not set" 1>&2
  exit 1
fi
if [[ ! -v ORCABUS_TOKEN_SECRET_ID ]]; then
  echo "Error: ORCABUS_TOKEN_SECRET_ID is not set" 1>&2
  exit 1
fi
if [[ ! -v INPUT_BAM_URI ]]; then
  echo "Error: INPUT_BAM_URI is not set" 1>&2
  exit 1
fi

# Set the HOSTNAME environment variable
HOSTNAME="$( \
  aws ssm get-parameter \
	--name "${HOSTNAME_SSM_PARAMETER_NAME}" \
	--output json | \
  jq --raw-output '.Parameter.Value' \
)"
export HOSTNAME

# Set ORCABUS_TOKEN environment variable
ORCABUS_TOKEN="$( \
  aws secretsmanager get-secret-value \
	--secret-id "${ORCABUS_TOKEN_SECRET_ID}" \
	--output json \
	--query SecretString | \
  jq --raw-output 'fromjson | .id_token' \
)"
export ORCABUS_TOKEN

# Get filemanager parameter inputs
bucket="$(
	python3 -c "from urllib.parse import urlparse; print(urlparse('${INPUT_BAM_URI}').netloc)"
)"
key="$(
	python3 -c "from urllib.parse import urlparse; print(urlparse('${INPUT_BAM_URI}').path.lstrip('/'))"
)"

# Download the index
CURL_GET_S3_PRESIGNED_URL_BAM_INDEX_ARGS_ARRAY=(
  "--fail" "--silent" "--location" "--show-error" \
  "--header" "Accept: application/json" \
  "--header" "Authorization: Bearer ${ORCABUS_TOKEN}" \
  "https://file.${HOSTNAME}/api/v1/s3/presign?&responseContentDisposition=inline&bucket=${bucket}&key=${key}.bai" \
)
bam_index_presigned_url="$( \
  curl "${CURL_GET_S3_PRESIGNED_URL_BAM_INDEX_ARGS_ARRAY[@]}" | \
  jq --raw-output '.results[0]' \
)"

# Download bam index
WGET_DOWNLOAD_INDEX_ARGS=( \
  "--quiet" \
  "--output-document" "$(basename "${key}").bai" \
  "${bam_index_presigned_url}" \
)
wget "${WGET_DOWNLOAD_INDEX_ARGS[@]}"

# Get bam presigned url
CURL_GET_S3_PRESIGNED_URL_BAM_ARGS_ARRAY=( \
  "--fail" "--silent" "--location" "--show-error" \
  "--header" "Accept: application/json" \
  "--header" "Authorization: Bearer ${ORCABUS_TOKEN}" \
  "https://file.${HOSTNAME}/api/v1/s3/presign?&responseContentDisposition=inline&bucket=${bucket}&key=${key}" \
)
bam_presigned_url="$( \
  curl "${CURL_GET_S3_PRESIGNED_URL_BAM_ARGS_ARRAY[@]}" | \
  jq --raw-output '.results[0]' \
)"

# Samtools stats args
SAMTOOLS_STATS_ARGS_ARRAY=( \
  # Set the customized index file parameter
  "-X" \
  "${bam_presigned_url}" \
  # But the index parameter must go after the bam file in arg positions
  "$(basename "${key}").bai" \
)
samtools stats "${SAMTOOLS_STATS_ARGS_ARRAY[@]}"
