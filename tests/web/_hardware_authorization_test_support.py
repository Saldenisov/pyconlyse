"""Shared service-ACL simulation for hardware-authorization web tests.

The contract is about the web-service identity, not the permissions of the
interactive user running pytest.  Simulate that identity explicitly so tests
remain valid on Windows, where chmod does not express the service ACL.
"""

from pathlib import Path


def simulate_hardware_authorization_service_acl(
    monkeypatch, *, policy_path, approval_dir, consumed_dir
):
    """Make policy and approvals readonly to the service, but consumed writable."""
    import hardware_authorization

    policy_path = Path(policy_path).resolve()
    policy_parent = policy_path.parent
    approval_dir = Path(approval_dir).resolve()
    consumed_dir = Path(consumed_dir).resolve()
    actual_access = hardware_authorization.os.access

    def web_service_access(path, mode):
        if mode != hardware_authorization.os.W_OK:
            return actual_access(path, mode)
        try:
            candidate = Path(path).resolve()
        except OSError:
            return False
        if candidate == consumed_dir:
            return True
        if candidate in {policy_path, policy_parent, approval_dir}:
            return False
        if candidate.parent == approval_dir:
            return False
        return actual_access(path, mode)

    monkeypatch.setattr(hardware_authorization.os, "access", web_service_access)
