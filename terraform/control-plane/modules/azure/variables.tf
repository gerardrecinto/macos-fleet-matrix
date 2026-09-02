variable "resource_group_name" {
  type        = string
  description = "Existing resource group to deploy the control-plane host into."
}

variable "location" {
  type    = string
  default = "westus2"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "vm_size" {
  type    = string
  default = "Standard_B2s"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID to attach the control-plane host's NIC to."
}

variable "admin_ssh_public_key" {
  type        = string
  description = "SSH public key material for the control-plane host's admin user."
}
