#!/usr/bin/env python3
"""DeviceServers Refactoring Verification Script

Tests imports from the reorganized DeviceServers structure
"""


def test_imports():
    """Test various device server imports to verify refactoring"""
    print("=" * 60)
    print("DeviceServers Refactoring Verification")
    print("=" * 60)

    imports_to_test = [
        # Base classes
        ("DeviceServers.base.general", "DS_General"),
        ("DeviceServers.base.motor", "DS_MOTORIZED_MULTI_AXES"),
        ("DeviceServers.base.camera", "DS_CAMERA_CCD"),
        # Cameras
        ("DeviceServers.cameras.basler.DS_Basler_camera", "DS_Basler_camera"),
        ("DeviceServers.cameras.andor.DS_ANDOR_CCD", "DS_ANDOR_CCD"),
        ("DeviceServers.cameras.avantes.DS_AVANTES_CCD", "DS_AVANTES_CCD"),
        # Motion
        ("DeviceServers.motion.owis.DS_OWIS_PS90", "DS_OWIS_PS90"),
        ("DeviceServers.motion.standa.DS_Standa_Motor", "DS_Standa_Motor"),
        ("DeviceServers.motion.topdirect.DS_TopDirect_Motor", "DS_TopDirect_Motor"),
        # Power
        ("DeviceServers.power.netio.DS_Netio_pdu", "DS_Netio_pdu"),
        ("DeviceServers.power.numato.DS_Numato_GPIO", "DS_Numato_GPIO"),
        ("DeviceServers.power.rpi.DS_RPI_GPIO", "DS_RPI_GPIO"),
        # Control
        ("DeviceServers.control.experiment.DS_Experiment", "DS_Experiment"),
        ("DeviceServers.control.laser_pointing.DS_LaserPointing", "DS_LaserPointing"),
        ("DeviceServers.control.sync.DS_SYNCHRONIZER", "DS_SYNCHRONIZER"),
        # Data
        ("DeviceServers.data.archive.DS_Archive", "DS_Archive"),
        ("DeviceServers.data.stresing.DS_STRESING_IR", "DS_STRESING_IR"),
        # Spectrographs
        (
            "DeviceServers.spectrographs.avantes.DS_AVANTES_SPECTRO",
            "DS_AVANTES_SPECTRO",
        ),
        # Shared
        ("DeviceServers.shared.DS_Widget", "DS_General_Widget"),
    ]

    successful_imports = []
    failed_imports = []

    for module_path, class_name in imports_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)  # Try to access the class
            successful_imports.append((module_path, class_name))
            print(f"✅ {module_path}.{class_name}")
        except ImportError as e:
            failed_imports.append((module_path, class_name, str(e)))
            print(f"❌ {module_path}.{class_name} - {e}")
        except AttributeError as e:
            failed_imports.append((module_path, class_name, f"Class not found: {e}"))
            print(f"❌ {module_path}.{class_name} - Class not found: {e}")
        except Exception as e:
            failed_imports.append((module_path, class_name, f"Unexpected error: {e}"))
            print(f"❌ {module_path}.{class_name} - Unexpected error: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully imported: {len(successful_imports)}")
    print(f"❌ Failed imports: {len(failed_imports)}")

    if failed_imports:
        print("\nFailed imports details:")
        for module_path, class_name, error in failed_imports:
            print(f"  - {module_path}.{class_name}: {error}")

    print(
        f"\nRefactoring status: {'🎉 SUCCESSFUL' if len(failed_imports) == 0 else '⚠️ NEEDS WORK'}"
    )
    print(
        f"Success rate: {len(successful_imports) / (len(successful_imports) + len(failed_imports)) * 100:.1f}%"
    )


if __name__ == "__main__":
    test_imports()
