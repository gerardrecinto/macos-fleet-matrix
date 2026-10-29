include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../modules/ack"
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
# account. Replace the VSwitch IDs before running `terragrunt apply`.
inputs = {
  region          = "us-west-1"
  vswitch_ids     = ["vsw-REPLACE_ME_A", "vsw-REPLACE_ME_B"]
  pod_vswitch_ids = ["vsw-REPLACE_ME_PODS_A", "vsw-REPLACE_ME_PODS_B"]
}
