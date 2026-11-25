# Server-side encryption key for BYOK payloads (Fernet).
# 32 random bytes as URL-safe base64 + padding (cryptography rejects unpadded keys).
resource "random_id" "fernet" {
  byte_length = 32
}

locals {
  # random_id.b64_url is unpadded; Fernet needs standard base64url with "=".
  fernet_key = "${random_id.fernet.b64_url}${substr("====", 0, (4 - length(random_id.fernet.b64_url) % 4) % 4)}"
}

resource "aws_ssm_parameter" "fernet_key" {
  name        = "/${var.project_name}/thyme_secrets_key"
  description = "Fernet key for encrypting user BYOK API keys"
  type        = "SecureString"
  value       = local.fernet_key

  tags = {
    Project = var.project_name
  }

  lifecycle {
    ignore_changes = [value]
  }
}

