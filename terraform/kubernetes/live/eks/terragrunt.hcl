include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../modules/eks"
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
# Replace the VPC and subnet IDs before running `terragrunt apply`.
inputs = {
  region             = "us-west-2"
  vpc_id             = "vpc-REPLACE_ME"
  private_subnet_ids = ["subnet-REPLACE_ME_A", "subnet-REPLACE_ME_B", "subnet-REPLACE_ME_C"]
}
