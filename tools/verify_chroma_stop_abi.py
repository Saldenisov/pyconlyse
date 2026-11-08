"""Offline corroboration of OFF adapter against the copied, hash-pinned PE.

Reads/disassembles bytes only; never loads a DLL or opens a serial session.
Requires pefile/capstone on the analysis machine, not on XP. This does not
qualify instrument behavior, current port mapping, or hardware OFF timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


EXPECTED_SHA256 = "d581e088f5d4b25796fe2b758fbec21a1ea7f4edb172b2aa7064dd70246677f8"
FUNCTIONS = {
    "chr62000_init": (0xcfb8, 16),
    "chr62000_close": (0xe7ed, 4),
    "chr62000_SetVoltage": (0x12c4c, 12),
    "chr62000_SetCurrent": (0x141b1, 12),
    "chr62000_SetCurrentSlew": (0x14fab, 12),
    "chr62000_SetOutput": (0x1571b, 8),
}


def verify(path):
    import pefile
    import capstone
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Unexpected driver hash")
    pe = pefile.PE(data=raw)
    if pe.FILE_HEADER.Machine != 0x14c:
        raise ValueError("Expected x86 driver")
    symbols = sorted(pe.DIRECTORY_ENTRY_EXPORT.symbols, key=lambda s: s.address)
    by_name = {s.name.decode("ascii"): s for s in symbols if s.name}
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    results = []
    for name, (rva, stack_bytes) in FUNCTIONS.items():
        symbol = by_name[name]
        if symbol.address != rva:
            raise ValueError("Export RVA changed: " + name)
        end = next(s.address for s in symbols if s.address > rva)
        instructions = list(decoder.disasm(pe.get_data(rva, end - rva), pe.OPTIONAL_HEADER.ImageBase + rva))
        returns = [i for i in instructions if i.mnemonic == "ret"]
        if not returns or any(int(i.op_str, 0) != stack_bytes for i in returns):
            raise ValueError("Unexpected stdcall stack cleanup: " + name)
        results.append(dict(export=name, rva=hex(rva), callee_stack_cleanup_bytes=stack_bytes))
    return dict(driver_sha256=digest, architecture="x86", functions=results,
                dll_loaded=False, hardware_access=False, native_hardware_behavior_verified=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dll")
    parser.add_argument("--dependencies", help="Existing local analysis dependency directory")
    args = parser.parse_args()
    if args.dependencies:
        sys.path.insert(0, str(Path(args.dependencies).resolve()))
    print(json.dumps(verify(args.dll), indent=2))
