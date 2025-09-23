import sys
from pathlib import Path
from typing import Dict, Optional, Type

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from PyQt5.QtGui import QIcon
from taurus.qt.qtgui.application import TaurusApplication

from DeviceServers.shared.DS_Widget import VisType
from gui.Panels import GeneralPanel


def create_client_panel(
    DS_Panel: Type[GeneralPanel],
    title: str,
    widget_class: Type,
    icon: str,
    layouts: Dict[str, Dict],
    instance: str,
    vis_type: VisType = VisType.FULL,
) -> Optional[GeneralPanel]:
    """Create a client panel programmatically

    Args:
        DS_Panel: Panel class to instantiate
        title: Window title
        widget_class: Widget class for the panel
        icon: Icon path
        layouts: Layout configurations
        instance: Instance name (key in layouts)
        vis_type: Visualization type

    Returns:
        Panel instance or None if failed

    """
    try:
        if instance not in layouts:
            print(f"Instance '{instance}' not found in layouts: {list(layouts.keys())}")
            return None

        choice = layouts[instance]["selection"]
        width = layouts[instance]["width"]

        print(f"Creating {title} panel - instance: {instance}, vis: {vis_type.value}")

        panel = DS_Panel(
            choice=choice,
            widget_class=widget_class,
            title=f"{title} - {instance}",
            icon=QIcon(icon),
            width=width,
            vis_type=vis_type,
        )

        return panel

    except Exception as e:
        print(f"Failed to create panel: {e}")
        import traceback

        traceback.print_exc()
        return None


def main(
    DS_Panel: GeneralPanel,
    title: str,
    widget_class,
    icon: str,
    layouts,
    instance: Optional[str] = None,
    vis_type: Optional[VisType] = None,
    standalone: bool = True,
):
    """Main function supporting both CLI and programmatic usage

    Args:
        DS_Panel: Panel class
        title: Window title
        widget_class: Widget class
        icon: Icon path
        layouts: Layout configurations
        instance: Instance name (if None, uses sys.argv[1])
        vis_type: Visualization type (if None, uses sys.argv[2] or FULL)
        standalone: Whether to run as standalone app with sys.exit

    """
    # Determine instance and vis_type
    if instance is None:
        if len(sys.argv) >= 2:
            instance = sys.argv[1]
        else:
            print("Not enough arguments were passed...")
            print(f"Available instances: {list(layouts.keys())}")
            return None

    if vis_type is None:
        vis_type = VisType.FULL
        if len(sys.argv) >= 3:
            try:
                vis_type = VisType(sys.argv[2])
            except (ValueError, NameError):
                print(f"Invalid vis_type '{sys.argv[2]}', using FULL")

    print(f"Arguments: instance={instance}, vis_type={vis_type.value}")

    try:
        # Create TaurusApplication if standalone
        if standalone:
            app = TaurusApplication(sys.argv, cmd_line_parser=None)

        # Create the panel
        panel = create_client_panel(
            DS_Panel, title, widget_class, icon, layouts, instance, vis_type
        )

        if panel is None:
            return None

        # Show the panel
        panel.show()

        # Run app if standalone
        if standalone:
            sys.exit(app.exec_())
        else:
            return panel

    except KeyError:
        print(f"Instance '{instance}' not found in layouts: {list(layouts.keys())}")
        return None
    except Exception as e:
        print(f"Error creating client: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
