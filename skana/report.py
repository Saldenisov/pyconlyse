"""Self-contained HTML analysis report without an R or Pandoc runtime."""

from __future__ import annotations

import base64
from html import escape
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np

from .matrix import MatrixData
from .plots import ambiguity_ensemble, diagnostics, image, profiles
from .kinetics import parse_scheme, variable_parameters


def _figure(fig) -> str:
    buffer = BytesIO()
    try:
        fig.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    finally:
        plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f'<img src="data:image/png;base64,{encoded}" alt="Analysis plot">'


def build_report(data: MatrixData, *, svd_result=None, als_result=None,
                 kinetic_result=None, scheme_text: str | None = None,
                 ambiguity_solutions=None) -> bytes:
    """Render selected matrix and available analyses as portable HTML bytes."""
    sections = [
        "<!doctype html><html lang='en'><meta charset='utf-8'>",
        "<title>SK-Ana Python report</title>",
        "<style>body{font:16px system-ui,sans-serif;max-width:1050px;margin:2rem auto;"
        "padding:0 1rem;color:#142032}h1,h2{color:#173b58}"
        "img{max-width:100%;height:auto}table{border-collapse:collapse}"
        "td,th{border:1px solid #bbb;padding:.35rem .6rem;text-align:right}"
        "section{margin:2rem 0;page-break-inside:avoid}</style><body>",
        f"<h1>SK-Ana Python: {escape(data.name)}</h1>",
        f"<p>{data.matrix.shape[0]} delays × {data.matrix.shape[1]} wavelengths; "
        f"delay {data.delay.min():.6g}–{data.delay.max():.6g}; "
        f"wavelength {data.wavelength.min():.6g}–{data.wavelength.max():.6g}.</p>",
        "<section><h2>Selected data</h2>", _figure(image(data, data.matrix, "Selected data")), "</section>",
    ]
    if svd_result is not None:
        sections.extend(["<section><h2>Singular value decomposition</h2>",
                         svd_result.statistics.to_html(index=False, float_format=lambda x: f"{x:.6g}"),
                         _figure(profiles(data, svd_result.u[:, :svd_result.rank],
                                          svd_result.vt[:svd_result.rank].T, "SVD")),
                         _figure(diagnostics(data, svd_result.model, svd_result.residual, "SVD")),
                         "</section>"])
    if ambiguity_solutions:
        sections.extend(["<section><h2>Rotational ambiguity</h2>",
                         f"<p>{len(ambiguity_solutions)} accepted rotations.</p>",
                         _figure(ambiguity_ensemble(data, ambiguity_solutions)),
                         "</section>"])
    for label, result in (("MCR-ALS", als_result), ("Kinetic model", kinetic_result)):
        if result is None:
            continue
        residual = result.resid if label == "MCR-ALS" else result.residual
        sections.extend([f"<section><h2>{label}</h2>",
                         f"<p>LOF {result.lof:.6g}%; relative RSS {result.rss:.6g}.</p>",
                         _figure(profiles(data, result.c, result.s, label)),
                         _figure(diagnostics(data, result.model, residual, label))])
        if label == "Kinetic model":
            if scheme_text:
                sections.extend(["<h3>Chemical scheme</h3>",
                                 f"<pre>{escape(scheme_text)}</pre>"])
            rows = "".join(f"<tr><th>{escape(name)}</th><td>{value:.8g}</td></tr>"
                           for name, value in result.parameters.items())
            sections.append(f"<h3>Fitted parameters</h3><table>{rows}</table>")
            fig, ax = plt.subplots(figsize=(7, 3))
            for j in range(result.c_all.shape[1]):
                ax.plot(data.time, result.c_all[:, j], label=f"Species {j + 1}")
            ax.set(xlabel="Physical time", ylabel="Concentration", title="Integrated kinetics")
            ax.legend()
            sections.extend(["<h3>Integrated kinetics</h3>", _figure(fig)])
            if svd_result is not None:
                sections.append(f"<p>Kinetic LOF: {result.lof:.6g}%; "
                                f"SVD rank {svd_result.rank} LOF: "
                                f"{svd_result.statistics.loc[svd_result.rank - 1, 'lof_pct']:.6g}%.</p>")
            if scheme_text and result.covariance is not None:
                scheme = parse_scheme(scheme_text, n_experiments=len(set(data.delay_id)))
                variable = variable_parameters(scheme)
                if len(variable) == len(result.contracted):
                    fig, ax = plt.subplots(figsize=(7, 3))
                    zgrid = np.linspace(-3, 3, 241)
                    ax.plot(zgrid, np.exp(-0.5 * zgrid**2), "k--", label="Prior")
                    for j, parameter in enumerate(variable):
                        sd = np.sqrt(max(result.covariance[j, j], 1e-30))
                        ax.plot(zgrid, np.exp(-0.5 * ((zgrid - result.contracted[j]) / sd)**2),
                                label=parameter.name)
                    ax.set(xlabel="Contracted parameter z", ylabel="Relative density",
                           title="Local posterior approximation")
                    ax.legend()
                    sections.extend(["<h3>Parameter densities</h3>", _figure(fig)])
        sections.append("</section>")
    sections.append("</body></html>")
    return "\n".join(sections).encode("utf-8")
