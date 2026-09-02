include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

locals {
  root = include.root.locals
}

terraform {
  source = "../../modules/alicloud"
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "alicloud" {
      region = var.region
    }
  EOF
}

# Placeholder identifiers: this repository provisions no real AliCloud
# account. Replace vpc_id/vswitch_id with your own before running
# `terragrunt apply`.
inputs = {
  region     = "us-west-1"
  vpc_id     = "vpc-REPLACE_ME"
  vswitch_id = "vsw-REPLACE_ME"
  image_ref  = local.root.image_ref
}
