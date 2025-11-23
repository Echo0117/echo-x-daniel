#!/usr/bin/env bash
set -euo pipefail

# ==== EDIT THESE IF YOUR NAMES DIFFER ====
AWS_REGION="eu-north-1"
CLUSTER="echo-x-daniel-cluster"
SERVICE="echo-x-daniel-svc"
ECR_REPO="echo-x-daniel"          # your ECR repository name
IMAGE_TAG="latest"                 # change if you version images
# ========================================

# ==== Your provided values ====
AUTH_USERNAME="daniel"
AUTH_PASSWORD="01031997daniel"
SECRET_KEY="9f44f32f3b0e96c6b3b1d82f26c4a981a3e84fa0b889f6fadc2a8149e96f4c52"

DDB_TABLE="echo_x_daniel_messages"
DDB_TABLE_POSTS="echo_x_daniel_posts"
AUTO_CREATE_TABLE="1"
# ==============================

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
EXEC_ROLE_ARN=$(aws iam get-role --role-name ecsTaskExecutionRole --query 'Role.Arn' --output text 2>/dev/null || true)
if [[ -z "${EXEC_ROLE_ARN:-}" ]]; then
  echo "ecsTaskExecutionRole not found. Creating one…"
  aws iam create-role --role-name ecsTaskExecutionRole \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }' >/dev/null
  aws iam attach-role-policy --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
  EXEC_ROLE_ARN=$(aws iam get-role --role-name ecsTaskExecutionRole --query 'Role.Arn' --output text)
fi

IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

echo "==> Putting SSM parameters"
aws ssm put-parameter --name "/echo/app/SECRET_KEY"    --value "$SECRET_KEY"    --type "SecureString" --overwrite --region "$AWS_REGION"
aws ssm put-parameter --name "/echo/app/AUTH_USERNAME" --value "$AUTH_USERNAME" --type "SecureString" --overwrite --region "$AWS_REGION"
aws ssm put-parameter --name "/echo/app/AUTH_PASSWORD" --value "$AUTH_PASSWORD" --type "SecureString" --overwrite --region "$AWS_REGION"

echo "==> Creating/Updating ECS Task Role"
cat > /tmp/ecs-task-trust.json <<'JSON'
{
  "Version":"2012-10-17",
  "Statement":[
    {"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}
  ]
}
JSON
aws iam get-role --role-name echo-xd-task-role >/dev/null 2>&1 || \
aws iam create-role --role-name echo-xd-task-role \
  --assume-role-policy-document file:///tmp/ecs-task-trust.json >/dev/null

cat > /tmp/echo-xd-task-policy.json <<JSON
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Effect":"Allow",
      "Action":["dynamodb:PutItem","dynamodb:Scan","dynamodb:DescribeTable"],
      "Resource":[
        "arn:aws:dynamodb:${AWS_REGION}:*:table/${DDB_TABLE}",
        "arn:aws:dynamodb:${AWS_REGION}:*:table/${DDB_TABLE_POSTS}"
      ]
    },
    {
      "Effect":"Allow",
      "Action":["ssm:GetParameter","ssm:GetParameters"],
      "Resource":[
        "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter/echo/app/*"
      ]
    },
    {
      "Effect":"Allow",
      "Action":["kms:Decrypt"],
      "Resource":"*",
      "Condition":{"ForAnyValue:StringEquals":{"kms:ResourceAliases":["alias/aws/ssm"]}}
    }
  ]
}
JSON
aws iam put-role-policy \
  --role-name echo-xd-task-role \
  --policy-name echo-xd-task-inline \
  --policy-document file:///tmp/echo-xd-task-policy.json >/dev/null
TASK_ROLE_ARN=$(aws iam get-role --role-name echo-xd-task-role --query 'Role.Arn' --output text)

echo "==> Ensuring CloudWatch log group"
aws logs describe-log-groups --log-group-name-prefix /ecs/echo-x-daniel --region "$AWS_REGION" \
  --query 'logGroups[?logGroupName==`/ecs/echo-x-daniel`].logGroupName' --output text >/dev/null 2>&1 || \
aws logs create-log-group --log-group-name /ecs/echo-x-daniel --region "$AWS_REGION" >/dev/null

echo "==> Building Task Definition JSON"
cat > /tmp/echo-x-daniel-taskdef.json <<JSON
{
  "family": "echo-x-daniel-task",
  "networkMode": "awsvpc",
  "cpu": "512",
  "memory": "1024",
  "requiresCompatibilities": ["FARGATE"],
  "executionRoleArn": "${EXEC_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "${IMAGE_URI}",
      "essential": true,
      "portMappings": [ { "containerPort": 8080, "protocol": "tcp" } ],
      "environment": [
        { "name": "PORT", "value": "8080" },
        { "name": "AWS_REGION", "value": "${AWS_REGION}" },
        { "name": "DDB_TABLE", "value": "${DDB_TABLE}" },
        { "name": "DDB_TABLE_POSTS", "value": "${DDB_TABLE_POSTS}" },
        { "name": "AUTO_CREATE_TABLE", "value": "${AUTO_CREATE_TABLE}" }
      ],
      "secrets": [
        { "name": "SECRET_KEY",    "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter/echo/app/SECRET_KEY" },
        { "name": "AUTH_USERNAME", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter/echo/app/AUTH_USERNAME" },
        { "name": "AUTH_PASSWORD", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter/echo/app/AUTH_PASSWORD" }
      ],
      "healthCheck": {
        "retries": 3,
        "timeout": 5,
        "interval": 30,
        "startPeriod": 10,
        "command": ["CMD-SHELL","curl -fsS http://localhost:8080/healthz || exit 1"]
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-region": "${AWS_REGION}",
          "awslogs-group": "/ecs/echo-x-daniel",
          "awslogs-stream-prefix": "web"
        }
      }
    }
  ]
}
JSON

echo "==> Registering task definition"
aws ecs register-task-definition \
  --region "$AWS_REGION" \
  --cli-input-json file:///tmp/echo-x-daniel-taskdef.json >/dev/null

echo "==> Forcing new deployment of service ${SERVICE}"
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --force-new-deployment \
  --region "$AWS_REGION" >/dev/null

echo "All set. Watch CloudWatch logs: /ecs/echo-x-daniel"
