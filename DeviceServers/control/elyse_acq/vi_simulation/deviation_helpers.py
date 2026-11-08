"""Independent literal oracle for two original Acquisition comparison helpers.

Frame 0 copies IN to OUT. Frame 1 updates only each subcluster's orange
field (position 2). The direct-line Phase HF/Laser flag is wired False.
These are display deviations, not physical overvoltage interlocks.
"""


def compare_line_cluster(cluster: tuple, threshold: float, *, direct: bool) -> tuple:
    """Preserve all other fields, using the supplied DBL values literally."""
    count = 11 if direct else 9
    if type(direct) is not bool or type(cluster) is not tuple or len(cluster) != count:
        raise ValueError("explicit direct/deviated nested cluster shape required")
    if type(threshold) not in (float, int) or any(
        type(channel) is not tuple
        or len(channel) != 11
        or type(channel[5]) not in (float, int)
        or type(channel[6]) not in (float, int)
        for channel in cluster
    ):
        raise ValueError("eleven fields per channel, numeric consigne/lecture required")
    output = []
    for index, channel in enumerate(cluster):
        orange = (
            False if direct and index == 2 else abs(channel[5] - channel[6]) > threshold
        )
        output.append(channel[:2] + (orange,) + channel[3:])
    return tuple(output)
