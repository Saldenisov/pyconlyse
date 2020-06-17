from dataclasses import dataclass


# General dataclass
@dataclass(frozen=True, order=True)
class DataClass_frozen:
    pass


@dataclass(order=True, frozen=False)
class DataClass_unfrozen:
    pass
