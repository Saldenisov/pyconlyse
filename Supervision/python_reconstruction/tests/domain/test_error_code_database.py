import unittest

from supervision_reconstruction.domain.error_code_database import (
    ERROR_CODE_DATABASE_BLOCKED,
    ErrorCodeDatabaseUnavailable,
    lookup_error_code,
)


class ErrorCodeDatabaseBoundaryTests(unittest.TestCase):
    def test_password_protected_lookup_always_fails_closed(self) -> None:
        self.assertFalse(ERROR_CODE_DATABASE_BLOCKED.implementation_allowed)
        self.assertIn("block diagram", ERROR_CODE_DATABASE_BLOCKED.missing_evidence)
        with self.assertRaises(ErrorCodeDatabaseUnavailable):
            lookup_error_code(5, source="test")


if __name__ == "__main__":
    unittest.main()
