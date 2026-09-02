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
      ExecStartPre=/usr/bin/docker pull ${image_ref}
      ExecStart=/usr/bin/docker run --rm ${image_ref} inventory sample

      [Install]
      WantedBy=multi-user.target

runcmd:
  - systemctl daemon-reload
  - systemctl enable mfm-control-plane.service
  - systemctl start mfm-control-plane.service
