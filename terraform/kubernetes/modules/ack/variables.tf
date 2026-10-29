variable "region" {
  type        = string
  description = "AliCloud region. Informational here; the provider block is supplied by the caller (live/ack/terragrunt.hcl)."
  default     = "us-west-1"
}

variable "cluster_name" {
  type    = string
  default = "mfm-workloads"
}

variable "cluster_spec" {
  type        = string
  description = "ACK managed cluster edition. ack.pro.small is the Pro edition, which has the SLA and the managed control-plane audit logging."
  default     = "ack.pro.small"
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes version. Leave empty to take the newest version ACK offers."
  default     = ""
}

variable "vswitch_ids" {
  type        = list(string)
  description = "VSwitches for the control-plane ENIs and the node pool. Use at least two zones."
}

variable "pod_vswitch_ids" {
  type        = list(string)
  description = "VSwitches Terway allocates pod ENIs from. Kept separate from the node VSwitches so pods get their own address space."
}

variable "service_cidr" {
  type    = string
  default = "172.21.0.0/20"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["ecs.g7.large"]
}

variable "node_count" {
  type    = number
  default = 3
}

variable "node_disk_size_gb" {
  type    = number
  default = 100
}
