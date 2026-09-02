include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

locals {
  root = include.root.locals
}

terraform {
  source = "../../modules/gcp"
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "google" {
      project = var.project_id
      region  = var.region
    }
  EOF
}

# Placeholder identifiers: this repository provisions no real GCP project.
# Replace project_id with your own before running `terragrunt apply`.
inputs = {
  project_id = "mfm-reference-REPLACE_ME"
  region     = "us-west1"
  zone       = "us-west1-a"
  image_ref  = local.root.image_ref
}
