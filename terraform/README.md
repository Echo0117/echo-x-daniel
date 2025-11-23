Terraform for echo-x-daniel (ECS Fargate with ALB)

This Terraform stacks provisions:
- VPC with two public subnets (for simplicity)
- ECR repository
- ECS Fargate cluster + task definition + service
- Application Load Balancer (HTTP)
- IAM roles (execution + task), with execution role allowed to read SSM Parameter Store secrets and task role allowed to access DynamoDB tables
- CloudWatch Logs group /ecs/echo-x-daniel

Defaults are aligned with your deploy.sh and taskdef.json:
- Region: eu-north-1
- Container port: 8080
- Health check path: /healthz
- Container name: web
- CPU: 512, Memory: 1024

Prerequisites
- Terraform >= 1.4
- AWS CLI configured with credentials
- Docker to build/push the image (outside Terraform)

Variables of note
- docker_image_tag: The image tag to deploy (default: latest). Change this to roll out a specific version.
- environment: Map of plain env vars injected into the container.
- ssm_parameters: Map of secret env var name -> SSM Parameter name (e.g., /echo/app/SECRET_KEY). These are fetched by the ECS agent using the execution role.

Quick start

1) Initialize

   terraform init

2) Plan (edit values as needed or use a tfvars file)

   terraform plan -var "aws_region=eu-north-1" -var "docker_image_tag=latest"

3) Apply

   terraform apply -var "aws_region=eu-north-1" -var "docker_image_tag=latest"

After apply, you’ll get the ALB DNS name in outputs. The service will point to the ECR repo URL with the tag you specified.

Build & push your Docker image (using your script, without ECS deploy):

   ./deploy.sh --region eu-north-1 --repo echo-x-daniel

This builds and pushes :latest and :$VERSION. Terraform references the tag in docker_image_tag (default: latest). To roll out a new build tagged latest without changing Terraform, you can force a new deployment via:

   aws ecs update-service --cluster echo-x-daniel-cluster --service echo-x-daniel --force-new-deployment

Or, change docker_image_tag to the specific version and terraform apply.

Notes
- For production, prefer private subnets, ALB TLS, autoscaling, and a remote state backend (see backend.tf.example).
- Ensure your SSM parameters exist and are readable by the execution role.
