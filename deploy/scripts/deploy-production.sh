#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-sshelper.service}"
REMOTE="${REMOTE:-origin}"
RELEASE_BRANCH="${RELEASE_BRANCH:-andreysevcenko1-flats-detail-notifications}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_PYTHON="${VENV_PYTHON:-$REPO_ROOT/venv/bin/python}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/sshelper-backups}"

log() {
    printf '\n==> %s\n' "$*"
}

fail() {
    printf '\nERROR: %s\n' "$*" >&2
    exit 1
}

cd "$REPO_ROOT"
[[ -f .env ]] || fail ".env is missing in $REPO_ROOT"
[[ -x "$VENV_PYTHON" ]] || fail "Python virtualenv not found: $VENV_PYTHON"

log "Fetching release branch"
git fetch "$REMOTE" "$RELEASE_BRANCH"

log "Stopping $SERVICE_NAME"
sudo systemctl stop "$SERVICE_NAME" || true

log "Backing up production database"
mkdir -p "$BACKUP_DIR"
if [[ -f sshelper.db ]]; then
    backup="$BACKUP_DIR/sshelper-$(date +%Y%m%d-%H%M%S).db"
    cp --preserve=timestamps sshelper.db "$backup"
    printf 'Database backup: %s\n' "$backup"
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'sshelper-*.db' -print0 \
        | xargs -0 ls -1t \
        | tail -n +11 \
        | xargs -r rm --
fi

log "Installing the exact tested release"
git cherry-pick --abort >/dev/null 2>&1 || true
git merge --abort >/dev/null 2>&1 || true
git rebase --abort >/dev/null 2>&1 || true
git reset --hard "$REMOTE/$RELEASE_BRANCH"

if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' app deploy scripts tests; then
    fail "Git conflict markers found in release files"
fi

log "Installing pinned dependencies"
"$VENV_PYTHON" -m pip install --disable-pip-version-check -q -r requirements.txt

log "Running local production preflight"
"$VENV_PYTHON" -m compileall -q app scripts
"$VENV_PYTHON" scripts/production_preflight.py --telegram

log "Installing systemd reliability guards"
SSHELPER_SKIP_RESTART=1 sudo -E bash deploy/scripts/install-production-guards.sh

log "Starting $SERVICE_NAME"
sudo systemctl reset-failed "$SERVICE_NAME" || true
service_started_at="$(date --iso-8601=seconds)"
sudo systemctl restart "$SERVICE_NAME"

for _ in {1..15}; do
    if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        sleep 3
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            break
        fi
    fi
    sleep 2
done

if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl --no-pager -l status "$SERVICE_NAME" || true
    sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager -l || true
    fail "$SERVICE_NAME did not become active"
fi

sleep 8
if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl --no-pager -l status "$SERVICE_NAME" || true
    sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager -l || true
    fail "$SERVICE_NAME exited after startup"
fi

polling_ready=false
for _ in {1..30}; do
    if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        break
    fi
    # Consume the journal fully: grep -q can trigger SIGPIPE under pipefail.
    if sudo journalctl -u "$SERVICE_NAME" --since "$service_started_at" --no-pager \
        | grep -F "Starting Telegram polling" >/dev/null; then
        polling_ready=true
        break
    fi
    sleep 2
done

if [[ "$polling_ready" != true ]]; then
    sudo systemctl --no-pager -l status "$SERVICE_NAME" || true
    sudo journalctl -u "$SERVICE_NAME" -n 100 --no-pager -l || true
    fail "Telegram polling readiness message was not observed"
fi

log "Deployment successful"
git --no-pager log -1 --oneline
sudo systemctl --no-pager -l status "$SERVICE_NAME" | sed -n '1,15p'
sudo journalctl -u "$SERVICE_NAME" -n 30 --no-pager -l
