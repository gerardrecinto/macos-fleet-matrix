# The control plane plus a small managed node group. Karpenter cannot launch
# the node it runs on, so its controller and the cluster add-ons live on a
# group that does not depend on it. Every other node comes from Karpenter
# (deploy/k8s/karpenter/).
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  # Private API endpoint only: workload code is untrusted (docs/THREAT-MODEL.md).
  cluster_endpoint_public_access           = false
  cluster_endpoint_private_access          = true
  enable_cluster_creator_admin_permissions = true

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  cluster_addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = {}
    eks-pod-identity-agent = {}
  }

  eks_managed_node_groups = {
    system = {
      instance_types = var.system_instance_types
      ami_type       = "AL2023_x86_64_STANDARD"

      min_size     = 2
      max_size     = 3
      desired_size = 2

      labels = {
        workload = "system"
      }
    }
  }

  # Karpenter finds the node security group by this tag.
  node_security_group_tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }

  tags = var.tags
}

# Karpenter finds the subnets it may launch into by this tag. The subnets are
# passed in rather than created here, so the tag is added to them.
resource "aws_ec2_tag" "karpenter_discovery" {
  for_each = toset(var.private_subnet_ids)

  resource_id = each.value
  key         = "karpenter.sh/discovery"
  value       = var.cluster_name
}

# IAM for the controller and for the nodes it launches, plus the SQS queue that
# carries spot interruption and rebalance notices to it. The controller itself
# and its NodePools are installed by ArgoCD (deploy/argocd/karpenter.yaml).
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 20.0"

  cluster_name = module.eks.cluster_name

  enable_v1_permissions = true

  # EKS Pod Identity, not IRSA, gives the controller its AWS permissions.
  create_pod_identity_association = true
  namespace                       = "kube-system"

  # A fixed role name lets deploy/k8s/karpenter/ec2nodeclass.yaml reference it
  # without reading a Terraform output.
  node_iam_role_use_name_prefix = false
  node_iam_role_name            = "${var.cluster_name}-karpenter-node"
  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  tags = var.tags
}
