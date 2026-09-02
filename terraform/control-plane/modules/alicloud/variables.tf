variable "region" {
  type        = string
  description = "AliCloud region. Informational here; the provider block that actually authenticates is supplied by the caller (see live/alicloud/terragrunt.hcl), not by this module."
  default     = "us-west-1"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "instance_type" {
  type        = string
  description = "ECS instance type for the control-plane host."
  default     = "ecs.t6-c1m1.large"
}

variable "vpc_id" {
  type        = string
  description = "VPC to place the security group in."
}

variable "vswitch_id" {
  type        = string
  description = "VSwitch to launch the control-plane host into."
}

variable "security_group_name" {
  type    = string
  default = "mfm-control-plane"
}
