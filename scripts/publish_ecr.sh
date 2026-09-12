#!/usr/bin/env bash
# Local helper mirroring CI deploy publish step (optional).
set -euo pipefail
REGION="${AWS_REGION:-us-west-2}"
REPO="${ECR_REPOSITORY:-llm-serving-bench-serving}"
PARAM="${IMAGE_PARAM:-/llm-serving-bench/serving_image}"
TAG="${1:-latest}"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:${TAG}"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

docker build -f serving/Dockerfile -t "${URI}" .
docker push "${URI}"
aws ssm put-parameter --name "${PARAM}" --type String --value "${URI}" --overwrite --region "${REGION}"
echo "Published ${URI} → ${PARAM}"
