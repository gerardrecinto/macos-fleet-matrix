variable "region" {
  type        = string
  description = "AWS region. Informational here; the provider block is supplied by the caller (live/eks/terragrunt.hcl)."
  default     = "us-west-2"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name. Also the value of the karpenter.sh/discovery tag on the subnets and node security group."
  default     = "mfm-workloads"
}

variable "cluster_version" {
  type    = string
  default = "1.31"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for the control plane ENIs, the system node group and Karpenter-launched nodes. Tagged for Karpenter discovery by this module."
}

variable "system_instance_types" {
  type    = list(string)
  default = ["m6i.large"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
