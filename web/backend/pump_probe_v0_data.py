"""Compatibility entry points for shot-preserving V0/TRANCON readers."""

from pump_probe_v0_dataset import load_payload


def parse_dat_payload(path, payload):
    return load_payload(path, payload)


def parse_zip_payload(path, payload):
    return load_payload(path, payload)


def parse_h5_payload(path, payload):
    return load_payload(path, payload)
