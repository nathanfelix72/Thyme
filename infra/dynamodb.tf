resource "aws_dynamodb_table" "user_secrets" {
  name         = "${var.project_name}-user-secrets"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project = var.project_name
    Purpose = "BYOK-encrypted-provider-keys"
  }
}

# Ready for the recipes sprint — empty table, no write traffic yet.
resource "aws_dynamodb_table" "recipes" {
  name         = "${var.project_name}-recipes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "recipe_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "recipe_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project = var.project_name
    Purpose = "standardized-recipe-json"
  }
}
