variable "location" {
  type    = string
  default = "westus2"
}

variable "resource_group_name" {
  type        = string
  description = "Existing resource group that holds the cluster. ARO creates a second, managed resource group for its own resources."
}

variable "cluster_name" {
  type    = string
  default = "mfm-workloads"
}

variable "domain" {
  type        = string
  description = "DNS prefix for the cluster, e.g. mfm. Must be unique in the region."
  default     = "mfm"
}

variable "openshift_version" {
  type        = string
  description = "OpenShift version. List supported versions with: az aro get-versions --location <region>"
}

variable "control_plane_subnet_id" {
  type = string
}

variable "worker_subnet_id" {
  type = string
}

variable "control_plane_vm_size" {
  type    = string
  default = "Standard_D8s_v5"
}

variable "worker_vm_size" {
  type    = string
  default = "Standard_D4s_v5"
}

variable "worker_node_count" {
  type    = number
  default = 3
}

variable "worker_disk_size_gb" {
  type    = number
  default = 128
}

variable "pod_cidr" {
  type    = string
  default = "10.128.0.0/14"
}

variable "service_cidr" {
  type    = string
  default = "172.30.0.0/16"
}

variable "service_principal_client_id" {
  type = string
}

variable "service_principal_client_secret" {
  type      = string
  sensitive = true
}

variable "pull_secret" {
  type        = string
  sensitive   = true
  description = "Red Hat pull secret JSON. Optional but required for the Red Hat operator catalogs."
  default     = null
}
