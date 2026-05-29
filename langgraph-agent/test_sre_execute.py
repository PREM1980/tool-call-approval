import subprocess
from unittest.mock import MagicMock, patch

import pytest

from sre.orchestrate.tools.execute import _check_safe, execute_command


def test_check_safe_blocks_delete():
    with pytest.raises(ValueError, match="delete"):
        _check_safe("kubectl delete pod payments-api")


def test_check_safe_blocks_force():
    with pytest.raises(ValueError):
        _check_safe("kubectl get pods --force")


def test_check_safe_blocks_terminate():
    with pytest.raises(ValueError, match="terminate"):
        _check_safe("aws ec2 terminate-instances --instance-ids i-123")


def test_check_safe_blocks_rm():
    with pytest.raises(ValueError, match="rm"):
        _check_safe("aws s3 rm s3://bucket/key")


def test_check_safe_allows_get():
    _check_safe("kubectl get pods -n default")


def test_check_safe_allows_describe():
    _check_safe("kubectl describe pod payments-api -n payments")


def test_check_safe_allows_aws_describe():
    _check_safe("aws ec2 describe-instances --instance-ids i-123")


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_returns_stdout(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="NAME   STATUS\npod-1  Running", stderr="")
    result = execute_command.invoke({"command": "kubectl get pods -n default"})
    assert result == "NAME   STATUS\npod-1  Running"


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_returns_stderr_on_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error from server: not found")
    result = execute_command.invoke({"command": "kubectl get pods -n missing"})
    assert result == "Error from server: not found"


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="kubectl", timeout=30)
    result = execute_command.invoke({"command": "kubectl get pods -n default"})
    assert result == "Command timed out after 30 seconds"


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_not_found(mock_run):
    err = FileNotFoundError()
    err.filename = "kubectl"
    mock_run.side_effect = err
    result = execute_command.invoke({"command": "kubectl get pods"})
    assert result == "Command not available: kubectl"


def test_execute_command_blocks_destructive():
    with pytest.raises(ValueError):
        execute_command.invoke({"command": "kubectl delete namespace production"})
