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
