variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Short name for resources"
  type        = string
  default     = "echo-x-daniel"
}

variable "docker_image_tag" {
  description = "Tag for the image pushed to ECR"
  type        = string
  default     = "latest"
}

variable "desired_count" {
  description = "Number of Fargate tasks to run"
  type        = number
  default     = 1
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8080
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "public_subnets" {
  type    = list(string)
  default = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "cpu" {
  description = "Fargate task CPU units"
  type        = number
  default     = 512
}

variable "memory" {
  description = "Fargate task memory (MiB)"
  type        = number
  default     = 1024
}

variable "container_name" {
  description = "ECS container name inside the task definition"
  type        = string
  default     = "web"
}

variable "environment" {
  description = "Plain environment variables to inject into the container"
  type        = map(string)
  default = {
    PORT       = "8080"
    AWS_REGION = "eu-north-1"
    DDB_TABLE  = "echo_x_daniel_messages"
    DDB_TABLE_POSTS = "echo_x_daniel_posts"
    AUTO_CREATE_TABLE = "0"
  }
}

variable "ssm_parameters" {
  description = "Map of env var name -> SSM Parameter name (e.g. /echo/app/SECRET_KEY) for ECS secrets"
  type        = map(string)
  default = {
    SECRET_KEY    = "/echo/app/SECRET_KEY"
    AUTH_USERNAME = "/echo/app/AUTH_USERNAME"
    AUTH_PASSWORD = "/echo/app/AUTH_PASSWORD"
  }
}

variable "ddb_tables" {
  description = "DynamoDB tables the application needs access to"
  type        = list(string)
  default     = ["echo_x_daniel_messages", "echo_x_daniel_posts"]
}
