#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run as root: sudo bash deploy/scripts/install-production-guards.sh" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

install -D -m 0755 \
    "$repo_root/deploy/scripts/sshelper-maintenance" \
    /usr/local/sbin/sshelper-maintenance

install -D -m 0644 \
    "$repo_root/deploy/systemd/sshelper-maintenance.service" \
    /etc/systemd/system/sshelper-maintenance.service
install -D -m 0644 \
    "$repo_root/deploy/systemd/sshelper-maintenance.timer" \
    /etc/systemd/system/sshelper-maintenance.timer
install -D -m 0644 \
    "$repo_root/deploy/systemd/sshelper-journald.conf" \
    /etc/systemd/journald.conf.d/sshelper-limits.conf
install -D -m 0644 \
    "$repo_root/deploy/systemd/sshelper-service-override.conf" \
    /etc/systemd/system/sshelper.service.d/reliability.conf

systemctl daemon-reload
systemctl restart systemd-journald
systemctl enable --now sshelper-maintenance.timer

# Repair an already-full disk immediately, then ensure the bot is enabled.
/usr/local/sbin/sshelper-maintenance
systemctl enable sshelper.service
systemctl restart sshelper.service

echo
echo "Production guards installed."
systemctl --no-pager status sshelper-maintenance.timer | sed -n '1,12p'
df -h /

