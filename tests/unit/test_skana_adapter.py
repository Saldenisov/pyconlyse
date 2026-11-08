"""Adapter checks against the existing upstream Python solver, not a new port."""

from functools import wraps
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import skana

from utilities.skana import AnalysisCancelled, Dataset, UPSTREAM_COMMIT, analyze, from_measurement


def test_existing_one_free_signed_kinetic_spectrum_limitation_is_explicit():
    times = np.linspace(0, 3, 8)
    wavelengths = np.array([400., 500., 600.])
    data = Dataset(np.exp(-times[:, None]) * np.array([[1., 0.5, 0.2]]), times, wavelengths, time_unit='ns')
    result = analyze(data, 'target', {'scheme': 'A -> 0 ; 1\nc0_A_1 = 1\neps_A = 1', 'nonnegative_s': False})
    assert len(result['warnings']) == 1
    assert 'one free active kinetic spectrum' in result['warnings'][0]
    assert result['diagnostics']['warnings'] == result['warnings']


def dataset(unit='ns'):
    times = np.linspace(0.0, 4.0, 16)
    wavelengths = np.linspace(420.0, 680.0, 19)
    c = np.column_stack((np.exp(-times), 1 - np.exp(-0.4 * times)))
    s = np.column_stack((np.exp(-((wavelengths - 470) / 30) ** 2),
                         np.exp(-((wavelengths - 610) / 35) ** 2)))
    return Dataset(c @ s.T, times, wavelengths, time_unit=unit, source='synthetic OD')


def test_vendored_upstream_modules_match_recorded_source_hashes():
    root = Path(__file__).resolve().parents[2]
    provenance = json.loads((root / 'skana/UPSTREAM.json').read_text(encoding='utf-8'))
    assert provenance['commit'] == UPSTREAM_COMMIT
    assert provenance['branch'] == 'SKAna-Python'
    assert provenance['license'] == 'CeCILL-2.1'
    assert len(provenance['sha256']) == 10
    for relative, expected in provenance['sha256'].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected


def test_measurement_snapshot_transposes_explicit_layout_and_freezes_copies():
    original = np.arange(12.0).reshape(3, 4)
    measurement = SimpleNamespace(data=original, wavelengths=np.array([450., 550., 650.]),
                                  timedelays=np.array([0., 1., 2., 3.]), time_scale='??')
    result = from_measurement(measurement, source='selected map')
    assert result.matrix.shape == (4, 3)
    np.testing.assert_array_equal(result.matrix, original.T)
    assert result.time_unit == '??'
    assert result.signal_unit == 'a.u.'
    original[0, 0] = 900
    assert result.matrix[0, 0] == 0
    assert not result.matrix.flags.writeable
    assert not result.times.flags.writeable
    assert not result.wavelengths.flags.writeable
    with pytest.raises(ValueError):
        result.matrix[0, 0] = 5


def test_square_measurements_are_transposed_without_orientation_guessing():
    matrix = np.array([[1., 2.], [3., 4.]])
    measurement = SimpleNamespace(data=matrix, wavelengths=[450., 650.], timedelays=[1., 2.], time_scale='ps')
    result = from_measurement(measurement)
    np.testing.assert_array_equal(result.matrix, [[1, 3], [2, 4]])


def test_mismatched_measurement_axes_rejected_instead_of_auto_transposing():
    measurement = SimpleNamespace(data=np.ones((4, 3)), wavelengths=[450., 550., 650.],
                                  timedelays=[0., 1., 2., 3.], time_scale='ns')
    with pytest.raises(ValueError, match='wavelength'):
        from_measurement(measurement)


@pytest.mark.parametrize('bad', [np.full((2, 2), np.nan), np.full((2, 2), np.inf),
                                np.ones((2, 2), dtype=complex), [['x', 'y'], ['z', 'q']]])
def test_invalid_values_are_not_replaced_by_zeros(bad):
    with pytest.raises(ValueError):
        Dataset(bad, [0., 1.], [400., 500.])


