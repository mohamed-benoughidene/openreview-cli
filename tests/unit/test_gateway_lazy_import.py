import subprocess
import sys


def test_gateway_package_import_does_not_pull_litellm() -> None:
    code = "import openreview_cli.gateway, sys; sys.exit(1 if 'litellm' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
