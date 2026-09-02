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

data "alicloud_images" "ubuntu" {
  name_regex  = "^ubuntu_22_04_x64"
  most_recent = true
  owners      = "system"
}

resource "alicloud_instance" "control_plane" {
  instance_name              = "mfm-control-plane"
  instance_type              = var.instance_type
  image_id                   = data.alicloud_images.ubuntu.images[0].id
  vswitch_id                 = var.vswitch_id
  security_groups            = [alicloud_security_group.control_plane.id]
  internet_max_bandwidth_out = 0

  user_data = base64encode(local.cloud_init)
}
