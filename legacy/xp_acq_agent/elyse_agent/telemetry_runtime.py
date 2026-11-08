"""Optional outbound relay configuration; no listener or hardware startup."""
import json
import os

from .supervision_wire import validate_key
from .telemetry_relay import TelemetryRelay


def load_relay(root_path, outbox):
    config_path = os.path.join(root_path, 'config.telemetry-relay.json')
    if not os.path.isfile(config_path):
        return None
    with open(config_path, 'r') as source:
        config = json.load(source)
    if type(config) is not dict or set(config) != set(('enabled', 'everest_host', 'everest_port', 'key_file')):
        raise ValueError('invalid relay configuration fields')
    if config['enabled'] is False:
        return None
    if config['enabled'] is not True:
        raise ValueError('relay enabled must be Boolean')
    if config['everest_host'] != '10.20.30.202' or config['everest_port'] != 8767 or type(config['everest_port']) is not int:
        raise ValueError('relay destination must be verified Everest 10.20.30.202:8767')
    if not isinstance(config['key_file'], str) or not config['key_file']:
        raise ValueError('relay requires an explicit key file')
    key_path = config['key_file']
    if not os.path.isabs(key_path):
        key_path = os.path.join(root_path, key_path)
    with open(key_path, 'rb') as source:
        key = validate_key(source.read().strip())
    return TelemetryRelay(outbox, (config['everest_host'], config['everest_port']), key)
