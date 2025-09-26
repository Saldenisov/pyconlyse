import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from PyQt5 import QtWidgets
from DeviceServers.shared.DS_Widget import VisType
from gui.Panels import GeneralPanel


def main(DS_Panel: GeneralPanel, title: str, widget_class, icon: str, layouts, instance=None, vis_type=None, standalone=True):
    print(f'Arguments: {sys.argv} were given')
    
    # Determine instance - from parameter or command line
    if instance is None:
        if len(sys.argv) >= 2:
            instance = sys.argv[1]
        else:
            print(f'Not enough arguments were passed...')
            return
    
    # Determine vis_type - from parameter or command line
    if vis_type is None:
        vis_type = VisType.FULL
        if len(sys.argv) >= 3:
            try:
                vis_type = VisType(sys.argv[2])
            except (ValueError, NameError):
                pass
    
    try:
        choice = layouts[instance]['selection']
        width = layouts[instance]['width']
        print(f'Starting Widget in {vis_type}...')
        
        if standalone:
            app = TaurusApplication(sys.argv, cmd_line_parser=None)
            panel = DS_Panel(choice=choice, widget_class=widget_class, title=title,
                           icon=QIcon(icon), width=width, vis_type=vis_type)
            # Fit window to its contents
            try:
                if panel.layout() is not None:
                    panel.layout().setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
            except Exception:
                pass
            panel.adjustSize()
            panel.show()
            panel.raise_()
            panel.activateWindow()
            sys.exit(app.exec_())
        else:
            # Non-standalone mode - return panel instance
            panel = DS_Panel(choice=choice, widget_class=widget_class, title=title,
                           icon=QIcon(icon), width=width, vis_type=vis_type)
            return panel
            
    except KeyError:
        print(f'Instance "{instance}" is not presented in {list(layouts.keys())}')


if __name__ == '__main__':
    main()
