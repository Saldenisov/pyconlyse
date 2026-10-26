"""Explicit operator test permission, distinct from physical qualification."""

SUPERVISED_OPERATIONS = frozenset((
    "modulator.general.start", "modulator.general.stop", "cooling.start",
    "chauffage.start", "chauffage.stop", "prema.start", "prema.stop",
    "focales.start", "focales.stop", "relays_ht.start", "relays_ht.stop",
    "modulator.reset",
))


def supervised_enabled(subject):
    value = (subject.get("operator_supervised_test", False) if isinstance(subject, dict)
             else getattr(subject, "operator_supervised_test", False))
    return value is True


def supervised_allowed(subject, operation):
    return supervised_enabled(subject) and operation in SUPERVISED_OPERATIONS


def controls_permitted(subject, flag, operation):
    verified = subject.get(flag, False) if isinstance(subject, dict) else getattr(subject, flag, False)
    return verified is True or supervised_allowed(subject, operation)
