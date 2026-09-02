terraform {
  required_version = ">= 1.5"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.230"
    }
  }
}

provider "alicloud" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-west-1"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "instance_type" {
  type        = string
  description = "ECS instance type for the control-plane host."
  default     = "ecs.t6-c1m1.large"
}

variable "vpc_id" {
  type        = string
  description = "VPC to place the security group in."
}

variable "vswitch_id" {
  type        = string
  description = "VSwitch to launch the control-plane host into."
}

variable "security_group_name" {
  type    = string
  default = "mfm-control-plane"
}

data "alicloud_images" "ubuntu" {
  name_regex  = "^ubuntu_22_04_x64"
  most_recent = true
  owners      = "system"
}

resource "alicloud_security_group" "control_plane" {
  security_group_name = var.security_group_name
  vpc_id              = var.vpc_id
}

resource "alicloud_security_group_rule" "egress_https" {
  type              = "egress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "443/443"
  security_group_id = alicloud_security_group.control_plane.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_instance" "control_plane" {
  instance_name              = "mfm-control-plane"
  instance_type              = var.instance_type
  image_id                   = data.alicloud_images.ubuntu.images[0].id
  vswitch_id                 = var.vswitch_id
  security_groups            = [alicloud_security_group.control_plane.id]
  internet_max_bandwidth_out = 0

  user_data = base64encode(templatefile("${path.module}/../cloud-init.yaml.tpl", {
    image_ref = var.image_ref
  }))
}

output "instance_id" {
  value = alicloud_instance.control_plane.id
}
