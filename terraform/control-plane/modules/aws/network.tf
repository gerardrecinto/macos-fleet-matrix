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
