"""SK-Ana's independent Python application API."""

from .analysis import SVDResult, als, als_contributions, svd
from .ambiguity import Rotation, Rotation3, rotate_three, rotate_two
from .matrix import (MatrixData, baseline_correct, combine, compress, postprocess_compress, export_matrix,
                     read_matrix, select, suggest_baseline_intervals,
                     suggest_signal_mask)
from .kinetics import (KineticResult, Reaction, Scheme, concentrations, fit_kinetics,
                       format_scheme, parse_scheme, solve_spectra, stoichiometry,
                       variable_parameters)
from .r_project import read_r_project, read_r_selection
from .report import build_report

__all__ = [
    "MatrixData", "Rotation", "Rotation3", "SVDResult", "als", "als_contributions", "baseline_correct", "combine", "compress", "postprocess_compress",
    "export_matrix", "read_matrix", "rotate_three", "rotate_two", "select", "svd",
    "KineticResult", "Reaction", "Scheme", "concentrations", "fit_kinetics",
    "format_scheme", "parse_scheme", "solve_spectra", "stoichiometry",
    "variable_parameters",
    "read_r_project",
    "read_r_selection",
    "build_report",
    "suggest_signal_mask",
    "suggest_baseline_intervals",
]
