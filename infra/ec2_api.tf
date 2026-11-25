# Always-on API host in us-west-1 (Lightsail is not offered in this region).
# t3.small ≈ 2 GB — similar budget/capability to the planned Lightsail small bundle.

data "aws_ami" "ubuntu_2404" {
  count       = var.enable_ec2_api ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "tls_private_key" "api" {
  count     = var.enable_ec2_api ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "api" {
  count      = var.enable_ec2_api ? 1 : 0
  key_name   = "${var.project_name}-api"
  public_key = tls_private_key.api[0].public_key_openssh
}

resource "local_sensitive_file" "api_ssh_key" {
  count           = var.enable_ec2_api ? 1 : 0
  filename        = "${path.module}/thyme-api.pem"
  content         = tls_private_key.api[0].private_key_pem
  file_permission = "0600"
}

resource "aws_security_group" "api" {
  count       = var.enable_ec2_api ? 1 : 0
  name        = "${var.project_name}-api"
  description = "Thyme API - SSH and HTTP API for CloudFront origin"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "API (CloudFront origin)"
    from_port   = 8765
    to_port     = 8765
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = var.project_name
    Role    = "api"
  }
}

data "aws_iam_policy_document" "api_assume" {
  count = var.enable_ec2_api ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "api" {
  count = var.enable_ec2_api ? 1 : 0

  statement {
    sid = "DynamoRecipesAndSecrets"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchWriteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [
      aws_dynamodb_table.recipes.arn,
      aws_dynamodb_table.user_secrets.arn,
    ]
  }

  statement {
    sid = "ReadThymeSecrets"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      aws_ssm_parameter.fernet_key.arn,
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/thyme/*",
    ]
  }

  statement {
    sid       = "DecryptFernetKey"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }

  statement {
    sid = "CognitoAdmin"
    actions = [
      "cognito-idp:ListUsers",
      "cognito-idp:AdminListGroupsForUser",
      "cognito-idp:AdminAddUserToGroup",
      "cognito-idp:AdminRemoveUserFromGroup",
      "cognito-idp:AdminGetUser",
    ]
    resources = [aws_cognito_user_pool.main.arn]
  }
}

resource "aws_iam_role" "api" {
  count              = var.enable_ec2_api ? 1 : 0
  name               = "${var.project_name}-api"
  assume_role_policy = data.aws_iam_policy_document.api_assume[0].json

  tags = {
    Project = var.project_name
  }
}

resource "aws_iam_role_policy" "api" {
  count  = var.enable_ec2_api ? 1 : 0
  name   = "${var.project_name}-api"
  role   = aws_iam_role.api[0].id
  policy = data.aws_iam_policy_document.api[0].json
}

resource "aws_iam_instance_profile" "api" {
  count = var.enable_ec2_api ? 1 : 0
  name  = "${var.project_name}-api"
  role  = aws_iam_role.api[0].name
}

resource "aws_instance" "api" {
  count                       = var.enable_ec2_api ? 1 : 0
  ami                         = data.aws_ami.ubuntu_2404[0].id
  instance_type               = var.ec2_api_instance_type
  key_name                    = aws_key_pair.api[0].key_name
  vpc_security_group_ids      = [aws_security_group.api[0].id]
  iam_instance_profile        = aws_iam_instance_profile.api[0].name
  associate_public_ip_address = true

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  # Hop limit 2 so boto3 inside Docker can reach IMDSv2 via the instance role.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    mkdir -p /opt/thyme
    chown ubuntu:ubuntu /opt/thyme
  EOT

  tags = {
    Name    = "${var.project_name}-api"
    Project = var.project_name
    Role    = "api"
  }
}

resource "aws_eip" "api" {
  count  = var.enable_ec2_api ? 1 : 0
  domain = "vpc"

  tags = {
    Name    = "${var.project_name}-api"
    Project = var.project_name
  }
}

resource "aws_eip_association" "api" {
  count         = var.enable_ec2_api ? 1 : 0
  instance_id   = aws_instance.api[0].id
  allocation_id = aws_eip.api[0].id
}
