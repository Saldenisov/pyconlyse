"""
Draggable cursor lines for 2D data visualization.

Provides an intuitive interface for selecting regions on imshow plots
using draggable vertical and horizontal lines instead of rectangle selection.
"""

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.artist import Artist


class DraggableCursor:
    """
    Manages four draggable lines (2 vertical, 2 horizontal) for region selection.
    
    Much more convenient than RectangleSelector - each line can be dragged independently,
    with visual feedback showing which line is being moved.
    """
    
    def __init__(self, ax, on_change_callback=None, initial_cursors=None):
        """
        Parameters
        ----------
        ax : matplotlib.axes.Axes
            The axes to draw cursors on
        on_change_callback : callable, optional
            Function to call when cursor positions change.
            Signature: callback(x1, x2, y1, y2)
        initial_cursors : Cursors2D, optional
            Initial cursor positions
        """
        self.ax = ax
        self.on_change_callback = on_change_callback
        self.active_line = None
        self.press_event = None
        
        # Get data limits
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Initialize cursor positions
        if initial_cursors:
            x1_pos, x2_pos = initial_cursors.x1[1], initial_cursors.x2[1]
            y1_pos, y2_pos = initial_cursors.y1[1], initial_cursors.y2[1]
        else:
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            x1_pos = xlim[0] + x_range * 0.2
            x2_pos = xlim[0] + x_range * 0.8
            y1_pos = ylim[0] + y_range * 0.2
            y2_pos = ylim[0] + y_range * 0.8
        
        # Create the four cursor lines with distinct styling
        self.vline1 = ax.axvline(x=x1_pos, color='red', linewidth=2.5, 
                                 alpha=0.8, linestyle='-', picker=5)
        self.vline2 = ax.axvline(x=x2_pos, color='red', linewidth=2.5, 
                                 alpha=0.8, linestyle='-', picker=5)
        self.hline1 = ax.axhline(y=y1_pos, color='cyan', linewidth=2.5, 
                                 alpha=0.8, linestyle='-', picker=5)
        self.hline2 = ax.axhline(y=y2_pos, color='cyan', linewidth=2.5, 
                                 alpha=0.8, linestyle='-', picker=5)
        
        # Store references
        self.lines = {
            'vline1': self.vline1,
            'vline2': self.vline2,
            'hline1': self.hline1,
            'hline2': self.hline2
        }
        
        # Connect events
        self.canvas = ax.figure.canvas
        self.cid_press = self.canvas.mpl_connect('button_press_event', self.on_press)
        self.cid_release = self.canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_motion = self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        
    def on_press(self, event):
        """Handle mouse button press - pick a line to drag."""
        if event.inaxes != self.ax:
            return
        
        # Check which line was clicked (if any)
        for name, line in self.lines.items():
            if line.contains(event)[0]:
                self.active_line = name
                self.press_event = event
                # Highlight the active line
                line.set_linewidth(4)
                line.set_alpha(1.0)
                self.canvas.draw_idle()
                break
    
    def on_motion(self, event):
        """Handle mouse motion - drag the active line."""
        if self.active_line is None or event.inaxes != self.ax:
            return
        
        line = self.lines[self.active_line]
        
        # Update line position based on which type it is
        if self.active_line.startswith('vline'):
            # Vertical line - update x position
            if event.xdata is not None:
                line.set_xdata([event.xdata, event.xdata])
        else:
            # Horizontal line - update y position
            if event.ydata is not None:
                line.set_ydata([event.ydata, event.ydata])
        
        self.canvas.draw_idle()
    
    def on_release(self, event):
        """Handle mouse button release - finalize line position."""
        if self.active_line is None:
            return
        
        # Reset line styling
        line = self.lines[self.active_line]
        line.set_linewidth(2.5)
        line.set_alpha(0.8)
        
        self.active_line = None
        self.press_event = None
        self.canvas.draw_idle()
        
        # Notify callback of position change
        if self.on_change_callback:
            positions = self.get_positions()
            self.on_change_callback(*positions)
    
    def get_positions(self):
        """
        Get current cursor positions.
        
        Returns
        -------
        tuple
            (x1, x2, y1, y2) positions in data coordinates
        """
        x1 = self.vline1.get_xdata()[0]
        x2 = self.vline2.get_xdata()[0]
        y1 = self.hline1.get_ydata()[0]
        y2 = self.hline2.get_ydata()[0]
        return x1, x2, y1, y2
    
    def set_positions(self, x1=None, x2=None, y1=None, y2=None):
        """
        Set cursor positions programmatically.
        
        Parameters
        ----------
        x1, x2 : float, optional
            Vertical line positions
        y1, y2 : float, optional
            Horizontal line positions
        """
        if x1 is not None:
            self.vline1.set_xdata([x1, x1])
        if x2 is not None:
            self.vline2.set_xdata([x2, x2])
        if y1 is not None:
            self.hline1.set_ydata([y1, y1])
        if y2 is not None:
            self.hline2.set_ydata([y2, y2])
        self.canvas.draw_idle()
    
    def update_from_cursors(self, cursors):
        """
        Update positions from a Cursors2D object.
        
        Parameters
        ----------
        cursors : Cursors2D
            Cursor data structure with x1, x2, y1, y2 tuples
        """
        self.set_positions(
            x1=cursors.x1[1],
            x2=cursors.x2[1],
            y1=cursors.y1[1],
            y2=cursors.y2[1]
        )
    
    def remove(self):
        """Remove all cursor lines and disconnect events."""
        for line in self.lines.values():
            line.remove()
        self.canvas.mpl_disconnect(self.cid_press)
        self.canvas.mpl_disconnect(self.cid_release)
        self.canvas.mpl_disconnect(self.cid_motion)
    
    def set_visible(self, visible):
        """Show or hide cursor lines."""
        for line in self.lines.values():
            line.set_visible(visible)
        self.canvas.draw_idle()


class ToggleableCursor(DraggableCursor):
    """
    Extended draggable cursor with keyboard toggle functionality.
    
    Press 'c' to toggle cursor visibility
    Press 'r' to reset cursors to default positions
    """
    
    def __init__(self, ax, on_change_callback=None, initial_cursors=None):
        super().__init__(ax, on_change_callback, initial_cursors)
        self.visible = True
        self.cid_key = self.canvas.mpl_connect('key_press_event', self.on_key)
    
    def on_key(self, event):
        """Handle keyboard shortcuts."""
        if event.key == 'c':
            # Toggle visibility
            self.visible = not self.visible
            self.set_visible(self.visible)
        elif event.key == 'r':
            # Reset to default positions
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            self.set_positions(
                x1=xlim[0] + x_range * 0.2,
                x2=xlim[0] + x_range * 0.8,
                y1=ylim[0] + y_range * 0.2,
                y2=ylim[0] + y_range * 0.8
            )
            if self.on_change_callback:
                positions = self.get_positions()
                self.on_change_callback(*positions)
    
    def remove(self):
        """Remove cursor and disconnect all events."""
        self.canvas.mpl_disconnect(self.cid_key)
        super().remove()
