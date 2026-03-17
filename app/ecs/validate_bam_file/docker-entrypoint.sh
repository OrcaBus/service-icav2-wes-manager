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

# Run samtools quickcheck
samtools quickcheck "${bam_presigned_url}"
