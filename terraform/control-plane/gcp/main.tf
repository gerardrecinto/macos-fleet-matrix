terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  description = "GCP project to deploy the control-plane host into."
}

variable "region" {
  type    = string
  default = "us-west1"
}

variable "zone" {
  type    = string
  default = "us-west1-a"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "machine_type" {
  type    = string
  default = "e2-small"
}

variable "network" {
  type    = string
  default = "default"
}

resource "google_compute_firewall" "control_plane_egress" {
  name    = "mfm-control-plane-egress-https"
  network = var.network

  direction          = "EGRESS"
  destination_ranges = ["0.0.0.0/0"]

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  target_tags = ["mfm-control-plane"]
}

resource "google_compute_instance" "control_plane" {
  name         = "mfm-control-plane"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["mfm-control-plane"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network = var.network
  }

  metadata = {
    user-data = templatefile("${path.module}/../cloud-init.yaml.tpl", {
      image_ref = var.image_ref
    })
  }
}

output "instance_self_link" {
  value = google_compute_instance.control_plane.self_link
}
