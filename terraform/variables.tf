variable "macos_version" {
  type        = string
  description = "Pinned macOS version used by the image pipeline."
  default     = "15"
}

variable "xcode_version" {
  type        = string
  description = "Pinned Xcode version used by the image pipeline."
  default     = "16"
}

output "image_label" {
  value = "macos-${var.macos_version}-xcode-${var.xcode_version}"
}
