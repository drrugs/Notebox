# Notebox Diagram App
D2 Drag n Drop Diagram Designer - A powerful, intuitive D2 studio built with Python, Cursor (AI), and PyQt that makes it easy to create, edit, and export diagrams.

<img src="https://github.com/user-attachments/assets/e3f0d434-1e8a-4c37-9d62-286a85ec993e" height="500" />


## Features

- **Intuitive Canvas Interface**: Drag and drop elements to create your diagram
- **Multiple Shape Types**: Boxes, circles, diamonds, hexagons and more
- **Connection Arrows**: Create clear relationships between elements
- **Real-time D2 Code Generation**: Automatically generates D2 code from your visual diagram
- **Smart Sizing**: Elements automatically resize to accommodate text
- **Multiple Export Options**: SVG, PNG, JPEG, and interactive HTML
- **Interactive HTML Export**: Embedded viewer with zoom, pan, and fullscreen capabilities
- **Dark Mode**: Easy on the eyes for extended design sessions
- **Advanced Selection Tools**: Selection box for multiple elements
- **Keyboard Shortcuts**: Speed up your workflow with keyboard commands
- **Color Customization**: Choose from predefined colors or pick custom shades
- **Undo/Redo**: Full support for undo/redo operations

## Usage

### Basic Controls

- **Left-click and drag**: Move elements or pan the canvas
- **Right-click and drag**: Create a selection box
- **Double-click**: Edit element properties
- **Mouse wheel**: Zoom in/out

### Keyboard Shortcuts

- **Ctrl+S**: Save diagram
- **Ctrl+O**: Open diagram
- **Ctrl+Z**: Undo
- **Ctrl+Y**: Redo
- **Ctrl+D**: Duplicate selected element
- **Ctrl+X**: Remove parent relationship
- **Delete/X**: Delete selected element
- **Arrow keys**: Move selected element

### Creating Connections

1. Select a source element
2. Right-click and drag to the target element
3. Release to create the connection

### Export Options

Access export options through the Save/Load menu:
- SVG: Vector format ideal for printing and further editing
- PNG: Raster format with transparency
- JPEG: Compact raster format
- HTML: Interactive web page with embedded diagram viewer

## Technologies

- **Python**: Core programming language
- **PyQt5**: GUI framework
- **D2**: Diagram scripting language (for code generation)
- **SVG**: Vector graphics for export and rendering


## Installation

### Prerequisites

- Python 3.6 or higher
- PyQt5
- Additional dependencies listed in `requirements.txt`
