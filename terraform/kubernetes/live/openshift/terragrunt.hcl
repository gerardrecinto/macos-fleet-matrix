include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../modules/openshift"
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
# subscription. Replace every REPLACE_ME before running `terragrunt apply`,
# and pass the service principal secret through TF_VAR_service_principal_client_secret
# rather than writing it here.
inputs = {
  resource_group_name         = "REPLACE_ME"
  openshift_version           = "4.16.30"
  control_plane_subnet_id     = "/subscriptions/REPLACE_ME/resourceGroups/REPLACE_ME/providers/Microsoft.Network/virtualNetworks/REPLACE_ME/subnets/control-plane"
  worker_subnet_id            = "/subscriptions/REPLACE_ME/resourceGroups/REPLACE_ME/providers/Microsoft.Network/virtualNetworks/REPLACE_ME/subnets/workers"
  service_principal_client_id = "REPLACE_ME"
}
