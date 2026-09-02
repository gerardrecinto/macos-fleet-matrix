terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "resource_group_name" {
  type        = string
  description = "Existing resource group to deploy the control-plane host into."
}

variable "location" {
  type    = string
  default = "westus2"
}

variable "image_ref" {
  type        = string
  description = "Container image reference to pull and smoke-test on boot."
  default     = "ghcr.io/gerardrecinto/macos-fleet-matrix:latest"
}

variable "vm_size" {
  type    = string
  default = "Standard_B2s"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID to attach the control-plane host's NIC to."
}

variable "admin_ssh_public_key" {
  type        = string
  description = "SSH public key material for the control-plane host's admin user."
}

resource "azurerm_network_security_group" "control_plane" {
  name                = "mfm-control-plane-nsg"
  location            = var.location
  resource_group_name = var.resource_group_name

  security_rule {
    name                       = "AllowHTTPSEgress"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "control_plane" {
  name                = "mfm-control-plane-nic"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_network_interface_security_group_association" "control_plane" {
  network_interface_id      = azurerm_network_interface.control_plane.id
  network_security_group_id = azurerm_network_security_group.control_plane.id
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

  custom_data = base64encode(templatefile("${path.module}/../cloud-init.yaml.tpl", {
    image_ref = var.image_ref
  }))
}

output "vm_id" {
  value = azurerm_linux_virtual_machine.control_plane.id
}
