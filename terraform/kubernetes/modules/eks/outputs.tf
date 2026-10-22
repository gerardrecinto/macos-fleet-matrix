output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "karpenter_queue_name" {
  description = "Interruption queue name for the Karpenter chart's settings.interruptionQueue value."
  value       = module.karpenter.queue_name
}

output "karpenter_node_role_name" {
  description = "IAM role name for the EC2NodeClass role field."
  value       = module.karpenter.node_iam_role_name
}
