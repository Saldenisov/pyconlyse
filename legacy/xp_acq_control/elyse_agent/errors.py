class AgentError(Exception):
    """Base error exposed by the command protocol."""

    code = "agent_error"


class ConfigError(AgentError):
    code = "config_error"


class ProtocolError(AgentError):
    code = "protocol_error"


class HardwareWriteBlocked(AgentError):
    code = "hardware_write_blocked"


class CommandError(AgentError):
    code = "command_error"
