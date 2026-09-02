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

resource "azurerm_linux_virtual_machine" "control_plane" {
  name                  = "mfm-control-plane"
  resource_group_name   = var.resource_group_name
  location              = var.location
  size                  = var.vm_size
  admin_username        = "mfm"
  network_interface_ids = [azurerm_network_interface.control_plane.id]

  admin_ssh_key {
    username   = "mfm"
    public_key = var.admin_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(local.cloud_init)
}
