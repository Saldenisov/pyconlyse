"""Pure command-setpoint display copies, not a measured output or hardware write."""

# Destination device position, source bank, source field. Each device cell
# has Consigne at field5; source bank inputs are separate local-read snapshots.
DIRECT = (
    (3, 9, 0),
    (4, 9, 1),
    (5, 9, 2),
    (6, 9, 3),
    (9, 9, 4),
    (10, 9, 5),
    (0, 10, 8),
    (1, 10, 5),
    (7, 10, 0),
    (8, 10, 1),
    (2, 11, 5),
)
DEVIATED = (
    (4, 9, 6),
    (5, 9, 7),
    (8, 9, 9),
    (7, 9, 8),
    (6, 10, 9),
    (0, 10, 6),
    (1, 10, 7),
    (2, 10, 3),
    (3, 10, 4),
)


def _copy(cells, size, banks, mapping):
    types = (bool,) * 5 + (float,) * 2 + (bool,) * 4
    if (
        type(cells) is not tuple
        or len(cells) != size
        or any(
            type(cell) is not tuple
            or len(cell) != 11
            or any(type(value) is not expected for value, expected in zip(cell, types))
            for cell in cells
        )
    ):
        raise TypeError("explicit complete nested device-cell snapshot required")
    expected = {bank for _, bank, _ in mapping}
    if set(banks) != expected or any(
        type(values) is not tuple
        or len(values) != 10
        or any(type(value) is not float for value in values)
        for values in banks.values()
    ):
        raise TypeError(
            "explicit separate full-size DBL command-bank snapshots required"
        )
    result = [list(cell) for cell in cells]
    for destination, bank, source in mapping:
        result[destination][5] = banks[bank][source]
    return tuple(tuple(cell) for cell in result)


def direct_display(cells, *, bank9, bank10, bank11):
    return _copy(cells, 11, {9: bank9, 10: bank10, 11: bank11}, DIRECT)


def deviated_display(cells, *, bank9, bank10):
    return _copy(cells, 9, {9: bank9, 10: bank10}, DEVIATED)
