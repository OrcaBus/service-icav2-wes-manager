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
echo "bam is valid" 1>&2

# Checking if bam index is valid
CURL_GET_S3_PRESIGNED_URL_BAI_ARGS_ARRAY=( \
  "--fail" "--silent" "--location" "--show-error" \
  "--header" "Accept: application/json" \
  "--header" "Authorization: Bearer ${ORCABUS_TOKEN}" \
  "https://file.${HOSTNAME}/api/v1/s3/presign?responseContentDisposition=inline&bucket=${bucket}&key=${key}.bai" \
)

if ! (
  curl "${CURL_GET_S3_PRESIGNED_URL_BAI_ARGS_ARRAY[@]}" | \
  jq --exit-status '(.results | length) > 0' 2>/dev/null \
); then
  echo "No bam index, skipping bam index check!" 1>&2
  exit
fi

# Download the bam index
bai_presigned_url="$( \
  curl "${CURL_GET_S3_PRESIGNED_URL_BAI_ARGS_ARRAY[@]}" | \
  jq --raw-output '.results[0]' \
)"
wget \
  --quiet \
  --output-document "bam_index.bai" \
  "${bai_presigned_url}"

# Build the targets file containing the last chromosome in the file
samtools view \
  --header-only \
  --customized-index \
  "${bam_presigned_url}" \
  "bam_index.bai" | \
grep '^@SQ' | \
tail -n1 | \
jq --raw-input --raw-output \
  '
    # Input will look like this
    # "@SQ\tSN:HLA-DRB1*16:02:01\tLN:11005"
    split("\t") as $sq_line |
    [
      # Contig name
      ($sq_line[1] | gsub("^SN:"; "")),
      # Start
      0,
      # Contig end
      ($sq_line[2] | gsub("^LN:"; ""))
    ] |
    # To bed format
    join("\t")
    # Output will look like
    # HLA-DRB1*16:02:01    0  11005
  ' > "targets.txt"

# Ensure we can view the last item with a corrupted index
samtools view \
  --targets-file "targets.txt" \
  --use-index \
  --customized-index \
  "${bam_presigned_url}" \
  "bam_index.bai" 1>/dev/null
