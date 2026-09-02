include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

locals {
  root = include.root.locals
}

terraform {
  source = "../../modules/openstack"
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "openstack" {
      cloud = "openstack"
    }
  EOF
}

# Placeholder identifier: this repository provisions no real OpenStack
# cloud. Replace network_id with your own before running `terragrunt apply`,
# and configure a `clouds.yaml` entry named "openstack" for authentication.
inputs = {
  network_id = "REPLACE_ME-network-uuid"
  image_ref  = local.root.image_ref
}
