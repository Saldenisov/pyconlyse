"""Portable proof-bundle refusals; never load LabVIEW, NI, or live telemetry."""

import ast
import hashlib
import io
import json
import os
import shutil
import struct
import tempfile
import unittest

from tools import verify_supervision_observer_bundle as verifier


def read(path):
    with open(path, "rb") as stream:
        return stream.read()


class ObserverProofBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="observer-proof-")
        self.root = os.path.join(self.temp.name, "bundle")
        shutil.copytree(verifier.DEFAULT_BUNDLE, self.root)
        self.vi = os.path.join(self.root, "SUP_Camera_Observe_U8_UNCOMPILED.vi")

    def tearDown(self):
        self.temp.cleanup()

    def test_reviewed_pair_has_native12_flags_but_no_runtime_claim(self):
        result = verifier.verify_bundle(self.root)
        self.assertEqual(result["status"], "NOT_RUNTIME_QUALIFIED")
        self.assertEqual(set(result["files"]), set(verifier.PINS))
        self.assertFalse(result["vi_loaded"])
        self.assertFalse(result["vi_executed"])
        self.assertFalse(result["native2012_open_save_verified"])

    def test_changed_vi_bytes_and_forged_manifest_hash_both_refuse(self):
        raw = bytearray(read(self.vi))
        raw[40] ^= 1
        with open(self.vi, "wb") as stream:
            stream.write(raw)
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)
        path = os.path.join(self.root, "manifest.json")
        with io.open(path, encoding="utf-8") as stream:
            manifest = json.load(stream)
        manifest["files"]["SUP_Camera_Observe_U8_UNCOMPILED.vi"]["sha256"] = "0" * 64
        with io.open(path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest))
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_runtime_promotion_and_unreviewed_dependency_refuse(self):
        path = os.path.join(self.root, "manifest.json")
        with io.open(path, encoding="utf-8") as stream:
            manifest = json.load(stream)
        manifest["native2012_open_save_verified"] = True
        with io.open(path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest))
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)
        manifest["native2012_open_save_verified"] = False
        with io.open(path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest))
        with open(os.path.join(self.root, "Basics.llb"), "wb") as stream:
            stream.write(b"unreviewed dependency")
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_binary_parser_refuses_run_on_open_and_wrong_version_independently(self):
        raw = bytearray(read(self.vi))
        offset, length = verifier._resource_sections(raw)[(b"LVSR", 0)]
        execution = struct.unpack_from(">I", raw, offset + 4)[0]
        struct.pack_into(">I", raw, offset + 4, execution | (1 << 14))
        self.assertRaises(verifier.BundleError, verifier.inspect_vi_rsrc, raw)
        struct.pack_into(">I", raw, offset + 4, execution)
        struct.pack_into(">I", raw, offset, 0x20008000)
        self.assertRaises(verifier.BundleError, verifier.inspect_vi_rsrc, raw)

    def test_truncation_region_overflow_and_missing_helper_refuse(self):
        raw = bytearray(read(self.vi))
        self.assertRaises(verifier.BundleError, verifier.inspect_vi_rsrc, raw[:64])
        struct.pack_into(">I", raw, 16, 0xFFFFFFFF)
        self.assertRaises(verifier.BundleError, verifier.inspect_vi_rsrc, raw)
        os.remove(os.path.join(self.root, "observer_v3", "SUP_Camera_Queue_Latest.vi"))
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_proof_tamper_and_duplicate_json_key_refuse(self):
        path = os.path.join(self.root, "proof.json")
        with open(path, "ab") as stream:
            stream.write(b" ")
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)
        path = os.path.join(self.root, "manifest.json")
        with open(path, "wb") as stream:
            stream.write(b'{"schema_version":1,"schema_version":1}')
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_rewritten_manifest_cannot_authorize_changed_proof(self):
        path = os.path.join(self.root, "proof.json")
        changed = read(path) + b" "
        with open(path, "wb") as stream:
            stream.write(changed)
        manifest_path = os.path.join(self.root, "manifest.json")
        with io.open(manifest_path, encoding="utf-8") as stream:
            manifest = json.load(stream)
        manifest["proof_sha256"] = hashlib.sha256(changed).hexdigest()
        with io.open(manifest_path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest))
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_registered_subpacket_manifest_tamper_refuses(self):
        path = os.path.join(self.root, "individual_helpers", "package_manifest.json")
        with open(path, "ab") as stream:
            stream.write(b" ")
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_registered_subpacket_rejects_unlisted_non_VI_files(self):
        for relative in ("extra.exe", "extra.py", "camera/extra.lvlps"):
            path = os.path.join(self.root, "individual_helpers", *relative.split("/"))
            with open(path, "wb") as stream:
                stream.write(b"unexpected test payload; never executed")
            self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)
            os.remove(path)

    def test_subpacket_registration_is_explicit_and_validates_nested_helpers(self):
        path = os.path.join(self.root, "manifest.json")
        with io.open(path, encoding="utf-8") as stream:
            manifest = json.load(stream)
        original = manifest["registered_subpackets"]
        manifest["registered_subpackets"] = []
        with io.open(path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest))
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)
        manifest["registered_subpackets"] = original
        with io.open(path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest))
        os.remove(
            os.path.join(
                self.root, "individual_helpers", "camera", "SUP_Camera_FrameTap.vi"
            )
        )
        self.assertRaises(verifier.BundleError, verifier.verify_bundle, self.root)

    def test_verifier_keeps_python34_grammar(self):
        with io.open(verifier.__file__, encoding="utf-8") as stream:
            source = stream.read()
        try:
            ast.parse(source, feature_version=(3, 4))
        except TypeError:
            ast.parse(source)  # actual Python3.4 has no feature_version argument


if __name__ == "__main__":
    unittest.main()
