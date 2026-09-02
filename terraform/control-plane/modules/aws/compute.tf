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

resource "aws_instance" "control_plane" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.control_plane.id]
  user_data              = local.cloud_init

  tags = {
    Name    = "mfm-control-plane"
    Managed = "terraform"
  }
}
