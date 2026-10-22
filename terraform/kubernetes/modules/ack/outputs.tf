output "cluster_id" {
  value = alicloud_cs_managed_kubernetes.workloads.id
}

output "node_pool_id" {
  value = alicloud_cs_kubernetes_node_pool.workloads.id
}
