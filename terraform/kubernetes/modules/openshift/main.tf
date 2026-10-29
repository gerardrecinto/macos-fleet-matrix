resource "azurerm_redhat_openshift_cluster" "workloads" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name

  cluster_profile {
    domain      = var.domain
    version     = var.openshift_version
    pull_secret = var.pull_secret
  }

  network_profile {
    pod_cidr     = var.pod_cidr
    service_cidr = var.service_cidr
  }

  main_profile {
    vm_size   = var.control_plane_vm_size
    subnet_id = var.control_plane_subnet_id
  }

  worker_profile {
    vm_size      = var.worker_vm_size
    disk_size_gb = var.worker_disk_size_gb
    node_count   = var.worker_node_count
    subnet_id    = var.worker_subnet_id
  }

  # Private API server and ingress: workload code is untrusted
  # (docs/THREAT-MODEL.md), so neither endpoint is reachable from the internet.
  api_server_profile {
    visibility = "Private"
  }

  ingress_profile {
    visibility = "Private"
  }

  service_principal {
    client_id     = var.service_principal_client_id
    client_secret = var.service_principal_client_secret
  }
}
