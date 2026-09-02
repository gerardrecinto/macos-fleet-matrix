resource "alicloud_security_group" "control_plane" {
  security_group_name = var.security_group_name
  vpc_id              = var.vpc_id
}

resource "alicloud_security_group_rule" "egress_https" {
  type              = "egress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "443/443"
  security_group_id = alicloud_security_group.control_plane.id
  cidr_ip           = "0.0.0.0/0"
}
