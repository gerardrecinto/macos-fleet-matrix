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

resource "openstack_compute_instance_v2" "control_plane" {
  name            = "mfm-control-plane"
  flavor_name     = var.flavor_name
  image_name      = var.os_image_name
  security_groups = [openstack_networking_secgroup_v2.control_plane.name]

  network {
    uuid = var.network_id
  }

  user_data = local.cloud_init
}
