"""Emulate native LabVIEW's project-FILE URL base; no LabVIEW or file I/O."""

import ntpath
import posixpath
import unittest
import xml.etree.ElementTree as ET

from tools.labview_project_paths import project_item_url


class LabVIEWProjectPathTests(unittest.TestCase):
    def assert_native_resolves(self, project, target, expected_url):
        url = project_item_url(project, target)
        self.assertEqual(url, expected_url)
        # Intentionally join to the FILE, not dirname(project). This emulates
        # native behavior independently of the URL generation implementation.
        native = ntpath.normcase(ntpath.normpath(ntpath.join(project, url)))
        self.assertEqual(native, ntpath.normcase(ntpath.normpath(target)))

    def test_same_directory_uses_parent_marker(self):
        self.assert_native_resolves(
            r"C:\helpers\project.lvproj", r"C:\helpers\tap.vi", "../tap.vi"
        )

    def test_real_export_project_sibling_layout_requires_two_parents(self):
        root = r"C:\dev\sup_vi_camera_20261027\individual_helpers_20261028"
        project = root + r"\export2012_preparation\SUP_Sync_Export_Native_2020.lvproj"
        target = root + r"\sync_lifecycle\counter_only_candidate\SUP_SyncTap.vi"
        self.assert_native_resolves(
            project, target,
            "../../sync_lifecycle/counter_only_candidate/SUP_SyncTap.vi",
        )
        previous_bug = ntpath.relpath(target, ntpath.dirname(project))
        self.assertNotEqual(
            ntpath.normpath(ntpath.join(project, previous_bug)), target
        )

    def test_staged_project_child_camera_folder(self):
        self.assert_native_resolves(
            r"C:\packet\SUP_Individual_Helpers.lvproj",
            r"C:\packet\camera\private\SUP_Camera_Epoch.vi",
            "../camera/private/SUP_Camera_Epoch.vi",
        )

    def test_forward_slashes_and_drive_case(self):
        self.assert_native_resolves(
            "C:/packet/project.lvproj", "c:/packet/camera/tap.vi",
            "../camera/tap.vi",
        )

    def test_spaces_unicode_and_ampersand_survive_xml_roundtrip(self):
        project = "C:/helper pack/project.lvproj"
        target = "C:/helper pack/caméra/a & b.vi"
        url = project_item_url(project, target)
        item = ET.Element("Item", URL=url)
        parsed = ET.fromstring(ET.tostring(item, encoding="utf-8"))
        self.assertEqual(parsed.get("URL"), "../caméra/a & b.vi")
        resolved = ntpath.normpath(ntpath.join(project, parsed.get("URL")))
        self.assertEqual(resolved, ntpath.normpath(target))

    def test_posix_paths_follow_same_filebase_rule(self):
        project, target = "/packet/project.lvproj", "/packet/camera/tap.vi"
        url = project_item_url(project, target)
        self.assertEqual(url, "../camera/tap.vi")
        self.assertEqual(posixpath.normpath(posixpath.join(project, url)), target)

    def test_rejects_directory_base_relative_paths_and_different_drives(self):
        for project, target in [
            (r"C:\packet", r"C:\packet\tap.vi"),
            ("project.lvproj", r"C:\packet\tap.vi"),
            (r"C:\packet\project.lvproj", "tap.vi"),
            (r"C:\packet\project.lvproj", r"D:\packet\tap.vi"),
        ]:
            with self.assertRaises(ValueError):
                project_item_url(project, target)


if __name__ == "__main__":
    unittest.main()
