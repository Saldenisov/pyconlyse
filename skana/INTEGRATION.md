# SK-Ana in Pyconlyse Treatment

The numerical package is the existing `SKAna-Python` branch of
https://github.com/Saldenisov/SK-Ana at commit
`ad7bba876715f052869cd9bacc52e21ca43aa5d4`. The ten upstream Python modules are
copied without numerical changes; `UPSTREAM.json` records their hashes and the
original CeCILL-2.1 license is retained beside this file.

The `SK-Ana` tab is embedded in the standalone TreatmentVD2 application
(`Treatment/main.py`), its legacy Treatment entry, and Web Data Treatment for
the VD2 profile. Each uses `utilities.skana`, which adapts current treatment
measurements to the existing `skana.svd`, `skana.als`, and
`skana.fit_kinetics` functions. No R, Shiny or Streamlit process is started.

## Data and results

Treatment measurements use wavelength × time arrays. The adapter checks both
axis lengths and transposes explicitly to SK-Ana's time × wavelength layout.
It copies data, preserves physical time coordinates and units, and leaves the
treatment measurement and calculated OD unchanged. Unknown time units remain
unknown; reaction fitting requires an explicit unit label without rescaling
numeric coordinates. Signed spectra can be enabled explicitly.

The desktop tab receives actual measurement notifications, including calculated
OD, and never analyzes the initial plotting placeholder. Its numerical calls run
outside the GUI thread; playback notifications are marshalled back to that thread.
The Web tab reads full-resolution calculated OD already held by the treatment
session, or an explicitly imported numeric corner-cell table. It does not open
an acquisition file. Text import follows the existing SK-Ana parser: axes are
sorted and invalid signal cells become zero; the interface displays this warning.

All fits use the selected full-resolution matrix. Web heatmaps are sampled only
for display, with the sampling flag and matching selected coordinates retained.
JSON and CSV ZIP downloads contain full-resolution selected data, fitted profiles,
model, residuals, units and diagnostics. Residuals are data minus model.

Web jobs are session-scoped and serialized because the existing LSODA routine is
not reentrant. Matching jobs/results can be restored after leaving and reopening
the tab. Results and imported matrices are held in bounded server memory; export
them to retain them across a Web restart. Completed results expire after one hour
and are limited to two retained results per session, with six jobs globally.

The upstream numerical functions do not provide interruption callbacks.
Cancellation therefore requests result discard and retains the worker until the
existing call returns. Closing the desktop window waits asynchronously for that
ownership to finish. A nonconverged result remains explicitly nonconverged.

## Dependencies and scope

The integration uses the existing NumPy, SciPy, pandas, scikit-learn, matplotlib
and Qt dependencies. The upstream package also requires `rdata`, even when only
numeric matrices are used. The integration dependency list is
`requirements-integration.txt`; for a new environment, install it with:

```powershell
python -m pip install -r skana/requirements-integration.txt
```

The tabs expose SVD, constrained MCR-ALS and the existing reaction-scheme MAP
fitter. Advanced desktop options forward supported upstream parameters rather
than implementing another solver. The original Streamlit-specific project and
report UI is not embedded. No separate DAS algorithm has been added.

Upstream differences from R, including broadening, optimizer behavior and the
single-free-spectrum kinetic branch, remain upstream behavior. The adapter does
not establish physical species identification or complete numerical equivalence
to the R application. Validation uses synthetic matrices and direct calls to the
unchanged Python package, not operational acquisition data.