def test_svd_adapter_is_identical_to_existing_python_svd_and_preserves_units():
    source = dataset('??')
    before = source.matrix.copy()
    expected = skana.svd(source.to_upstream(), rank=2, max_rank=5)
    actual = analyze(source, 'svd', {'rank': 2, 'max_rank': 5})
    np.testing.assert_allclose(actual['reconstruction'], expected.model)
    np.testing.assert_allclose(actual['residuals'], expected.residual)
    np.testing.assert_allclose(actual['singular_values'], expected.singular_values)
    np.testing.assert_allclose(np.array(actual['concentrations']) @ np.array(actual['spectra']).T, expected.model)
    np.testing.assert_array_equal(source.matrix, before)
    assert actual['statistics'] == expected.statistics.to_dict('records')
    assert actual['time_unit'] == '??'
    assert actual['iterations'] == 1
    assert actual['diagnostics']['upstream_commit'] == UPSTREAM_COMMIT
    assert actual['diagnostics']['time_conversion_applied'] is False
    json.dumps(actual, allow_nan=False)


def test_mcr_adapter_forwards_existing_options_without_reimplementing_solver():
    source = dataset()
    options = dict(n_components=2, init_method='svd', maxiter=20, thresh=1e-7,
                   nonneg_c=True, nonneg_s=[True, False], norm_s=True, norm_mode='l1')
    expected = skana.als(source.to_upstream(), **options)
    actual = analyze(source, 'mcr_als', options)
    np.testing.assert_allclose(actual['concentrations'], expected.c)
    np.testing.assert_allclose(actual['spectra'], expected.s)
    np.testing.assert_allclose(actual['reconstruction'], expected.model)
    np.testing.assert_allclose(actual['residuals'], expected.resid)
    assert actual['iterations'] == expected.iter
    assert actual['converged'] == expected.converged
    assert actual['lof_percent'] == expected.lof
    assert options['nonneg_s'] == [True, False]
    json.dumps(actual, allow_nan=False)


def test_broadening_uses_existing_upstream_model_not_simple_c_times_s():
    source = dataset()
    options = dict(n_components=2, maxiter=3, broadening=[True, False])
    expected = skana.als(source.to_upstream(), **options)
    actual = analyze(source, 'mcr_als', options)
    np.testing.assert_allclose(actual['reconstruction'], expected.model)
    np.testing.assert_allclose(actual['broadening'], expected.g)
    assert actual['broadening_components'] == expected.broadening_vec.tolist()


def test_ui_aliases_are_explicit_and_ambiguous_options_rejected():
    source = dataset()
    aliases = dict(n_components=2, max_iterations=8, tolerance=1e-6,
                   nonnegative_concentrations=True, nonnegative_spectra=False,
                   initialization='svd', normalize_spectra='max')
    direct = dict(n_components=2, maxiter=8, thresh=1e-6, nonneg_c=True,
                  nonneg_s=False, init_method='svd', norm_s=True, norm_mode='intensity')
    np.testing.assert_allclose(analyze(source, 'mcr_als', aliases)['reconstruction'],
                               analyze(source, 'mcr_als', direct)['reconstruction'])
    with pytest.raises(ValueError, match='only one'):
        analyze(source, 'mcr_als', dict(maxiter=10, max_iterations=10))


def test_masks_use_existing_select_and_preserve_physical_time_coordinates():
    source = dataset('ps')
    options = dict(rank=2, delay_range=[source.times[2], source.times[-3]],
                   wavelength_range=[source.wavelengths[2], source.wavelengths[-3]])
    actual = analyze(source, 'svd', options)
    expected = skana.select(source.to_upstream(), delay_range=options['delay_range'],
                            wavelength_range=options['wavelength_range'])
    np.testing.assert_array_equal(actual['times'], expected.time)
    np.testing.assert_array_equal(actual['wavelengths'], expected.wavelength)
    np.testing.assert_array_equal(actual['data'], expected.matrix)
    np.testing.assert_allclose(actual['reconstruction'], skana.svd(expected, rank=2).model)
    assert actual['input_shape'] == list(expected.matrix.shape)
    assert actual['original_shape'] == list(source.matrix.shape)


SCHEME = 'A -> B ; 0.7\nc0_A_1 = 1\neps_A = 1\neps_B = 0.8\n'


def target_data():
    times = np.linspace(0.0, 3.0, 16)
    wavelengths = np.linspace(400., 680., 19)
    scheme = skana.parse_scheme(SCHEME)
    blank = skana.MatrixData(np.zeros((times.size, wavelengths.size)), times, wavelengths)
    c = skana.concentrations(blank, scheme)
    s = np.column_stack((np.exp(-((wavelengths - 470) / 30) ** 2),
                         0.8 * np.exp(-((wavelengths - 610) / 35) ** 2)))
    s[:, 0] /= s[:, 0].max()
    s[:, 1] *= 0.8 / s[:, 1].max()
    return Dataset(c @ s.T, times, wavelengths, time_unit='ns'), scheme


