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

variable "enable_ec2_api" {
  type        = bool
  description = "If true, create an EC2 API host and route CloudFront /api/* to it. (Lightsail is unavailable in us-west-1.)"
  default     = true
}

variable "ec2_api_instance_type" {
  type        = string
  description = "EC2 size for the API. t3.small ≈ 2 GB RAM (~$12–15/mo on-demand)."
  default     = "t3.small"
}
