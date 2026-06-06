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
if [[ ! -v INPUT_VCF_URI ]]; then
  echo "Error: INPUT_VCF_URI is not set" 1>&2
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

# Set error logs file
ERROR_LOGS_FILE="error_logs.txt"

# Get filemanager parameter inputs
bucket="$(
	python3 -c "from urllib.parse import urlparse; print(urlparse('${INPUT_VCF_URI}').netloc)"
)"
key="$(
	python3 -c "from urllib.parse import urlparse; print(urlparse('${INPUT_VCF_URI}').path.lstrip('/'))"
)"

download_file_from_filemanager(){
  : '
  Download a file from the filemanager
  '
  # Inputs
  local bucket="${1}"
  local key="${2}"

  # Input vars
  local CURL_GET_S3_QUERY_ARGS_ARRAY
  local CURL_GET_S3_PRESIGNED_URL_ARGS_ARRAY

  # Get query args array
  CURL_GET_S3_QUERY_ARGS_ARRAY=( \
    "--fail" "--silent" "--location" "--show-error" \
    "--header" "Accept: application/json" \
    "--header" "Authorization: Bearer ${ORCABUS_TOKEN}" \
    "https://file.${HOSTNAME}/api/v1/s3?bucket=${bucket}&key=${key}" \
  )

  # Get presigned url
  CURL_GET_S3_PRESIGNED_URL_ARGS_ARRAY=( \
    "--fail" "--silent" "--location" "--show-error" \
    "--header" "Accept: application/json" \
    "--header" "Authorization: Bearer ${ORCABUS_TOKEN}" \
    "https://file.${HOSTNAME}/api/v1/s3/presign?responseContentDisposition=inline&bucket=${bucket}&key=${key}" \
  )

  # Check the file is available
  if ! ( \
    curl "${CURL_GET_S3_QUERY_ARGS_ARRAY[@]}" | \
    jq --exit-status '(.results | length > 0)' 2>/dev/null
  ); then
    return 1
  fi

  # Download the file
  wget \
    --quiet \
    --output-document "$(basename "${key}")" \
    "$( \
      curl "${CURL_GET_S3_PRESIGNED_URL_ARGS_ARRAY[@]}" | \
      jq --raw-output '.results[0]' \
    )"
}

# Download the file from the filemanager
download_file_from_filemanager "${bucket}" "${key}"

# Set VCF Vars
vcf_file_name="$(basename "${key}")"

# Confirm vcf is gzipped; for plain-text VCF ensure the final line is newline-terminated
if [[ ! "${vcf_file_name}" =~ \.gz$ ]]; then
  if [[ -n "$(tail -c 1 "${vcf_file_name}")" ]]; then
    echo "Error viewing the vcf s3://${bucket}/${key}, final line does not end with newline" 1>&2
    exit 1
  fi
  exit 0
fi

# Pipe through zcat to confirm valid file
if ! zcat "${vcf_file_name}" 1>/dev/null; then
  echo "Error viewing the vcf s3://${bucket}/${key}, vcf is corrupted" 1>&2
  exit 1
fi

# Try and view the vcf file from bcftools
# Also generate the vcf stats
if ! bcftools view "${vcf_file_name}" 1>/dev/null 2>"${ERROR_LOGS_FILE}"; then
  echo "VCF file is not corrupted but not valid, nothing we can do, and we cannot check the index" 1>&2
  if [[ -s "${ERROR_LOGS_FILE}" ]]; then
    cat "${ERROR_LOGS_FILE}"
  fi
  exit 0
fi

# Download the index file from the filemanager
if ! (
  download_file_from_filemanager "${bucket}" "${key}.tbi"
) then
  echo "No vcf index to validate, skipping" 1>&2
else
  echo "Checking with vcf index" 1>&2
  bcftools view "${vcf_file_name}" 1>/dev/null 2>"${ERROR_LOGS_FILE}"

  if [[ -s "${ERROR_LOGS_FILE}" ]]; then
    echo "Error viewing the vcf s3://${bucket}/${key}, but because vcf-index is corrupted" 1>&2
    exit 1
  fi

fi
