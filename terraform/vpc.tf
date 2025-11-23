resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags = { Name = "${var.project_name}-igw" }
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, length(var.public_subnets))
}

resource "aws_subnet" "public" {
  for_each = { for idx, cidr in var.public_subnets : tostring(idx) => cidr }
  vpc_id                 = aws_vpc.main.id
  cidr_block             = each.value
  map_public_ip_on_launch = true
  availability_zone      = local.azs[tonumber(each.key)]
  tags = { Name = "${var.project_name}-public-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public_assoc" {
  for_each = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

data "aws_availability_zones" "available" {}
