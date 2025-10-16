from _functools import partial

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtCore import Qt
from taurus import Device
from taurus.qt.qtgui.display import TaurusLabel
from taurus.qt.qtgui.input import TaurusWheelEdit

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class Standa_LaserPointing(DS_General_Widget):
    """Minimal Standa motor widget for LaserPointing applications."""

    def __init__(self, device_name: str, parent=None, vis_type=VisType.MIN):
        self.relative_shift = 1.0
        super().__init__(device_name, parent, vis_type)
        
    def register_DS_full(self, group_number=1):
        # Use MIN layout even for FULL vis_type in LaserPointing context
        self.register_DS_min(group_number)
        
    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        dev_name = self.dev_name
        
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
            
            # Get device properties safely
            friendly_name = dev_name.split('/')[-1]
            try:
                friendly_name = ds.get_property("friendly_name")["friendly_name"][0]
            except Exception:
                pass
            
            # Get layouts
            lo_device = getattr(self, f"layout_main_{dev_name}")
            lo_status = getattr(self, f"layout_status_{dev_name}")
            
            # Simple status
            self.set_state_status()
            
            # Create simple widget
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(widget)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)
            
            # Name
            name_label = QtWidgets.QLabel(friendly_name)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet("font-size: 10px; font-weight: bold;")
            layout.addWidget(name_label)
            
            # Position
            pos_label = TaurusLabel()
            pos_label.model = f"{dev_name}/position"
            pos_label.setAlignment(Qt.AlignCenter)
            pos_label.setStyleSheet("background: white; border: 1px solid gray; font-size: 9px;")
            pos_label.setMaximumHeight(20)
            layout.addWidget(pos_label)
            
            # Buttons
            btn_layout = QtWidgets.QHBoxLayout()
            
            btn_left = QtWidgets.QPushButton("<")
            btn_left.setFixedSize(20, 20)
            btn_left.clicked.connect(partial(self.move_step, -1))
            
            step_label = QtWidgets.QLabel(f"{self.relative_shift}")
            step_label.setAlignment(Qt.AlignCenter)
            step_label.setStyleSheet("background: lightgray; font-size: 8px;")
            step_label.setMaximumHeight(20)
            step_label.setMinimumWidth(30)
            
            btn_right = QtWidgets.QPushButton(">")
            btn_right.setFixedSize(20, 20)
            btn_right.clicked.connect(partial(self.move_step, 1))
            
            # Context menu for step size
            step_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            step_label.customContextMenuRequested.connect(self.show_step_menu)
            
            btn_layout.addWidget(btn_left)
            btn_layout.addWidget(step_label)
            btn_layout.addWidget(btn_right)
            
            layout.addLayout(btn_layout)
            
            # Store references
            setattr(self, f"step_label_{dev_name}", step_label)
            
            # Add to main layout
            lo_device.addLayout(lo_status)
            lo_device.addWidget(widget)
            lo_group.addLayout(lo_device)
            
        except Exception as e:
            print(f"Error creating Standa LaserPointing widget for {dev_name}: {e}")
            # Fallback: create simple error label
            error_label = QtWidgets.QLabel(f"Error: {dev_name}")
            lo_group.addWidget(error_label)
    
    def move_step(self, direction: int):
        """Move motor by step size in given direction"""
        try:
            current_pos = self.ds.position
            new_pos = current_pos + (self.relative_shift * direction)
            # Use non-blocking execute_action
            self.execute_action(new_pos, self.ds, "move_axis_abs", True)
        except Exception as e:
            print(f"Error moving {self.dev_name}: {e}")
    
    def show_step_menu(self, pos):
        """Show context menu for step size selection"""
        sender = self.sender()
        menu = QtWidgets.QMenu()
        
        step_sizes = [0.1, 0.5, 1, 2, 5, 10, 20, 50]
        
        for step in step_sizes:
            action = menu.addAction(f"{step}")
            action.triggered.connect(partial(self.set_step_size, step))
            
        menu.exec_(sender.mapToGlobal(pos))
    
    def set_step_size(self, step):
        """Set the step size"""
        self.relative_shift = step
        step_label = getattr(self, f"step_label_{self.dev_name}")
        step_label.setText(f"{step}")
        
    def set_the_control_value(self, value):
        """Set position from external control (e.g., states)"""
        try:
            # Use non-blocking execute_action like the original widget
            self.execute_action(float(value), self.ds, "move_axis_abs", True)
        except Exception as e:
            print(f"Error setting control value for {self.dev_name}: {e}")
            
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click selection"""
        if self.parent:
            print(f"{self.dev_name} is selected.")
            self.setStyleSheet("background-color: lightgreen; border: 1px solid black;")
            self.parent.active_widget = self.dev_name
            self.parent.update_active_widget()
