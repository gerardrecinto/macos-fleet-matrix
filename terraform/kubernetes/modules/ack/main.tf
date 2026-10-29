resource "alicloud_cs_managed_kubernetes" "workloads" {
  name         = var.cluster_name
  cluster_spec = var.cluster_spec
  version      = var.kubernetes_version == "" ? null : var.kubernetes_version

  vswitch_ids     = var.vswitch_ids
  pod_vswitch_ids = var.pod_vswitch_ids
  service_cidr    = var.service_cidr

  # Private API endpoint only. Workload code is untrusted (docs/THREAT-MODEL.md),
  # so the API server is not reachable from the internet.
  slb_internet_enabled = false
  new_nat_gateway      = false
  deletion_protection  = true

  addons {
    name = "terway-eniip"
  }

  addons {
    name = "csi-plugin"
  }

  addons {
    name = "csi-provisioner"
  }
}

resource "alicloud_cs_kubernetes_node_pool" "workloads" {
  cluster_id     = alicloud_cs_managed_kubernetes.workloads.id
  node_pool_name = "${var.cluster_name}-default"
  vswitch_ids    = var.vswitch_ids
  instance_types = var.node_instance_types
  desired_size   = var.node_count

  system_disk_category = "cloud_essd"
  system_disk_size     = var.node_disk_size_gb

  # Nodes are replaced, not repaired in place, which matches the one-job,
  # destroy-after lease model for the runners this cluster hosts.
  management {
    auto_repair  = true
    auto_upgrade = false
  }
}
