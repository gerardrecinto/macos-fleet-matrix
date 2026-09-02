include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

locals {
  root = include.root.locals
}

terraform {
  source = "../../modules/aws"
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "aws" {
      region = var.region
    }
  EOF
}

# Placeholder identifiers: this repository provisions no real AWS account.
# Replace vpc_id/subnet_id with your own before running `terragrunt apply`.
inputs = {
  region        = "us-west-2"
  image_ref     = local.root.image_ref
  instance_type = "t3.small"
  vpc_id        = "vpc-REPLACE_ME"
  subnet_id     = "subnet-REPLACE_ME"
}
