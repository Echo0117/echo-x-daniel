#!/usr/bin/env bash
set -euo pipefail

# ---------- Defaults ----------
AWS_REGION="${AWS_REGION:-eu-north-1}"
REPO="${REPO:-echo-x-daniel}"
VERSION="${VERSION:-v$(date +%Y%m%d-%H%M)}"
INSTALL_HF="${INSTALL_HF:-0}"      # 1 安装 transformers/peft/torch
NO_CACHE="${NO_CACHE:-0}"          # 1 禁用 cache
PLATFORM="linux/amd64"             # 固定 amd64，避免 Fargate 架构不匹配

# ECS（可选自动发布）
CLUSTER="${CLUSTER:-}"             # 例：echo-x-daniel-cluster
SERVICE="${SERVICE:-}"             # 例：echo-x-daniel-svc
CONTAINER_NAME="${CONTAINER_NAME:-web}"   # 任务定义里的 container name
USE_LATEST="${USE_LATEST:-1}"      # 1：服务/TD用 :latest，只强制重部署；0：注册新修订版并改成 :$VERSION

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]
  --region <aws-region>        (default: ${AWS_REGION})
  --repo <ecr-repo>            (default: ${REPO})
  --version <tag>              (default: ${VERSION})
  --hf                         include HF stack (INSTALL_HF=1)
  --no-cache                   docker build without cache
  --cluster <ecs-cluster>      deploy to ECS cluster
  --service <ecs-service>      deploy to ECS service
  --container <name>           container name in task def (default: ${CONTAINER_NAME})
  --use-latest                 keep :latest; force new deployment (default)
  --pin-version                register new TD revision with :\$VERSION and switch
  -h|--help
EOF
}

# ---------- Flags ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) AWS_REGION="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --version) VERSION="$2"; shift 2;;
    --hf) INSTALL_HF="1"; shift 1;;
    --no-cache) NO_CACHE="1"; shift 1;;
    --cluster) CLUSTER="$2"; shift 2;;
    --service) SERVICE="$2"; shift 2;;
    --container) CONTAINER_NAME="$2"; shift 2;;
    --use-latest) USE_LATEST="1"; shift 1;;
    --pin-version) USE_LATEST="0"; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1"; usage; exit 1;;
  esac
done

command -v aws >/dev/null || { echo "❌ aws CLI not found"; exit 1; }
command -v docker >/dev/null || { echo "❌ docker not found"; exit 1; }

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REG="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${ECR_REG}/${REPO}"

echo "🔧 Region:        ${AWS_REGION}"
echo "🔧 Repo:          ${REPO}"
echo "🔧 Version tag:   ${VERSION}"
echo "🔧 HF stack:      ${INSTALL_HF}"
echo "🔧 Build platform ${PLATFORM}"
[[ -n "${CLUSTER}" && -n "${SERVICE}" ]] && echo "🚀 ECS deploy → ${CLUSTER}/${SERVICE} (container: ${CONTAINER_NAME}, use_latest=${USE_LATEST})"

# Ensure repo
aws ecr describe-repositories --repository-names "${REPO}" --region "${AWS_REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${REPO}" --region "${AWS_REGION}" >/dev/null

# Login
aws ecr get-login-password --region "${AWS_REGION}" \
 | docker login --username AWS --password-stdin "${ECR_REG}" >/dev/null

# Build args (safe for set -u)
BUILD_ARGS=()
[[ "${INSTALL_HF}" == "1" ]] && BUILD_ARGS+=( --build-arg INSTALL_HF=1 )
[[ "${NO_CACHE}" == "1" ]] && BUILD_ARGS+=( --no-cache )

echo "🏗️  Building & pushing image → ${ECR_URI}:${VERSION}"
export DOCKER_BUILDKIT=1
docker buildx create --use >/dev/null 2>&1 || true

# Optional: use registry-based cache (speeds up CI/builders without local cache)
CACHE_NAME="${ECR_URI}:buildcache"
docker buildx build \
  --platform "${PLATFORM}" \
  -t "${ECR_URI}:${VERSION}" \
  -t "${ECR_URI}:latest" \
  --cache-from type=registry,ref="${CACHE_NAME}" \
  --cache-to type=registry,ref="${CACHE_NAME}",mode=max \
  ${BUILD_ARGS[@]:-} \
  --push \
  .

echo ""
echo "✅ Pushed:"
echo "   ${ECR_URI}:${VERSION}"
echo "   ${ECR_URI}:latest"

# ---------- ECS Deploy (optional) ----------
if [[ -n "${CLUSTER}" && -n "${SERVICE}" ]]; then
  if [[ "${USE_LATEST}" == "1" ]]; then
    echo "🔁 Forcing new deployment (service uses :latest)…"
    aws ecs update-service \
      --cluster "${CLUSTER}" \
      --service "${SERVICE}" \
      --force-new-deployment >/dev/null
    echo "✅ ECS rolling restart kicked off."
  else
    command -v jq >/dev/null || { echo "❌ jq not found. Install jq or use --use-latest."; exit 1; }
    echo "🧱 Registering new task definition revision pinned to :${VERSION}…"
    TD_ARN=$(aws ecs describe-services --cluster "${CLUSTER}" --services "${SERVICE}" \
      --query 'services[0].taskDefinition' --output text)

    aws ecs describe-task-definition --task-definition "${TD_ARN}" --query 'taskDefinition' > /tmp/td.json

    # mutate image of the target container
    jq --arg IMG "${ECR_URI}:${VERSION}" --arg NAME "${CONTAINER_NAME}" '
      .containerDefinitions |= map(
        if .name == $NAME then .image = $IMG else . end
      )
      # clean read-only fields
      | del(.status, .taskDefinitionArn, .requiresAttributes, .compatibilities, .revision)
    ' /tmp/td.json > /tmp/td_mut.json

    NEW_TD_ARN=$(aws ecs register-task-definition \
      --cli-input-json file:///tmp/td_mut.json \
      --query 'taskDefinition.taskDefinitionArn' --output text)

    echo "📦 New TD: ${NEW_TD_ARN}"

    echo "🚀 Updating service to new TD…"
    aws ecs update-service \
      --cluster "${CLUSTER}" \
      --service "${SERVICE}" \
      --task-definition "${NEW_TD_ARN}" >/dev/null

    echo "✅ ECS service updated to ${NEW_TD_ARN}"
  fi

  echo "ℹ️  Watch rollout:"
  echo "aws ecs describe-services --cluster ${CLUSTER} --services ${SERVICE} --query 'services[0].deployments'"
fi

echo ""
echo "👉 If running on EC2 directly:"
echo "docker pull ${ECR_URI}:${VERSION}"
echo "docker rm -f ${REPO} 2>/dev/null || true"
echo "docker run -d --name ${REPO} -p 80:8000 ${ECR_URI}:${VERSION}"
