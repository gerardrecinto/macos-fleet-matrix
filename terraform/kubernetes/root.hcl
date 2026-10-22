# Root Terragrunt configuration shared by every cluster stack under live/.
#
# Local backend for the same reason as ../control-plane/root.hcl: there is no
# provisioned account or state bucket behind this repository. Each
# live/<platform> stack keeps its own state file keyed by its path.

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
