output "cluster_id" {
  value = azurerm_redhat_openshift_cluster.workloads.id
}

output "console_url" {
  value = azurerm_redhat_openshift_cluster.workloads.console_url
}

output "api_server_url" {
  value = azurerm_redhat_openshift_cluster.workloads.api_server_profile[0].url
}
