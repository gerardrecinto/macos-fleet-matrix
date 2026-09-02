variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "flavor_name" {
  type    = string
  default = "m1.small"
}

variable "os_image_name" {
  type        = string
  description = "Name of the base OS image already present in Glance."
  default     = "Ubuntu-22.04"
}

variable "network_id" {
  type        = string
  description = "Neutron network UUID to attach the control-plane host to."
}