def test_target_adapter_matches_existing_map_and_does_not_fabricate_iterations():
    source, scheme = target_data()
    expected = skana.fit_kinetics(source.to_upstream(), scheme, nonnegative_s=True, weighted=True, sigma=0.01)
    actual = analyze(source, 'target', dict(scheme=SCHEME, nonnegative_s=True, weighted=True, sigma=0.01))
    np.testing.assert_allclose(actual['reconstruction'], expected.model)
    np.testing.assert_allclose(actual['residuals'], expected.residual)
    np.testing.assert_allclose(actual['concentrations'], expected.c)
    assert actual['parameters'] == expected.parameters
    assert actual['converged'] == expected.success
    assert actual['iterations'] is None
    assert actual['diagnostics']['message'] == expected.message
    assert actual['diagnostics']['parameter_time_basis'] == 'ns'
    assert actual['diagnostics']['covariance_basis'] == 'normalized log-parameter z space'
    json.dumps(actual, allow_nan=False)


def test_unknown_target_units_require_explicit_label_without_rescaling_numbers():
    source, _ = target_data()
    unknown = Dataset(source.matrix, source.times, source.wavelengths, time_unit='??')
    with pytest.raises(ValueError, match='known time_unit'):
        analyze(unknown, 'target', dict(scheme=SCHEME))
    actual = analyze(unknown, 'target', dict(scheme=SCHEME, time_unit='ns'))
    assert actual['time_unit'] == 'ns'
    np.testing.assert_array_equal(actual['times'], unknown.times)
    assert unknown.time_unit == '??'


def test_cancel_after_upstream_call_discards_result_without_changing_solver(monkeypatch):
    original = skana.svd
    stopped = [False]

    @wraps(original)
    def already_running(*args, **kwargs):
        result = original(*args, **kwargs)
        stopped[0] = True
        return result

    monkeypatch.setattr(skana, 'svd', already_running)
    with pytest.raises(AnalysisCancelled):
        analyze(dataset(), cancel=lambda: stopped[0])
    with pytest.raises(AnalysisCancelled):
        analyze(dataset(), cancel=lambda: True)


def test_target_jobs_serialize_existing_nonreentrant_lsoda_solver(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    import time
    original = skana.fit_kinetics
    counters = dict(active=0, maximum=0)
    lock = Lock()

    @wraps(original)
    def observe_overlap(*args, **kwargs):
        with lock:
            counters['active'] += 1
            counters['maximum'] = max(counters['maximum'], counters['active'])
        try:
            time.sleep(0.03)  # Make a missing wrapper lock observable.
            return original(*args, **kwargs)
        finally:
            with lock:
                counters['active'] -= 1

    monkeypatch.setattr(skana, 'fit_kinetics', observe_overlap)
    source, _ = target_data()
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(analyze, source, 'target', {'scheme': SCHEME}) for _ in range(2)]
        for future in futures:
            assert future.result(timeout=5)['converged']
    assert counters['maximum'] == 1


@pytest.mark.parametrize('method,options', [('das', {}), ('svd', {'rank': True}),
    ('svd', {'rank': 1.5}), ('svd', {'centering': True}), ('mcr_als', {'maxiter': 100000}),
    ('mcr_als', {'nonneg_s': [True, 1]}), ('mcr_als', {'init_method': 'invented'}),
    ('target', {'scheme': SCHEME, 'local_iterations': 10}),
    ('target', {'scheme': SCHEME, 'global_generations': -1}),
    ('target', {'scheme': SCHEME, 'start': [np.nan]}),
    ('target', {'scheme': SCHEME, 'sigma': 0}),
    ('target', {'scheme': SCHEME, 'fixed_spectra': {'UNKNOWN': [1, 2]}})])
def test_unavailable_features_and_invalid_solver_parameters_are_explicit(method, options):
    with pytest.raises(ValueError):
        analyze(dataset(), method, options)


def test_all_zero_input_does_not_become_fake_successful_signal_analysis():
    zero = Dataset(np.zeros((3, 4)), np.arange(3.), np.arange(4.))
    with pytest.raises(ValueError, match='nonzero signal'):
        analyze(zero)
