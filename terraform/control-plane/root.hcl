# Root Terragrunt configuration shared by every provider under live/.
#
# Local backend on purpose: this is a reference repository with no
# provisioned cloud account or state bucket behind it (see README.md's
# "public repository, private credentials" principle). Each live/<provider>
# stack gets its own local state file, keyed by its path relative to this
# file, so `terragrunt run-all` never collides across providers. Point
# `remote_state.backend` at s3/gcs/azurerm/etc. to adapt this for a real
# deployment; nothing else in this file needs to change.

locals {
  image_ref = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

remote_state {
  backend = "local"

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }

  config = {
    path = "${path_relative_to_include()}/terraform.tfstate"
  }
}
