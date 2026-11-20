# GitHub Actions → AWS deploy role (no long-lived access keys in GitHub).
# Reuses the account's existing GitHub OIDC provider if present.

data "aws_caller_identity" "current" {}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # This account's GitHub OIDC tokens use immutable owner@id/repo@id subjects
    # (same pattern as portfolio-github-deploy), not plain repo:user/name refs.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:nathanfelix72@131198703/Thyme@1464665864:*",
      ]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${var.project_name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json

  tags = {
    Project = var.project_name
  }
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid = "S3Sync"
    actions = [
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.frontend.arn]
  }

  statement {
    sid = "S3Objects"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
  }

  statement {
    sid = "CloudFrontInvalidate"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
      "cloudfront:ListInvalidations",
    ]
    resources = [
      var.enable_cloudfront ? aws_cloudfront_distribution.frontend[0].arn : "*",
    ]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "${var.project_name}-github-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
