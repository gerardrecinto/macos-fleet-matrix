variable "project_id" {
  type        = string
  description = "GCP project to deploy the control-plane host into. Informational here; the provider block that actually authenticates is supplied by the caller (see live/gcp/terragrunt.hcl), not by this module."
}

variable "region" {
  type    = string
  default = "us-west1"
}

variable "zone" {
  type    = string
  default = "us-west1-a"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "machine_type" {
  type    = string
  default = "e2-small"
}

variable "network" {
  type    = string
  default = "default"
}
