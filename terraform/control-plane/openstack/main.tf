terraform {
  required_version = ">= 1.5"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53"
    }
  }
}

provider "openstack" {
  cloud = var.cloud_name
}

variable "cloud_name" {
  type        = string
  description = "Name of the clouds.yaml entry to authenticate with."
  default     = "openstack"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "flavor_name" {
  type    = string
  default = "m1.small"
}

variable "os_image_name" {
  type        = string
  description = "Name of the base OS image already present in Glance."
  default     = "Ubuntu-22.04"
}

variable "network_id" {
  type        = string
  description = "Neutron network UUID to attach the control-plane host to."
}

resource "openstack_networking_secgroup_v2" "control_plane" {
  name        = "mfm-control-plane"
  description = "No inbound; HTTPS egress only for image pulls."
}

resource "openstack_networking_secgroup_rule_v2" "egress_https" {
  direction         = "egress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.control_plane.id
}

resource "openstack_compute_instance_v2" "control_plane" {
  name            = "mfm-control-plane"
  flavor_name     = var.flavor_name
  image_name      = var.os_image_name
  security_groups = [openstack_networking_secgroup_v2.control_plane.name]

  network {
    uuid = var.network_id
  }

  user_data = templatefile("${path.module}/../cloud-init.yaml.tpl", {
    image_ref = var.image_ref
  })
}

output "instance_id" {
  value = openstack_compute_instance_v2.control_plane.id
}
