variable "region" {
  type        = string
  description = "AWS region for the control-plane host. Informational here; the provider block that actually authenticates is supplied by the caller (see live/aws/terragrunt.hcl), not by this module."
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type for the control-plane host. This is the Linux control plane only, not an EC2 Mac instance."
  default     = "t3.small"
}

variable "vpc_id" {
  type        = string
  description = "VPC to place the control-plane host and security group in."
}

variable "subnet_id" {
  type        = string
  description = "Subnet to launch the control-plane host into."
}
