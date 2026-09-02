include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

locals {
  root = include.root.locals
}

terraform {
  source = "../../modules/azure"
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "azurerm" {
      features {}
    }
  EOF
}

# Placeholder identifiers: this repository provisions no real Azure
# subscription. Replace resource_group_name/subnet_id/admin_ssh_public_key
# with your own before running `terragrunt apply`.
inputs = {
  resource_group_name  = "mfm-reference-REPLACE_ME"
  location             = "westus2"
  subnet_id            = "/subscriptions/REPLACE_ME/resourceGroups/REPLACE_ME/providers/Microsoft.Network/virtualNetworks/REPLACE_ME/subnets/REPLACE_ME"
  admin_ssh_public_key = "ssh-ed25519 REPLACE_ME"
  image_ref            = local.root.image_ref
}
