terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type        = string
  description = "AWS region for the control-plane host."
  default     = "us-west-2"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type for the control-plane host. This is the Linux control plane only, not an EC2 Mac instance."
  default     = "t3.small"
}

variable "vpc_id" {
  type        = string
  description = "VPC to place the control-plane host and security group in."
}

variable "subnet_id" {
  type        = string
  description = "Subnet to launch the control-plane host into."
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "control_plane" {
  name        = "mfm-control-plane"
  description = "Fleet control-plane host: no inbound, HTTPS egress only."
  vpc_id      = var.vpc_id

  egress {
    description = "Outbound HTTPS for GHCR pulls and package mirrors."
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "control_plane" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.control_plane.id]

  user_data = templatefile("${path.module}/../cloud-init.yaml.tpl", {
    image_ref = var.image_ref
  })

  tags = {
    Name    = "mfm-control-plane"
    Managed = "terraform"
  }
}

output "instance_id" {
  value = aws_instance.control_plane.id
}
