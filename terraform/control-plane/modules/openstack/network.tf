resource "openstack_networking_secgroup_v2" "control_plane" {
  name        = "mfm-control-plane"
  description = "No inbound; HTTPS egress only for image pulls."
}

resource "openstack_networking_secgroup_rule_v2" "egress_https" {
  direction         = "egress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.control_plane.id
}
