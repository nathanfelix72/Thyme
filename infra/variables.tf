variable "aws_region" {
  type        = string
  description = "AWS region for Thyme (default matches nathan-cli config)."
  default     = "us-west-1"
}

variable "project_name" {
  type        = string
  description = "Name prefix for resources."
  default     = "thyme"
}

variable "enable_cloudfront" {
  type        = bool
  description = "If true, put CloudFront in front of the S3 site (HTTPS + *.cloudfront.net URL)."
  default     = true
}
