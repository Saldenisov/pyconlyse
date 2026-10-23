"""Compatibility imports for the unchanged standard 27-bank contract."""
from .standard_banks import (BANKS, INPUTS, COMMANDS, SOFTWARE_STATUSES,
                             SOFTWARE_STATUS_SOURCE, UNAVAILABLE, schemas,
                             standard_packet, validate_standard_packet,
                             packet_age_seconds)
from .telemetry_publisher import StandardTelemetryPublisher
