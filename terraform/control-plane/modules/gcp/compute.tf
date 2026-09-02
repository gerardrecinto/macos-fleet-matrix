locals {
  # Self-contained on purpose: this module does not reach outside its own
  # directory for a shared template, so it stays usable on its own (e.g. if
  # published to a registry) instead of depending on repo layout.
  cloud_init = <<-CLOUDINIT
    #cloud-config
    package_update: true
    packages:
      - docker.io

    write_files:
      - path: /etc/systemd/system/mfm-control-plane.service
        content: |
          [Unit]
          Description=macOS Fleet Matrix control-plane smoke check
          After=docker.service network-online.target
          Requires=docker.service
          Wants=network-online.target

          [Service]
          Type=oneshot
          ExecStartPre=/usr/bin/docker pull ${var.image_ref}
          ExecStart=/usr/bin/docker run --rm ${var.image_ref} inventory sample

          [Install]
          WantedBy=multi-user.target

    runcmd:
      - systemctl daemon-reload
      - systemctl enable mfm-control-plane.service
      - systemctl start mfm-control-plane.service
  CLOUDINIT
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
    user-data = local.cloud_init
  }
}
