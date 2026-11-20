output "aws_region" {
  value = var.aws_region
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_app_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "user_secrets_table" {
  value = aws_dynamodb_table.user_secrets.name
}

output "recipes_table" {
  value = aws_dynamodb_table.recipes.name
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "cloudfront_url" {
  value = var.enable_cloudfront ? "https://${aws_cloudfront_distribution.frontend[0].domain_name}" : null
}

output "ssm_fernet_param" {
  value = aws_ssm_parameter.fernet_key.name
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}

output "cloudfront_distribution_id" {
  value = var.enable_cloudfront ? aws_cloudfront_distribution.frontend[0].id : null
}

output "cognito_admins_group" {
  value = aws_cognito_user_group.admins.name
}
