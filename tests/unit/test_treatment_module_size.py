from pathlib import Path

def test_treatment_modules_fit_within_900_lines():
    backend = Path(__file__).resolve().parents[2] / "web" / "backend"
    too_long = {}
    for module in backend.glob("treatment_*.py"):
        line_count = len(module.read_text(encoding="utf-8").splitlines())
        if line_count > 900:
            too_long[module.name] = line_count
    assert not too_long, f"Treatment modules over 900 lines: {too_long}"
