import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [("large", 0), ("delayed", 0), ("missing", 1), ("stopped", 1)],
)
def test_polling_readiness(mode, expected_code, tmp_path):
    script = (
        Path(__file__).resolve().parents[1]
        / "deploy/scripts/deploy-production.sh"
    ).read_text()
    readiness = script.split("polling_ready=false", 1)[1].split(
        'log "Deployment successful"', 1
    )[0]
    harness = r"""
set -euo pipefail
SERVICE_NAME=sshelper.service
service_started_at=now
sleep() { :; }
fail() { echo "$*" >&2; exit 1; }
sudo() {
    if [[ "$1" == systemctl ]]; then
        [[ "$MODE" != stopped ]]
        return
    fi
    if [[ "$MODE" == delayed && ! -f "$STATE" ]]; then
        touch "$STATE"
        return 0
    fi
    if [[ "$MODE" == missing ]]; then
        echo "Still starting"
        return 0
    fi
    echo "Starting Telegram polling"
    if [[ "$MODE" == large ]]; then
        for ((i=0; i<10000; i++)); do
            echo "Additional journal output after readiness $i"
        done
    fi
}
polling_ready=false
"""
    result = subprocess.run(
        ["bash", "-c", harness + readiness],
        env={"MODE": mode, "STATE": str(tmp_path / "journal-read"), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected_code, result.stderr
    if expected_code:
        assert "readiness message was not observed" in result.stderr
