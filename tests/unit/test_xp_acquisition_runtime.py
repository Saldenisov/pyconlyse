"""Collect the Python-3.4-compatible suite under the deny-network test lane."""
from legacy.xp_acq_agent.tests.test_acquisition_runtime import (
    BackendTests as BackendTests, HttpTests as HttpTests, RuntimeTests as RuntimeTests, StartupTests as StartupTests,
)
