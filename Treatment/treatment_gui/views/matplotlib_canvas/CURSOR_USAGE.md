# Draggable Cursor System

## Overview
The new draggable cursor system replaces the old RectangleSelector with a more intuitive interface for selecting regions in the 2D data visualization (imshow).

## Features

### Visual Design
- **Red vertical lines** (x1, x2) - control wavelength range
- **Cyan horizontal lines** (y1, y2) - control time delay range
- **Thicker lines (2.5pt)** for better visibility
- **Highlighted during drag (4pt)** with full opacity

### Usage

#### Basic Interaction
1. **Click and drag** any line to move it
2. Lines snap to your mouse position in real-time
3. Release mouse to finalize position
4. Kinetics and Spectrum graphs update automatically

#### Keyboard Shortcuts
- **'c'** - Toggle cursor visibility on/off
- **'r'** - Reset cursors to default positions (20% and 80% of data range)

### Advantages over RectangleSelector
1. **Individual line control** - Move each boundary independently
2. **Visual feedback** - See exactly which line you're dragging
3. **No diagonal dragging required** - Just grab and move
4. **Easier fine-tuning** - Precise positioning is simpler
5. **Better for touchpads** - No need for diagonal gestures

## Technical Details

### Classes

#### `DraggableCursor`
Base class managing four draggable lines with mouse interaction.

#### `ToggleableCursor`
Extended version with keyboard shortcuts for visibility and reset.

### Integration

The cursor system is integrated into `DataCanvas`:
```python
# Enable cursors with callback
canvas.enable_draggable_cursors(
    callback=lambda x1, x2, y1, y2: update_function(x1, x2, y1, y2)
)

# Update cursor positions programmatically
canvas.draw_cursors(cursors=cursors_2d_object)
```

## Color Scheme
- **Red**: Vertical lines (wavelength selection)
- **Cyan**: Horizontal lines (time delay selection)
- **Semi-transparent (0.8)**: Normal state
- **Opaque (1.0)**: During drag

This makes it easy to distinguish between wavelength and time dimensions while maintaining good visibility against the data.
