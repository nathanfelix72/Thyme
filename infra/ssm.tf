# Server-side encryption key for BYOK payloads (Fernet).
# 32 random bytes as URL-safe base64 matches cryptography.fernet.Fernet keys.
resource "random_id" "fernet" {
  byte_length = 32
}

resource "aws_ssm_parameter" "fernet_key" {
  name        = "/${var.project_name}/thyme_secrets_key"
  description = "Fernet key for encrypting user BYOK API keys"
  type        = "SecureString"
  value       = random_id.fernet.b64_url

  tags = {
    Project = var.project_name
  }

  lifecycle {
    ignore_changes = [value]
  }
}

