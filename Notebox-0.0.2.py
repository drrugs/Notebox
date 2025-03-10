import sys
import os
import json
import math
import random
import time
import re
import uuid
import ctypes
from datetime import datetime
from functools import partial

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QToolBar, QAction, QFileDialog, QMessageBox,
                           QDialog, QLineEdit, QFormLayout, QSpinBox, QComboBox, QColorDialog,
                           QToolButton, QMenu, QSizePolicy, QFrame, QScrollArea, QTextEdit,
                           QSlider, QGroupBox, QRadioButton, QCheckBox, QTabWidget, QSplitter,
                           QListWidget, QListWidgetItem, QGraphicsDropShadowEffect, QGridLayout, QShortcut,
                           QWidgetAction)
from PyQt5.QtCore import (Qt, QPoint, QRect, QSize, QTimer, QEvent, QMimeData, QByteArray, QBuffer, QIODevice,
                        pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF, QPointF, QLineF, QTime)
from PyQt5.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, QDrag, QCursor, QPolygon, 
                        QBrush, QPolygon, QPainterPath, QPalette, QIcon, QRadialGradient, QLinearGradient, QKeySequence, QFontMetrics)
from PyQt5.QtSvg import QSvgGenerator

# Dark mode colors
DARK_BG = QColor(45, 45, 45)
DARK_WIDGET_BG = QColor(60, 60, 60)
DARK_TEXT = QColor(240, 240, 240)  # Light color for UI text
DARK_HIGHLIGHT = QColor(80, 80, 80)
DARK_GRID = QColor(70, 70, 70)
DARK_SELECTION = QColor(0, 120, 215)
ARROW_COLOR = QColor(100, 150, 255, 180)  # Faint blue color for arrows
DARK_BORDER = QColor(100, 100, 100)
ELEMENT_TEXT_COLOR = QColor(0, 0, 0)  # Black color for element text

# Windows-specific dark mode constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20

def set_window_dark_mode(hwnd):
    """Enable dark mode for a window (Windows 10/11 only)"""
    try:
        # Check if running on Windows
        if sys.platform == "win32":
            # Try to set dark mode for the window
            dwmapi = ctypes.WinDLL("dwmapi")
            value = ctypes.c_int(1)  # 1 = dark mode
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
            return True
    except Exception as e:
        print(f"Failed to set dark mode for window: {e}")
        return False

class DiagramElement:
    """Base class for all diagram elements"""
    def __init__(self, x, y, width, height, label=""):
        self.x = x
        self.y = y
        self.label = label
        
        # Calculate minimum size based on text content
        min_width, min_height = self._calculate_min_size_for_text(label)
        
        # Use the larger of the provided size or the minimum required size
        self.width = max(width, min_width)
        self.height = max(height, min_height)
        
        self.id = id(self)
        self.color = QColor(180, 180, 180)  # Lighter default color for elements
        self.border_color = QColor(120, 120, 120)  # Darker border for contrast
        self.selected = False
        self.connections = []  # List of connected elements
        self.parent = None  # Parent element for nesting
        self.children = []  # Child elements nested inside this element
        self.container_title = ""  # Initialize with empty string for custom container title
    
    def _calculate_min_size_for_text(self, text):
        """Calculate the minimum size needed to display the text comfortably"""
        if not text:
            return 100, 60  # Default minimum size
        
        # Create a temporary QFontMetrics to measure text
        font = QFont()
        # Make the font slightly larger to ensure text fits
        font.setPointSize(10)  # Default size is usually 8 or 9
        font_metrics = QFontMetrics(font)
        
        # Get text dimensions - use horizontalAdvance if available (newer PyQt5), fall back to width
        try:
            text_width = font_metrics.horizontalAdvance(text)
        except AttributeError:
            # Fall back to width for older PyQt5 versions
            text_width = font_metrics.width(text)
            
        text_height = font_metrics.height()
        
        # Add generous padding around the text (40px on each side horizontally, 30px vertically)
        min_width = text_width + 80
        min_height = text_height + 60
        
        # Ensure minimum dimensions
        min_width = max(min_width, 100)
        min_height = max(min_height, 60)
        
        print(f"Text: '{text}', Calculated min size: {min_width}x{min_height}")
        
        return min_width, min_height
    
    def contains(self, point):
        return (self.x <= point.x() <= self.x + self.width and 
                self.y <= point.y() <= self.y + self.height)
    
    def overlaps_with(self, other, padding=10):
        """Check if this element overlaps with another element, considering padding"""
        # Add padding to both elements
        this_rect = QRectF(self.x - padding, self.y - padding, 
                          self.width + 2 * padding, self.height + 2 * padding)
        other_rect = QRectF(other.x, other.y, other.width, other.height)
        
        # Check if the rectangles intersect
        return this_rect.intersects(other_rect)
    
    def draw(self, painter):
        # To be implemented by subclasses
        pass
    
    def to_d2(self):
        # Base implementation for D2 code generation
        d2_code = f"{self.label}: {{\n  style.fill: \"#{self.color.red():02x}{self.color.green():02x}{self.color.blue():02x}\"\n"
        
        # Add container information if this element has children
        if self.children:
            # Add container title if available
            container_title = self.container_title if self.container_title else f"{self.label}"
            d2_code += f"  # Container: {container_title}\n"
            
            # Add child elements with unique IDs to avoid conflicts
            for i, child in enumerate(self.children):
                child_id = f"{self.label}_{child.label}_{i}"
                d2_code += f"  {child_id}: {{\n"
                d2_code += f"    label: {child.label}\n"
                if isinstance(child, CircleElement):
                    d2_code += f"    shape: circle\n"
                elif isinstance(child, DiamondElement):
                    d2_code += f"    shape: diamond\n"
                elif isinstance(child, HexagonElement):
                    d2_code += f"    shape: hexagon\n"
                else:  # Default to box/rectangle
                    d2_code += f"    shape: rectangle\n"
                d2_code += f"    style.fill: \"#{child.color.red():02x}{child.color.green():02x}{child.color.blue():02x}\"\n"
                d2_code += f"  }}\n"
        
        d2_code += "}"
        return d2_code
    
    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        
        # Move all children with the parent
        for child in self.children:
            child.move(dx, dy)
        
    def resize(self, width, height):
        # Calculate minimum size based on text content
        min_width, min_height = self._calculate_min_size_for_text(self.label)
        
        # Use the larger of the provided size or the minimum required size
        self.width = max(width, min_width)
        self.height = max(height, min_height)


class BoxElement(DiagramElement):
    """A rectangular box element"""
    def __init__(self, x, y, width=100, height=60, label="Box"):
        super().__init__(x, y, width, height, label)
        
    def draw(self, painter):
        if self.selected:
            painter.setPen(QPen(DARK_SELECTION, 2, Qt.SolidLine))
        else:
            painter.setPen(QPen(self.border_color, 1, Qt.SolidLine))
            
        painter.setBrush(QBrush(self.color))
        painter.drawRect(self.x, self.y, self.width, self.height)
        
        # Draw label with black text color
        painter.setPen(QPen(ELEMENT_TEXT_COLOR))
        
        # Save the current font
        original_font = painter.font()
        
        # Create a larger font for the text
        font = QFont(original_font)
        font.setPointSize(10)  # Larger font size
        painter.setFont(font)
        
        # Draw the text centered in the element
        painter.drawText(QRect(self.x, self.y, self.width, self.height), 
                         Qt.AlignCenter, self.label)
        
        # Restore the original font
        painter.setFont(original_font)
    
    def to_d2(self):
        # Directly formatted D2 code for box elements
        d2_code = f"{self.label}: {{\n  shape: rectangle\n  style.fill: \"#{self.color.red():02x}{self.color.green():02x}{self.color.blue():02x}\"\n  style.stroke: \"#000000\"\n"
        
        # Add position and size information as comments
        d2_code += f"  # position: {self.x},{self.y},{self.width},{self.height}\n"
        
        # Add container information if this element has children
        if self.children:
            # Add container title if available
            container_title = self.container_title if self.container_title else f"{self.label}"
            d2_code += f"  # Container: {container_title}\n"
            
            # Add child elements with unique IDs to avoid conflicts
            for i, child in enumerate(self.children):
                child_id = f"{self.label}_{child.label}_{i}"
                d2_code += f"  {child_id}: {{\n"
                d2_code += f"    label: {child.label}\n"
                if isinstance(child, CircleElement):
                    d2_code += f"    shape: circle\n"
                elif isinstance(child, DiamondElement):
                    d2_code += f"    shape: diamond\n"
                elif isinstance(child, HexagonElement):
                    d2_code += f"    shape: hexagon\n"
                else:  # Default to box/rectangle
                    d2_code += f"    shape: rectangle\n"
                d2_code += f"    style.fill: \"#{child.color.red():02x}{child.color.green():02x}{child.color.blue():02x}\"\n"
                # Add position and size information for child elements
                d2_code += f"    # position: {child.x},{child.y},{child.width},{child.height}\n"
                d2_code += f"  }}\n"
        
        d2_code += "}"
        return d2_code


class CircleElement(DiagramElement):
    """A circular element"""
    def __init__(self, x, y, width=80, height=80, label="Circle"):
        super().__init__(x, y, width, height, label)
        
    def draw(self, painter):
        if self.selected:
            painter.setPen(QPen(DARK_SELECTION, 2, Qt.SolidLine))
        else:
            painter.setPen(QPen(self.border_color, 1, Qt.SolidLine))
            
        painter.setBrush(QBrush(self.color))
        painter.drawEllipse(self.x, self.y, self.width, self.height)
        
        # Draw label with black text color
        painter.setPen(QPen(ELEMENT_TEXT_COLOR))
        
        # Save the current font
        original_font = painter.font()
        
        # Create a larger font for the text
        font = QFont(original_font)
        font.setPointSize(10)  # Larger font size
        painter.setFont(font)
        
        # Draw the text centered in the element
        painter.drawText(QRect(self.x, self.y, self.width, self.height), 
                         Qt.AlignCenter, self.label)
        
        # Restore the original font
        painter.setFont(original_font)
    
    def to_d2(self):
        # Directly formatted D2 code for circle elements
        d2_code = f"{self.label}: {{\n  shape: circle\n  style.fill: \"#{self.color.red():02x}{self.color.green():02x}{self.color.blue():02x}\"\n  style.stroke: \"#000000\"\n"
        
        # Add position and size information as comments
        d2_code += f"  # position: {self.x},{self.y},{self.width},{self.height}\n"
        
        # Add container information if this element has children
        if self.children:
            # Add container title if available
            container_title = self.container_title if self.container_title else f"{self.label}"
            d2_code += f"  # Container: {container_title}\n"
            
            # Add child elements with unique IDs to avoid conflicts
            for i, child in enumerate(self.children):
                child_id = f"{self.label}_{child.label}_{i}"
                d2_code += f"  {child_id}: {{\n"
                d2_code += f"    label: {child.label}\n"
                if isinstance(child, CircleElement):
                    d2_code += f"    shape: circle\n"
                elif isinstance(child, DiamondElement):
                    d2_code += f"    shape: diamond\n"
                elif isinstance(child, HexagonElement):
                    d2_code += f"    shape: hexagon\n"
                else:  # Default to box/rectangle
                    d2_code += f"    shape: rectangle\n"
                d2_code += f"    style.fill: \"#{child.color.red():02x}{child.color.green():02x}{child.color.blue():02x}\"\n"
                # Add position and size information for child elements
                d2_code += f"    # position: {child.x},{child.y},{child.width},{child.height}\n"
                d2_code += f"  }}\n"
        
        d2_code += "}"
        return d2_code


class DiamondElement(DiagramElement):
    """A diamond element"""
    def __init__(self, x, y, width=100, height=80, label="Diamond"):
        super().__init__(x, y, width, height, label)
        
    def draw(self, painter):
        if self.selected:
            painter.setPen(QPen(DARK_SELECTION, 2, Qt.SolidLine))
        else:
            painter.setPen(QPen(self.border_color, 1, Qt.SolidLine))
            
        painter.setBrush(QBrush(self.color))
        
        # Create a diamond shape using a polygon
        points = [
            QPoint(self.x + self.width // 2, self.y),  # Top
            QPoint(self.x + self.width, self.y + self.height // 2),  # Right
            QPoint(self.x + self.width // 2, self.y + self.height),  # Bottom
            QPoint(self.x, self.y + self.height // 2)  # Left
        ]
        painter.drawPolygon(QPolygon(points))
        
        # Draw label with black text color
        painter.setPen(QPen(ELEMENT_TEXT_COLOR))
        
        # Save the current font
        original_font = painter.font()
        
        # Create a larger font for the text
        font = QFont(original_font)
        font.setPointSize(10)  # Larger font size
        painter.setFont(font)
        
        # Draw the text centered in the element
        painter.drawText(QRect(self.x, self.y, self.width, self.height), 
                         Qt.AlignCenter, self.label)
        
        # Restore the original font
        painter.setFont(original_font)
    
    def to_d2(self):
        # Directly formatted D2 code for diamond elements
        d2_code = f"{self.label}: {{\n  shape: diamond\n  style.fill: \"#{self.color.red():02x}{self.color.green():02x}{self.color.blue():02x}\"\n  style.stroke: \"#000000\"\n"
        
        # Add position and size information as comments
        d2_code += f"  # position: {self.x},{self.y},{self.width},{self.height}\n"
        
        # Add container information if this element has children
        if self.children:
            # Add container title if available
            container_title = self.container_title if self.container_title else f"{self.label}"
            d2_code += f"  # Container: {container_title}\n"
            
            # Add child elements with unique IDs to avoid conflicts
            for i, child in enumerate(self.children):
                child_id = f"{self.label}_{child.label}_{i}"
                d2_code += f"  {child_id}: {{\n"
                d2_code += f"    label: {child.label}\n"
                if isinstance(child, CircleElement):
                    d2_code += f"    shape: circle\n"
                elif isinstance(child, DiamondElement):
                    d2_code += f"    shape: diamond\n"
                elif isinstance(child, HexagonElement):
                    d2_code += f"    shape: hexagon\n"
                else:  # Default to box/rectangle
                    d2_code += f"    shape: rectangle\n"
                d2_code += f"    style.fill: \"#{child.color.red():02x}{child.color.green():02x}{child.color.blue():02x}\"\n"
                # Add position and size information for child elements
                d2_code += f"    # position: {child.x},{child.y},{child.width},{child.height}\n"
                d2_code += f"  }}\n"
        
        d2_code += "}"
        return d2_code


class HexagonElement(DiagramElement):
    """A hexagon element"""
    def __init__(self, x, y, width=100, height=80, label="Hexagon"):
        super().__init__(x, y, width, height, label)
        
    def draw(self, painter):
        if self.selected:
            painter.setPen(QPen(DARK_SELECTION, 2, Qt.SolidLine))
        else:
            painter.setPen(QPen(self.border_color, 1, Qt.SolidLine))
            
        painter.setBrush(QBrush(self.color))
        
        # Create a hexagon shape using a polygon
        # Calculate points for a regular hexagon
        w, h = self.width, self.height
        points = [
            QPoint(self.x + w // 4, self.y),  # Top left
            QPoint(self.x + w * 3 // 4, self.y),  # Top right
            QPoint(self.x + w, self.y + h // 2),  # Right
            QPoint(self.x + w * 3 // 4, self.y + h),  # Bottom right
            QPoint(self.x + w // 4, self.y + h),  # Bottom left
            QPoint(self.x, self.y + h // 2)  # Left
        ]
        painter.drawPolygon(QPolygon(points))
        
        # Draw label with black text color
        painter.setPen(QPen(ELEMENT_TEXT_COLOR))
        
        # Save the current font
        original_font = painter.font()
        
        # Create a larger font for the text
        font = QFont(original_font)
        font.setPointSize(10)  # Larger font size
        painter.setFont(font)
        
        # Draw the text centered in the element
        painter.drawText(QRect(self.x, self.y, self.width, self.height), 
                         Qt.AlignCenter, self.label)
        
        # Restore the original font
        painter.setFont(original_font)
    
    def to_d2(self):
        # Directly formatted D2 code for hexagon elements
        d2_code = f"{self.label}: {{\n  shape: hexagon\n  style.fill: \"#{self.color.red():02x}{self.color.green():02x}{self.color.blue():02x}\"\n  style.stroke: \"#000000\"\n"
        
        # Add position and size information as comments
        d2_code += f"  # position: {self.x},{self.y},{self.width},{self.height}\n"
        
        # Add container information if this element has children
        if self.children:
            # Add container title if available
            container_title = self.container_title if self.container_title else f"{self.label}"
            d2_code += f"  # Container: {container_title}\n"
            
            # Add child elements with unique IDs to avoid conflicts
            for i, child in enumerate(self.children):
                child_id = f"{self.label}_{child.label}_{i}"
                d2_code += f"  {child_id}: {{\n"
                d2_code += f"    label: {child.label}\n"
                if isinstance(child, CircleElement):
                    d2_code += f"    shape: circle\n"
                elif isinstance(child, DiamondElement):
                    d2_code += f"    shape: diamond\n"
                elif isinstance(child, HexagonElement):
                    d2_code += f"    shape: hexagon\n"
                else:  # Default to box/rectangle
                    d2_code += f"    shape: rectangle\n"
                d2_code += f"    style.fill: \"#{child.color.red():02x}{child.color.green():02x}{child.color.blue():02x}\"\n"
                # Add position and size information for child elements
                d2_code += f"    # position: {child.x},{child.y},{child.width},{child.height}\n"
                d2_code += f"  }}\n"
        
        d2_code += "}"
        return d2_code


class ArrowConnection:
    """A connection between two elements"""
    def __init__(self, source, target, label=""):
        # Store references to the source and target elements
        if source is None or target is None:
            print("ERROR: Attempted to create connection with None element")
        
        self.source = source
        self.target = target
        self.label = label
        self.id = id(self)
        self.selected = False
        
        # Debug print
        print(f"Created connection from {self.source.label} to {self.target.label}")
        
    def draw(self, painter):
        # Calculate connection points
        source_center = QPoint(self.source.x + self.source.width//2, 
                              self.source.y + self.source.height//2)
        target_center = QPoint(self.target.x + self.target.width//2, 
                              self.target.y + self.target.height//2)
        
        # Calculate intersection points with shape boundaries
        source_edge = self._find_intersection_point(self.source, source_center, target_center)
        target_edge = self._find_intersection_point(self.target, target_center, source_center)
        
        # Draw line between edge points instead of centers
        if source_edge and target_edge:
            if self.selected:
                # Draw a thicker, brighter line for selected connections
                # First draw a wider, semi-transparent glow effect (70% opacity)
                glow_pen = QPen(QColor(0, 160, 255, 56), 5, Qt.SolidLine)  # 80 * 0.7 = 56
                painter.setPen(glow_pen)
                painter.drawLine(source_edge, target_edge)
                
                # Then draw the main line on top (70% opacity)
                highlight_pen = QPen(QColor(0, 160, 255, 178), 2, Qt.SolidLine)  # 255 * 0.7 = 178
                painter.setPen(highlight_pen)
                painter.drawLine(source_edge, target_edge)
                
                # Draw arrowhead with highlight color
                self._draw_arrow_head(painter, target_edge, self._calculate_angle(source_edge, target_edge))
            else:
                # Draw normal connection
                painter.setPen(QPen(ARROW_COLOR, 1, Qt.SolidLine))
                painter.drawLine(source_edge, target_edge)
                
                # Draw arrowhead
                angle = self._calculate_angle(source_edge, target_edge)
                self._draw_arrow_head(painter, target_edge, angle)
        
        # Draw label with black text color
        if self.label:
            # Make sure the label doesn't contain any ID information
            display_label = self.label
            if '#' in display_label:
                display_label = display_label.split('#')[0].strip()
                
            mid_point = QPoint((source_center.x() + target_center.x()) // 2,
                               (source_center.y() + target_center.y()) // 2)
            
            # Set text color
            painter.setPen(QPen(ELEMENT_TEXT_COLOR))
            
            # Calculate text rectangle for positioning
            text_rect = painter.fontMetrics().boundingRect(display_label)
            text_rect.moveCenter(mid_point)
            
            # Draw text directly without background
            painter.drawText(text_rect, Qt.AlignCenter, display_label)
    
    def _find_intersection_point(self, element, from_point, to_point):
        """Find the point where the line from from_point to to_point intersects the element's boundary"""
        # Calculate direction vector
        dx = to_point.x() - from_point.x()
        dy = to_point.y() - from_point.y()
        
        # Normalize the direction vector
        length = (dx**2 + dy**2)**0.5
        if length < 0.001:  # Avoid division by zero
            return from_point
            
        dx /= length
        dy /= length
        
        # For different shape types, calculate intersection differently
        if isinstance(element, CircleElement):
            # For circles, use parametric equation
            cx = element.x + element.width / 2
            cy = element.y + element.height / 2
            radius = min(element.width, element.height) / 2
            
            # Calculate intersection with circle
            t = self._ray_circle_intersection(from_point.x(), from_point.y(), dx, dy, cx, cy, radius)
            if t > 0:
                return QPoint(int(from_point.x() + dx * t), int(from_point.y() + dy * t))
        
        elif isinstance(element, DiamondElement):
            # For diamonds, check intersection with each edge
            points = [
                QPoint(int(element.x + element.width / 2), int(element.y)),  # Top
                QPoint(int(element.x + element.width), int(element.y + element.height / 2)),  # Right
                QPoint(int(element.x + element.width / 2), int(element.y + element.height)),  # Bottom
                QPoint(int(element.x), int(element.y + element.height / 2))  # Left
            ]
            
            # Check intersection with each edge
            for i in range(4):
                p1 = points[i]
                p2 = points[(i + 1) % 4]
                intersection = self._line_intersection(from_point, to_point, p1, p2)
                if intersection:
                    return intersection
        
        elif isinstance(element, HexagonElement):
            # For hexagons, check intersection with each edge
            w = element.width
            h = element.height
            x = element.x
            y = element.y
            
            points = [
                QPoint(int(x + w * 0.25), int(y)),  # Top left
                QPoint(int(x + w * 0.75), int(y)),  # Top right
                QPoint(int(x + w), int(y + h * 0.5)),  # Middle right
                QPoint(int(x + w * 0.75), int(y + h)),  # Bottom right
                QPoint(int(x + w * 0.25), int(y + h)),  # Bottom left
                QPoint(int(x), int(y + h * 0.5))  # Middle left
            ]
            
            # Check intersection with each edge
            for i in range(6):
                p1 = points[i]
                p2 = points[(i + 1) % 6]
                intersection = self._line_intersection(from_point, to_point, p1, p2)
                if intersection:
                    return intersection
        
        else:  # Default for BoxElement and other rectangular shapes
            # Check intersection with each edge of the rectangle
            rect_points = [
                QPoint(int(element.x), int(element.y)),  # Top-left
                QPoint(int(element.x + element.width), int(element.y)),  # Top-right
                QPoint(int(element.x + element.width), int(element.y + element.height)),  # Bottom-right
                QPoint(int(element.x), int(element.y + element.height))  # Bottom-left
            ]
            
            # Check intersection with each edge
            for i in range(4):
                p1 = rect_points[i]
                p2 = rect_points[(i + 1) % 4]
                intersection = self._line_intersection(from_point, to_point, p1, p2)
                if intersection:
                    return intersection
        
        # If no intersection found, return the center point
        return QPoint(int(element.x + element.width / 2), int(element.y + element.height / 2))
    
    def _ray_circle_intersection(self, x, y, dx, dy, cx, cy, r):
        """Calculate intersection of ray with circle"""
        # Vector from ray origin to circle center
        ocx = cx - x
        ocy = cy - y
        
        # Quadratic equation coefficients
        a = dx * dx + dy * dy
        b = 2 * (dx * ocx + dy * ocy)
        c = ocx * ocx + ocy * ocy - r * r
        
        # Discriminant
        discriminant = b * b - 4 * a * c
        
        if discriminant < 0:
            return -1  # No intersection
        
        # Calculate the two solutions
        t1 = (-b + (discriminant)**0.5) / (2 * a)
        t2 = (-b - (discriminant)**0.5) / (2 * a)
        
        # Return the smallest positive solution
        if t1 > 0 and t2 > 0:
            return min(t1, t2)
        elif t1 > 0:
            return t1
        elif t2 > 0:
            return t2
        else:
            return -1  # No positive solution
    
    def _line_intersection(self, p1, p2, p3, p4):
        """Find intersection point of two line segments"""
        # Convert QPoint to coordinates
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        x3, y3 = p3.x(), p3.y()
        x4, y4 = p4.x(), p4.y()
        
        # Calculate determinants
        den = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
        
        if abs(den) < 0.001:  # Lines are parallel
            return None
            
        ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / den
        ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / den
        
        # Check if intersection is within both line segments
        if 0 <= ua <= 1 and 0 <= ub <= 1:
            x = x1 + ua * (x2 - x1)
            y = y1 + ua * (y2 - y1)
            return QPoint(int(x), int(y))
            
        return None
    
    def _calculate_angle(self, p1, p2):
        import math
        return math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
    
    def _draw_arrow_head(self, painter, point, angle):
        import math
        arrow_size = 10
        angle_adjustment = math.pi / 6  # 30 degrees
        
        # Calculate points for the arrow head - convert float to int
        p1 = QPoint(int(point.x() - arrow_size * math.cos(angle - angle_adjustment)),
                    int(point.y() - arrow_size * math.sin(angle - angle_adjustment)))
        p2 = QPoint(int(point.x() - arrow_size * math.cos(angle + angle_adjustment)),
                    int(point.y() - arrow_size * math.sin(angle + angle_adjustment)))
        
        # Draw the arrow head with faint blue color
        arrow_head = QPolygon()
        arrow_head.append(point)
        arrow_head.append(p1)
        arrow_head.append(p2)
        painter.setBrush(QBrush(ARROW_COLOR))
        painter.drawPolygon(arrow_head)
    
    def to_d2(self):
        # Always use one-way arrow since we're using separate arrows for bidirectional connections
        connection_code = f"{self.source.label} -> {self.target.label}" + (f": {self.label}" if self.label else "")
        
        # Add source and target IDs as a comment to ensure connections can be restored correctly
        # Use a proper D2 comment format that won't be displayed in the diagram
        connection_code += f" # connection: {self.source.id},{self.target.id}"
        
        return connection_code


class ToolboxItem(QToolButton):
    """Items in the toolbox that can be dragged onto the canvas"""
    def __init__(self, element_type, tooltip=""):
        super().__init__()
        self.element_type = element_type
        self.setToolTip(tooltip)
        
        # Create custom icons based on element type
        self.setIconSize(QSize(40, 40))  # Double the icon size (from 20x20 to 40x40)
        self.setFixedSize(64, 64)  # Double the button size (from 32x32 to 64x64)
        
        # Set custom icon based on element type
        self.createCustomIcon(element_type)
        
        self.setStyleSheet("""
            QToolButton {
                background-color: #505050;
                color: #e0e0e0;
                border: 1px solid #646464;
                border-radius: 8px;  /* Double border radius (from 4 to 8) */
                padding: 8px;  /* Double padding (from 4 to 8) */
                margin: 4px;  /* Double margin (from 2 to 4) */
            }
            QToolButton:hover {
                background-color: #606060;
            }
        """)
        
        self._drag_start_position = None
        self.designer = None  # Reference to the DiagramDesigner
        
        # Find the DiagramDesigner parent
        self.find_designer_parent()
        
        # Connect the clicked signal
        self.clicked.connect(self.on_clicked)
    
    def find_designer_parent(self):
        """Find the DiagramDesigner parent to access the canvas and selected elements"""
        parent = self.parent()
        while parent and not isinstance(parent, DiagramDesigner):
            parent = parent.parent()
        
        if parent and isinstance(parent, DiagramDesigner):
            self.designer = parent
    
    def on_clicked(self):
        """Handle click events - change shape if element is selected"""
        if self.element_type in ["new", "save", "export"]:
            # Handle special buttons normally
            return
            
        if self.designer and self.designer.canvas and self.designer.canvas.selected_elements:
            # If an element is selected, change its shape
            self.change_element_shape(self.element_type)
    
    def change_element_shape(self, shape_type):
        """Change the shape of the currently selected element"""
        if not self.designer or not self.designer.canvas or not self.designer.canvas.selected_elements:
            return  # No element selected
            
        canvas = self.designer.canvas
        selected_element = canvas.selected_elements[0]
        
        # Store the current properties
        x, y = selected_element.x, selected_element.y
        width, height = selected_element.width, selected_element.height
        label = selected_element.label
        
        # Create a new element of the desired type
        new_element = None
        if shape_type == "box":
            new_element = BoxElement(x, y, width, height, label)
        elif shape_type == "circle":
            new_element = CircleElement(x, y, width, height, label)
        elif shape_type == "diamond":
            new_element = DiamondElement(x, y, width, height, label)
        elif shape_type == "hexagon":
            new_element = HexagonElement(x, y, width, height, label)
        
        if new_element:
            # Copy color properties
            new_element.color = selected_element.color
            new_element.border_color = selected_element.border_color
            
            # Preserve parent-child relationships
            new_element.parent = selected_element.parent
            new_element.children = selected_element.children
            new_element.container_title = selected_element.container_title
            
            # Update parent's reference to this element if it has a parent
            if new_element.parent:
                parent_element = new_element.parent
                if selected_element in parent_element.children:
                    parent_index = parent_element.children.index(selected_element)
                    parent_element.children[parent_index] = new_element
            
            # Update children's parent reference to the new element
            for child in new_element.children:
                child.parent = new_element
            
            # Replace the old element with the new one
            index = canvas.elements.index(selected_element)
            
            # Update connections to point to the new element
            for conn in canvas.connections[:]:
                if conn.source == selected_element:
                    conn.source = new_element
                if conn.target == selected_element:
                    conn.target = new_element
            
            # Replace the element in the list
            canvas.elements[index] = new_element
            
            # Update selection
            canvas.selected_elements = [new_element]
            
            # Signal that the diagram has changed
            canvas.diagram_changed.emit()
            
            # Update the properties panel
            self.designer.show_element_properties(new_element)
            
            # Trigger a redraw and update the D2 code
            canvas.update()
            self.designer.update_d2_code()
    
    def createCustomIcon(self, element_type):
        pixmap = QPixmap(40, 40)  # Double size (from 20x20 to 40x40)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        
        # Use white color for icons instead of DARK_TEXT
        icon_color = QColor(220, 220, 220)  # Light color for better visibility on dark background
        
        if element_type == "box":
            # Draw a rectangle
            painter.setPen(QPen(icon_color, 3))  # Double line width (from 1.5 to 3)
            painter.setBrush(QBrush(QColor(80, 80, 80)))
            painter.drawRect(4, 4, 32, 32)  # Double size (from 2,2,16,16 to 4,4,32,32)
        elif element_type == "circle":
            # Draw a circle
            painter.setPen(QPen(icon_color, 3))  # Double line width (from 1.5 to 3)
            painter.setBrush(QBrush(QColor(80, 80, 80)))
            painter.drawEllipse(4, 4, 32, 32)  # Double size (from 2,2,16,16 to 4,4,32,32)
        elif element_type == "diamond":
            # Draw a diamond
            painter.setPen(QPen(icon_color, 3))  # Double line width (from 1.5 to 3)
            painter.setBrush(QBrush(QColor(80, 80, 80)))
            path = QPainterPath()
            path.moveTo(20, 4)    # Top point (double from 10,2)
            path.lineTo(36, 20)   # Right point (double from 18,10)
            path.lineTo(20, 36)   # Bottom point (double from 10,18)
            path.lineTo(4, 20)    # Left point (double from 2,10)
            path.closeSubpath()
            painter.drawPath(path)
        elif element_type == "hexagon":
            # Draw a hexagon
            painter.setPen(QPen(icon_color, 3))  # Double line width (from 1.5 to 3)
            painter.setBrush(QBrush(QColor(80, 80, 80)))
            path = QPainterPath()
            path.moveTo(10, 4)    # Top left (double from 5,2)
            path.lineTo(30, 4)    # Top right (double from 15,2)
            path.lineTo(36, 20)   # Middle right (double from 18,10)
            path.lineTo(30, 36)   # Bottom right (double from 15,18)
            path.lineTo(10, 36)   # Bottom left (double from 5,18)
            path.lineTo(4, 20)    # Middle left (double from 2,10)
            path.closeSubpath()
            painter.drawPath(path)
        elif element_type == "new":
            # Draw a new document icon
            painter.setPen(QPen(icon_color, 3))  # Double line width (from 1.5 to 3)
            painter.drawRect(8, 8, 24, 24)      # Double size (from 4,4,12,12 to 8,8,24,24)
            painter.drawLine(16, 16, 24, 16)    # Double position (from 8,8,12,8 to 16,16,24,16)
            painter.drawLine(20, 12, 20, 20)    # Double position (from 10,6,10,10 to 20,12,20,20)
        
        painter.end()
        self.setIcon(QIcon(pixmap))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.element_type != "new":
            # Always store the drag start position for potential drag operations
            self._drag_start_position = event.pos()
            # Don't call super().mousePressEvent here to avoid triggering the click immediately
            # The click will be handled in mouseReleaseEvent if no drag occurs
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.element_type == "new":
            return  # Don't allow dragging for the new button
            
        if not (event.buttons() & Qt.LeftButton) or not self._drag_start_position:
            return
            
        # Only start drag if the mouse has moved far enough
        distance = (event.pos() - self._drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
            
        try:
            # Create the drag object
            drag = QDrag(self)
            mime_data = QMimeData()
            
            # Set the element type as plain text
            mime_data.setText(self.element_type)
            drag.setMimeData(mime_data)
            
            # Create pixmap for drag visual feedback
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)
            
            # Execute the drag operation
            print(f"Starting drag for element type: {self.element_type}")
            result = drag.exec_(Qt.CopyAction)
            print(f"Drag result: {result}")
            
            # Clear the drag start position
            self._drag_start_position = None
            
        except Exception as e:
            print(f"Error during drag: {str(e)}")
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.element_type != "new":
            # If we have a drag start position and the mouse hasn't moved much,
            # this is a click (not a drag)
            if self._drag_start_position:
                distance = (event.pos() - self._drag_start_position).manhattanLength()
                if distance < QApplication.startDragDistance():
                    # This was a click, not a drag - handle it as a click
                    self.clicked.emit()
                
                # Clear the drag start position
                self._drag_start_position = None
        
        super().mouseReleaseEvent(event)


class ElementPropertiesDialog(QDialog):
    """Dialog for editing element properties"""
    def __init__(self, element, canvas=None, parent=None):
        super().__init__(parent)
        self.element = element
        self.canvas = canvas
        self.setWindowTitle("Element Properties")
        
        # Define bright color palette with vibrant UI colors
        self.color_palette = [
            QColor(100, 181, 246),  # Bright Blue
            QColor(129, 199, 132),  # Bright Green
            QColor(255, 183, 77),   # Bright Orange
            QColor(255, 112, 67),   # Bright Red-Orange
            QColor(255, 241, 118),  # Bright Yellow
            QColor(180, 180, 180),  # Light Gray (matches default)
            
            QColor(158, 158, 158),  # Medium Gray
            QColor(189, 189, 189),  # Silver
            
            QColor(149, 117, 205),  # Bright Purple
            QColor(255, 138, 101),  # Bright Coral
            QColor(240, 98, 146),   # Bright Pink
            QColor(77, 208, 225),   # Bright Teal
            
            QColor(120, 144, 156),  # Blue Gray
            QColor(84, 110, 122),   # Darker Blue Gray
            
            QColor(55, 71, 79),     # Near Black
            QColor(244, 67, 54)     # Bright Red
        ]
        
        self.setup_ui()
        
        # Apply dark mode to dialog
        self.setStyleSheet("""
            QDialog { 
                background-color: #1a1a1a; 
                color: #e0e0e0; 
                border: 1px solid #333333;
            }
            QLabel { 
                color: #e0e0e0; 
            }
            QLineEdit { 
                background-color: #2d2d2d; 
                color: #e0e0e0; 
                border: 1px solid #3c3c3c; 
                border-radius: 4px;
                padding: 5px; 
                selection-background-color: #2c5aa0;
            }
            QLineEdit:focus {
                border: 1px solid #3a6ea5;
            }
            QGroupBox {
                font-weight: bold;
                color: #e0e0e0;
            }
            QPushButton {
                color: #e0e0e0;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 8px;
                background: #2a2a2a;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00BFFF;
                border: 1px solid #00BFFF;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #33CCFF;
            }
            QSlider::sub-page:horizontal {
                background: #3a6ea5;
                border: 1px solid #555555;
                height: 8px;
                border-radius: 4px;
            }
        """)
        
    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Label field
        self.label_edit = QLineEdit(self.element.label)
        layout.addRow("Label:", self.label_edit)
        
        # Color palette
        color_group_box = QGroupBox("Color")
        color_group_box.setStyleSheet("QGroupBox { color: #e0e0e0; border: 1px solid #646464; margin-top: 10px; padding-top: 15px; }")
        color_layout = QGridLayout(color_group_box)
        color_layout.setSpacing(6)  # Increased spacing between color buttons
        
        # Create a dark background for the color palette
        color_palette_bg = QWidget()
        color_palette_bg.setStyleSheet("background-color: #1e1e1e; border-radius: 4px;")
        color_palette_layout = QGridLayout(color_palette_bg)
        color_palette_layout.setContentsMargins(8, 8, 8, 8)  # Add padding around the color swatches
        color_palette_layout.setSpacing(6)  # Spacing between color buttons
        
        # Create color swatches
        self.color_buttons = []
        row, col = 0, 0
        for i, color in enumerate(self.color_palette):
            color_button = QPushButton()
            color_button.setFixedSize(32, 32)  # Slightly larger color buttons
            color_button.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 1px solid #646464; border-radius: 4px;")
            color_button.clicked.connect(lambda checked, c=color: self.select_color(c))
            color_palette_layout.addWidget(color_button, row, col)
            self.color_buttons.append(color_button)
            
            col += 1
            if col > 3:  # 4 colors per row
                col = 0
                row += 1
        
        # Add the color palette background to the main color layout
        color_layout.addWidget(color_palette_bg, 0, 0)
        
        # Add custom color button with improved styling
        custom_color_button = QPushButton("Custom Color...")
        custom_color_button.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #646464;
                border-radius: 4px;
                padding: 8px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        custom_color_button.clicked.connect(self.choose_custom_color)
        color_layout.addWidget(custom_color_button, 1, 0)
        
        layout.addRow("", color_group_box)
        
        # Size sliders with value labels
        size_group_box = QGroupBox("Size")
        size_group_box.setStyleSheet("QGroupBox { color: #e0e0e0; border: 1px solid #646464; margin-top: 10px; padding-top: 15px; }")
        size_layout = QVBoxLayout(size_group_box)
        size_layout.setContentsMargins(10, 15, 10, 10)  # Add more padding
        
        # Create a dark background for the sliders
        slider_bg = QWidget()
        slider_bg.setStyleSheet("background-color: #1e1e1e; border-radius: 4px; padding: 5px;")
        slider_layout = QVBoxLayout(slider_bg)
        slider_layout.setContentsMargins(10, 10, 10, 10)
        
        # Width slider
        width_layout = QHBoxLayout()
        width_label = QLabel("Width:")
        width_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setMinimum(20)  # Minimum width
        self.width_slider.setMaximum(300)  # Maximum width
        self.width_slider.setValue(self.element.width)
        self.width_slider.setTickInterval(15)  # 5% of range (300-20)
        self.width_slider.setTickPosition(QSlider.TicksBelow)
        self.width_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 8px;
                background: #2a2a2a;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00BFFF;
                border: 1px solid #00BFFF;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #33CCFF;
            }
            QSlider::sub-page:horizontal {
                background: #3a6ea5;
                border: 1px solid #555555;
                height: 8px;
                border-radius: 4px;
            }
        """)
        self.width_value_label = QLabel(f"{self.element.width}px")
        self.width_value_label.setStyleSheet("color: #e0e0e0; min-width: 45px; font-weight: bold;")
        self.width_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.width_slider.valueChanged.connect(self.update_width_label)
        
        width_layout.addWidget(width_label)
        width_layout.addWidget(self.width_slider)
        width_layout.addWidget(self.width_value_label)
        slider_layout.addLayout(width_layout)
        
        # Add a small spacer between sliders
        spacer = QFrame()
        spacer.setFrameShape(QFrame.HLine)
        spacer.setFrameShadow(QFrame.Sunken)
        spacer.setStyleSheet("background-color: #333333; max-height: 1px;")
        slider_layout.addWidget(spacer)
        
        # Height slider
        height_layout = QHBoxLayout()
        height_label = QLabel("Height:")
        height_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setMinimum(20)  # Minimum height
        self.height_slider.setMaximum(300)  # Maximum height
        self.height_slider.setValue(self.element.height)
        self.height_slider.setTickInterval(15)  # 5% of range (300-20)
        self.height_slider.setTickPosition(QSlider.TicksBelow)
        self.height_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 8px;
                background: #2a2a2a;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00BFFF;
                border: 1px solid #00BFFF;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #33CCFF;
            }
            QSlider::sub-page:horizontal {
                background: #3a6ea5;
                border: 1px solid #555555;
                height: 8px;
                border-radius: 4px;
            }
        """)
        self.height_value_label = QLabel(f"{self.element.height}px")
        self.height_value_label.setStyleSheet("color: #e0e0e0; min-width: 45px; font-weight: bold;")
        self.height_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.height_slider.valueChanged.connect(self.update_height_label)
        
        height_layout.addWidget(height_label)
        height_layout.addWidget(self.height_slider)
        height_layout.addWidget(self.height_value_label)
        slider_layout.addLayout(height_layout)
        
        # Add the slider background to the main size layout
        size_layout.addWidget(slider_bg)
        
        layout.addRow("", size_group_box)
        
        # OK/Cancel buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 10, 0, 0)  # Add top margin
        
        ok_button = QPushButton("OK")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #2c5aa0;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a6ea5;
            }
            QPushButton:pressed {
                background-color: #1c4a90;
            }
        """)
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(ok_button)
        
        layout.addRow("", buttons_layout)
    
    def update_width_label(self, value):
        self.width_value_label.setText(f"{value}px")
    
    def update_height_label(self, value):
        self.height_value_label.setText(f"{value}px")
    
    def select_color(self, color):
        self.element.color = color
        # Highlight the selected color button with a bright cyan border for better visibility in dark mode
        for button in self.color_buttons:
            button_color = button.palette().button().color()
            if button_color == color:
                button.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 3px solid #00FFFF; border-radius: 4px;")
            else:
                button.setStyleSheet(f"background-color: rgb({button_color.red()}, {button_color.green()}, {button_color.blue()}); border: 1px solid #646464; border-radius: 4px;")
    
    def choose_custom_color(self):
        color = QColorDialog.getColor(self.element.color, self)
        if color.isValid():
            self.element.color = color
    
    def accept(self):
        # Apply the changes
        if self.element:
            old_label = self.element.label
            new_label = self.label_edit.text()
            
            # Update the element properties
            self.element.label = new_label
            self.element.color = self.color_button.color
            
            # If the label changed, recalculate the element size
            if old_label != new_label:
                # Calculate minimum size based on new text
                min_width, min_height = self.element._calculate_min_size_for_text(new_label)
                
                # Use the larger of the current size or the minimum required size
                self.element.width = max(self.element.width, min_width)
                self.element.height = max(self.element.height, min_height)
            
            # Notify that properties have changed
            if self.canvas:
                self.canvas.diagram_changed.emit()
                self.canvas.update()
        
        # Close the dialog
        super().accept()


class DiagramCanvas(QWidget):
    """Widget for drawing and interacting with the diagram"""
    diagram_changed = pyqtSignal()
    element_selected = pyqtSignal(object)  # Signal to notify when an element is selected for editing
    
    # Constants
    ELEMENT_PADDING = 10  # Padding around elements to prevent overlap
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.elements = []  # List of diagram elements
        self.connections = []  # List of connections between elements
        self.selected_elements = []  # List of currently selected elements
        self.selected_connections = []  # List of currently selected connections
        self.setMouseTracking(True)  # Enable mouse tracking for hover effects
        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard focus
        
        # Initialize variables for dragging
        self.dragging = False
        self.drag_start = None
        self.drag_element = None
        self.last_mouse_pos = QPoint(0, 0)
        
        # Initialize variables for selection rectangle
        self.selecting = False
        self.selection_start = QPoint(0, 0)
        self.selection_rect = None
        self.selection_rect_active = False
        
        # Initialize variables for connection creation
        self.creating_connection = False
        self.connection_source = None
        self.connection_just_created = False
        self.connection_creation_time = QTime.currentTime()
        self.connection_drag = False
        
        # Initialize variables for nesting
        self.creating_nesting = False
        self.nesting_parent = None
        self.nesting_drag = False
        
        # Initialize variables for cutting
        self.cutting = False
        self.cut_start = None
        self.cut_current = None
        
        # Initialize variables for zoom and pan
        self.scale_factor = 1.0
        self.min_scale = 0.2  # Minimum zoom level
        self.max_scale = 5.0  # Maximum zoom level
        self.pan_offset = QPoint(0, 0)
        self.panning = False
        self.pan_start = QPoint(0, 0)
        
        # Set a dark background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(40, 40, 40))
        self.setPalette(palette)
        
        print("DiagramCanvas initialized")
        
        # Set up the widget
        self.setMinimumSize(800, 600)
        self.setAcceptDrops(True)  # Enable drop events
        
        # Create context menu - only for connections, not for creating connections
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        
        # Initialize zoom and pan attributes
        print("DiagramCanvas initialized")
    
    def contextMenuEvent(self, event):
        # Check if we just created a connection (within the last 1000ms)
        if self.connection_just_created:
            current_time = QTime.currentTime()
            if self.connection_creation_time.msecsTo(current_time) < 1000:  # Increased from 500ms to 1000ms
                # Prevent context menu from appearing
                event.accept()
                return
            else:
                # Reset the flag if enough time has passed
                self.connection_just_created = False
        
        # Transform mouse position to account for zoom and pan
        scene_pos = self.transform_point_to_scene(event.pos())
        
        # Check if we clicked on an element
        clicked_element = None
        for element in reversed(self.elements):
            if element.contains(scene_pos):
                clicked_element = element
                break
                
        if clicked_element:
            # Create element context menu
            menu = QMenu(self)
            
            # If the element is a child (has a parent), add option to disconnect
            if clicked_element.parent:
                disconnect_action = QAction("Disconnect from Parent", self)
                disconnect_action.triggered.connect(lambda: self.disconnect_from_parent(clicked_element))
                menu.addAction(disconnect_action)
                
                menu.exec_(event.globalPos())
                event.accept()
                return
            
            # If no special actions, start connection creation
            self.creating_connection = True
            self.connection_source = clicked_element
            self.update()
            event.accept()
            return
        
        # Find if we clicked on a connection
        clicked_connection = None
        for connection in self.connections:
            # Check if click is near the connection line
            source_center = QPoint(connection.source.x + connection.source.width//2, 
                                  connection.source.y + connection.source.height//2)
            target_center = QPoint(connection.target.x + connection.target.width//2, 
                                  connection.target.y + connection.target.height//2)
            
            # Calculate distance from click to line
            distance = self._point_to_line_distance(scene_pos, source_center, target_center)
            
            if distance < 10:  # 10 pixels threshold
                clicked_connection = connection
                break
        
        if clicked_connection:
            # Create connection context menu
            menu = QMenu(self)
            
            # Add actions for connection
            edit_label_action = QAction("Edit Label", self)
            edit_label_action.triggered.connect(lambda: self.edit_connection_label(clicked_connection))
            menu.addAction(edit_label_action)
            
            # Add option to create reverse connection
            create_reverse_action = QAction("Create Reverse Connection", self)
            create_reverse_action.triggered.connect(lambda: self.create_reverse_connection(clicked_connection))
            menu.addAction(create_reverse_action)
            
            # Delete connection
            delete_action = QAction("Delete Connection", self)
            delete_action.triggered.connect(lambda: self.delete_connection(clicked_connection))
            menu.addAction(delete_action)
            
            menu.exec_(event.globalPos())
            event.accept()
            return
        
        # Let the right-click event pass through for other purposes
        event.ignore()
    
    def disconnect_from_parent(self, element):
        """Disconnect an element from its parent"""
        if element.parent:
            parent = element.parent
            # Remove from parent's children list
            parent.children.remove(element)
            # Clear the parent reference
            element.parent = None
            print(f"Disconnected {element.label} from parent {parent.label}")
            self.diagram_changed.emit()
            self.update()
    
    def edit_connection_label(self, connection):
        """Edit the label of a connection"""
        text, ok = QInputDialog.getText(self, "Connection Label", "Enter label:", 
                                     QLineEdit.Normal, connection.label)
        if ok:
            connection.label = text
            self.diagram_changed.emit()
            self.update()
    
    def create_reverse_connection(self, connection):
        """Create a reverse connection"""
        # Check if a connection already exists in the opposite direction
        existing_reverse_connection = None
        for conn in self.connections:
            if conn.source == connection.target and conn.target == connection.source:
                existing_reverse_connection = conn
                break
        
        if existing_reverse_connection:
            # Connection already exists
            print(f"Connection already exists between {connection.target.label} and {connection.source.label}")
        else:
            # Create new reverse connection
            reverse_connection = ArrowConnection(connection.target, connection.source)
            self.connections.append(reverse_connection)
            print(f"Created reverse connection from {connection.target.label} to {connection.source.label}")
        
        # Ensure we emit the signal to update the D2 code
        self.diagram_changed.emit()
        self.update()
    
    def delete_connection(self, connection):
        """Delete a connection"""
        if connection in self.connections:
            self.connections.remove(connection)
            self.diagram_changed.emit()
            self.update()
    
    def _point_to_line_distance(self, point, line_start, line_end):
        """Calculate the distance from a point to a line segment"""
        # Extract coordinates
        px, py = point.x(), point.y()
        ax, ay = line_start.x(), line_start.y()
        bx, by = line_end.x(), line_end.y()
        
        # Calculate the squared length of the line segment
        ab_squared = (bx - ax) ** 2 + (by - ay) ** 2
        
        if ab_squared == 0:
            # Line segment is actually a point
            return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)
        
        # Calculate the projection parameter t
        t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ab_squared
        
        if t < 0:
            # Closest point is line_start
            return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)
        elif t > 1:
            # Closest point is line_end
            return math.sqrt((px - bx) ** 2 + (py - by) ** 2)
        else:
            # Closest point is on the line segment
            projection_x = ax + t * (bx - ax)
            projection_y = ay + t * (by - ay)
            return math.sqrt((px - projection_x) ** 2 + (py - projection_y) ** 2)
    
    def _would_create_circular_nesting(self, parent, child):
        """Check if creating a nesting relationship would create a circular reference"""
        # If the child is already a parent of the parent, it would create a circular reference
        current = parent
        while current:
            if current == child:
                return True
            current = current.parent
        return False
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        if event.mimeData().hasText():
            element_type = event.mimeData().text()
            
            # Transform drop position to account for zoom and pan
            scene_pos = self.transform_point_to_scene(event.pos())
            
            # Save state for undo before adding the element
            parent_window = self.window()
            if isinstance(parent_window, DiagramDesigner):
                parent_window.save_state()
            
            # Create a new element based on the type
            new_element = None
            if element_type == "box":
                # Create with default size - the constructor will adjust based on text
                new_element = BoxElement(scene_pos.x() - 50, scene_pos.y() - 30)
            elif element_type == "circle":
                new_element = CircleElement(scene_pos.x() - 40, scene_pos.y() - 40)
            elif element_type == "diamond":
                new_element = DiamondElement(scene_pos.x() - 50, scene_pos.y() - 40)
            elif element_type == "hexagon":
                new_element = HexagonElement(scene_pos.x() - 50, scene_pos.y() - 40)
            
            if new_element:
                # Center the element at the drop position after its size has been calculated
                new_element.x = scene_pos.x() - new_element.width // 2
                new_element.y = scene_pos.y() - new_element.height // 2
                
                # Check if the new element would overlap with any existing elements
                overlap_detected = False
                
                for element in self.elements:
                    if new_element.overlaps_with(element, self.ELEMENT_PADDING):
                        overlap_detected = True
                        break
                
                if overlap_detected:
                    # Find the nearest valid position
                    valid_position = self.find_nearest_valid_position(new_element)
                    
                    if valid_position:
                        # Update the element's position to the valid position
                        new_element.x, new_element.y = valid_position
                        print(f"Element repositioned to nearest valid position: ({new_element.x}, {new_element.y})")
                    else:
                        # No valid position found, don't add the element
                        print("No valid position found for the element")
                        return
                
                # Add the element to the canvas
                self.elements.append(new_element)
                
                # Clear previous selection
                self.selected_elements.clear()
                self.selected_connections.clear()
                
                # Select the new element
                self.selected_elements.append(new_element)
                
                # Show properties for the new element
                self.element_selected.emit(new_element)
                
                # Emit signal to update D2 code
                self.diagram_changed.emit()
                
                # Update the canvas
                self.update()
                
                # Print debug info
                print(f"Created new {element_type} element at ({new_element.x}, {new_element.y})")
                
                # Accept the drop event
                event.acceptProposedAction()
                
                # Return success
                return 1
            
            # If we get here, no element was created
            return 0
    
    def find_nearest_valid_position(self, element, max_distance=300):
        """
        Find the nearest valid position for an element that doesn't overlap with existing elements.
        Uses a spiral search pattern to find the closest valid position.
        
        Args:
            element: The element to position
            max_distance: Maximum search distance in pixels
            
        Returns:
            (x, y) tuple of the nearest valid position, or None if no valid position found
        """
        # Start with the element's current position
        original_x, original_y = element.x, element.y
        
        # Try the original position first
        overlap = False
        for existing_element in self.elements:
            if element.overlaps_with(existing_element, self.ELEMENT_PADDING):
                overlap = True
                break
                
        if not overlap:
            return original_x, original_y
        
        # Spiral search pattern
        # Start with a small step and increase gradually
        step_size = max(element.width, element.height) // 2
        max_steps = max_distance // step_size
        
        # Search in a spiral pattern (right, down, left, up, and repeat with increasing distance)
        directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # right, down, left, up
        
        for distance in range(1, max_steps + 1):
            for direction in directions:
                # Try multiple positions in each direction
                for step in range(distance):
                    # Calculate new position
                    test_x = original_x + direction[0] * step_size * distance
                    test_y = original_y + direction[1] * step_size * distance
                    
                    # Update element position temporarily
                    element.x = test_x
                    element.y = test_y
                    
                    # Check for overlaps
                    overlap = False
                    for existing_element in self.elements:
                        if element.overlaps_with(existing_element, self.ELEMENT_PADDING):
                            overlap = True
                            break
                    
                    if not overlap:
                        return test_x, test_y
        
        # If we get here, no valid position was found within the max distance
        # Reset the element's position
        element.x = original_x
        element.y = original_y
        return None
    
    def mousePressEvent(self, event):
        # Handle middle mouse button for zoom-to-fit
        if event.button() == Qt.MiddleButton:
            # Single click to zoom to fit
            self.zoom_to_fit()
            return
            
        # Transform mouse position to account for zoom and pan
        scene_pos = self.transform_point_to_scene(event.pos())
            
        if event.button() == Qt.LeftButton:
            # Check if clicking on an element
            clicked_element = None
            for element in reversed(self.elements):
                if element.contains(scene_pos):
                    clicked_element = element
                    break
            
            # Check if clicking on a connection
            clicked_connection = None
            if not clicked_element:
                for connection in self.connections:
                    source_center = QPoint(connection.source.x + connection.source.width//2, 
                                          connection.source.y + connection.source.height//2)
                    target_center = QPoint(connection.target.x + connection.target.width//2, 
                                          connection.target.y + connection.target.height//2)
                    
                    # Calculate distance from click to line
                    distance = self._point_to_line_distance(scene_pos, source_center, target_center)
                    
                    if distance < 10:  # 10 pixels threshold for selection
                        clicked_connection = connection
                        break
            
            # Handle Alt + left mouse button for cutting connections
            if event.modifiers() & Qt.AltModifier:
                self.cutting = True
                self.cut_start = scene_pos
                self.cut_current = scene_pos
                self.setCursor(Qt.CrossCursor)  # Set cursor to cross for cutting
                return
            
            if clicked_element:
                # Start dragging the element
                self.dragging = True
                self.drag_element = clicked_element
                self.drag_start = scene_pos
                
                # Check if we're clicking on a selected element
                if clicked_element in self.selected_elements:
                    # If Shift is not pressed, keep the current selection
                    pass
                else:
                    # If Shift is not pressed, clear the current selection
                    if not (event.modifiers() & Qt.ShiftModifier):
                        self.selected_elements.clear()
                    
                    # Add the clicked element to the selection
                    self.selected_elements.append(clicked_element)
                    
                    # Emit signal to notify that an element is selected
                    self.element_selected.emit(clicked_element)
                
                # Update the canvas
                self.update()
            elif clicked_connection:
                # Select the connection
                if not (event.modifiers() & Qt.ShiftModifier):
                    self.selected_connections.clear()
                    self.selected_elements.clear()
                
                self.selected_connections.append(clicked_connection)
                
                # Update the canvas
                self.update()
            else:
                # Clicking in empty space
                
                # Start panning if no element or connection was clicked
                self.panning = True
                self.pan_start = event.pos()
                self.setCursor(Qt.OpenHandCursor)  # Set cursor to open hand for panning
                
                # If Shift is not pressed, clear the current selection
                if not (event.modifiers() & Qt.ShiftModifier):
                    self.selected_elements.clear()
                    self.selected_connections.clear()
                    
                    # Emit signal to notify that no element is selected
                    self.element_selected.emit(None)
                
                # Update the canvas
                self.update()
        elif event.button() == Qt.RightButton:
            # Check if clicking on an element
            clicked_element = None
            for element in reversed(self.elements):
                if element.contains(scene_pos):
                    clicked_element = element
                    break
            
            if clicked_element:
                # Check if Alt key is pressed for nesting operation
                if event.modifiers() & Qt.AltModifier:
                    # Start creating a nesting relationship via dragging
                    self.creating_nesting = True
                    self.nesting_parent = clicked_element
                    self.nesting_drag = True  # Flag to indicate we're creating nesting by dragging
                    print(f"Starting nesting drag from parent: {clicked_element.label}")
                    self.update()
                else:
                    # Standard connection creation
                    self.creating_connection = True
                    self.connection_source = clicked_element
                    self.connection_drag = True  # Flag to indicate we're creating by dragging
                    print(f"Starting connection drag from element: {clicked_element.label}")
                    self.update()
            else:
                # Right-clicking in empty space - start selection rectangle
                self.selecting = True
                self.selection_start = event.pos()
                self.selection_rect = None
                self.selection_rect_active = False
                
                # If Shift is not pressed, clear the current selection
                if not (event.modifiers() & Qt.ShiftModifier):
                    self.selected_elements.clear()
                    self.selected_connections.clear()
                    
                    # Emit signal to notify that no element is selected
                    self.element_selected.emit(None)
                
                # Update the canvas
                self.update()
    
    def mouseMoveEvent(self, event):
        # Always update the last_mouse_pos for connection drawing and other interactions
        self.last_mouse_pos = self.transform_point_to_scene(event.pos())
        
        # Force update for all interactions
        need_update = False
        need_repaint = False  # For operations that need immediate visual feedback
        
        # Handle cutting with Alt + left mouse button
        if self.cutting and event.buttons() & Qt.LeftButton:
            # Update the current position of the cutting line
            self.cut_current = self.last_mouse_pos
            need_update = True
            
        # Handle panning with left mouse button in empty space
        elif self.panning and event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.pan_start
            self.pan_offset += delta
            self.pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)  # Change cursor to closed hand during active panning
            need_repaint = True  # Use repaint for immediate visual feedback
            
        # Handle connection creation with right mouse button
        elif self.creating_connection and event.buttons() & Qt.RightButton:
            # Just update to redraw the temporary connection line
            need_repaint = True  # Use repaint for immediate visual feedback
            
        # Handle nesting creation with Alt + right mouse button
        elif self.creating_nesting and event.buttons() & Qt.RightButton:
            # Just update to redraw the temporary nesting line
            need_repaint = True  # Use repaint for immediate visual feedback
            
        # Handle dragging elements
        elif self.dragging and self.drag_element and (event.buttons() & Qt.LeftButton):
            # Calculate the movement delta
            delta = self.last_mouse_pos - self.drag_start
            
            # Determine which elements to move
            elements_to_move = []
            if self.drag_element in self.selected_elements and len(self.selected_elements) > 1:
                # If dragging a selected element and multiple elements are selected,
                # move all selected elements
                elements_to_move = self.selected_elements
            else:
                # Otherwise just move the dragged element
                elements_to_move = [self.drag_element]
            
            # Store original positions to revert if needed
            original_positions = [(element, element.x, element.y) for element in elements_to_move]
            
            # Temporarily move all elements
            for element in elements_to_move:
                element.move(delta.x(), delta.y())
            
            # Check for overlap with other elements
            overlap_detected = False
            
            for moving_element in elements_to_move:
                for element in self.elements:
                    # Skip elements being moved and their children
                    if element in elements_to_move or element in moving_element.children:
                        continue
                    
                    # Skip if the element is a child of the current element
                    if element.parent == moving_element:
                        continue
                        
                    # Check if the moved element overlaps with this element
                    if moving_element.overlaps_with(element, self.ELEMENT_PADDING):
                        overlap_detected = True
                        break
                
                if overlap_detected:
                    break
            
            # If overlap detected, revert to original positions
            if overlap_detected:
                for element, orig_x, orig_y in original_positions:
                    element.x = orig_x
                    element.y = orig_y
                # Don't update drag_start here, so the elements can still be dragged
                # from their original positions in a different direction
            else:
                # Update the drag start position only if the move was successful
                self.drag_start = self.last_mouse_pos
            
            need_repaint = True  # Use repaint for immediate visual feedback
            
        # Handle selection rectangle with right mouse button
        elif hasattr(self, 'selecting') and self.selecting and (event.buttons() & Qt.RightButton):
            # Update selection rectangle
            current_pos = event.pos()
            self.selection_rect = QRect(self.selection_start, current_pos).normalized()
            self.selection_rect_active = True
            need_repaint = True  # Use repaint for immediate visual feedback
        
        # Always update the canvas if any interaction is happening
        if need_repaint:
            # Use repaint for immediate visual feedback
            self.repaint()
        elif need_update or event.buttons():
            # Use update for less critical updates
            self.update()
        
        event.accept()
    
    def mouseReleaseEvent(self, event):
        # Handle left mouse button release
        if event.button() == Qt.LeftButton:
            # Check if we were in cutting mode
            if self.cutting:
                # Find connections that intersect with the cutting line
                intersected_connections = self.find_intersected_connections(self.cut_start, self.cut_current)
                
                if intersected_connections:
                    # Save the current state for undo
                    parent_window = self.window()
                    if isinstance(parent_window, DiagramDesigner):
                        parent_window.save_state()
                    
                    # Remove the intersected connections
                    for connection in intersected_connections:
                        self.connections.remove(connection)
                    
                    # Emit signal to update D2 code
                    self.diagram_changed.emit()
                
                # Reset cutting mode
                self.cutting = False
                self.cut_start = None
                self.cut_current = None
                self.setCursor(Qt.ArrowCursor)
                self.update()
            
            # Check if we were panning
            elif self.panning:
                self.panning = False
                self.setCursor(Qt.ArrowCursor)
            
            # Check if we were dragging an element
            elif self.drag_element:
                # Save the current state for undo
                parent_window = self.window()
                if isinstance(parent_window, DiagramDesigner):
                    parent_window.save_state()
                
                # Reset drag element
                self.drag_element = None
                self.drag_start = None
                self.setCursor(Qt.ArrowCursor)
                
                # Emit signal to update D2 code
                self.diagram_changed.emit()

        elif event.button() == Qt.RightButton:
            # Handle selection rectangle with right mouse button
            if hasattr(self, 'selecting') and self.selecting:
                self.selecting = False
                
                # Transform selection rectangle to scene coordinates
                if self.selection_rect:
                    # Find elements within the selection rectangle
                    for element in self.elements:
                        element_rect = QRect(
                            self.transform_point_from_scene(QPoint(element.x, element.y)),
                            self.transform_point_from_scene(QPoint(element.x + element.width, element.y + element.height))
                        ).normalized()
                        
                        if self.selection_rect.intersects(element_rect):
                            if element not in self.selected_elements:
                                self.selected_elements.append(element)
                    
                    # Find connections within the selection rectangle
                    for connection in self.connections:
                        source_center = QPoint(
                            connection.source.x + connection.source.width//2,
                            connection.source.y + connection.source.height//2
                        )
                        target_center = QPoint(
                            connection.target.x + connection.target.width//2,
                            connection.target.y + connection.target.height//2
                        )
                        
                        source_screen = self.transform_point_from_scene(source_center)
                        target_screen = self.transform_point_from_scene(target_center)
                        
                        # Check if either endpoint is within the selection rectangle
                        if (self.selection_rect.contains(source_screen) or 
                            self.selection_rect.contains(target_screen)):
                            if connection not in self.selected_connections:
                                self.selected_connections.append(connection)
                
                # Clear selection rectangle
                self.selection_rect = None
                self.selection_rect_active = False
                
                # Show properties for the first selected element
                if self.selected_elements:
                    self.element_selected.emit(self.selected_elements[0])
                
                # Update the canvas
                self.update()
                return
                
            # Check if we were creating a nesting relationship with Alt+Right-click
            if self.creating_nesting and hasattr(self, 'nesting_drag') and self.nesting_drag:
                # Transform mouse position to account for zoom and pan
                scene_pos = self.transform_point_to_scene(event.pos())
                
                # Check if releasing over an element
                child_element = None
                for element in reversed(self.elements):
                    if element.contains(scene_pos):
                        child_element = element
                        break
                
                if child_element and child_element != self.nesting_parent:
                    # Check if this would create a circular nesting
                    if self._would_create_circular_nesting(self.nesting_parent, child_element):
                        print(f"Cannot nest {child_element.label} inside {self.nesting_parent.label} - would create circular nesting")
                    else:
                        # Remove from previous parent if exists
                        if child_element.parent:
                            child_element.parent.children.remove(child_element)
                        
                        # Create nesting relationship
                        child_element.parent = self.nesting_parent
                        self.nesting_parent.children.append(child_element)
                        print(f"Nested {child_element.label} inside {self.nesting_parent.label}")
                        self.diagram_changed.emit()
                        
                        # Set the flag to prevent context menu
                        self.connection_just_created = True
                        self.connection_creation_time = QTime.currentTime()
                else:
                    print("Nesting operation cancelled - no child element or same as parent")
                
                # Reset nesting creation state
                self.creating_nesting = False
                self.nesting_parent = None
                self.nesting_drag = False
                self.update()
                
                # Accept the event to prevent context menu
                event.accept()
                return
                
            # Check if we were creating a connection with Right-click
            elif self.creating_connection:
                # Transform mouse position to account for zoom and pan
                scene_pos = self.transform_point_to_scene(event.pos())
                
                # Check if releasing over an element
                target_element = None
                for element in reversed(self.elements):
                    if element.contains(scene_pos):
                        target_element = element
                        break
                
                if target_element and target_element != self.connection_source:
                    # Check if a connection already exists between these elements
                    existing_connection = None
                    for conn in self.connections:
                        if (conn.source == self.connection_source and conn.target == target_element):
                            existing_connection = conn
                            break
                    
                    if existing_connection:
                        # Connection already exists
                        print(f"Connection already exists between {self.connection_source.label} and {target_element.label}")
                    else:
                        # Create a new connection
                        new_connection = ArrowConnection(self.connection_source, target_element)
                        self.connections.append(new_connection)
                        print(f"Created connection from {self.connection_source.label} to {target_element.label}")
                        self.diagram_changed.emit()
                        
                        # Set the flag to prevent context menu
                        self.connection_just_created = True
                        self.connection_creation_time = QTime.currentTime()
                else:
                    print("Connection creation cancelled - no target element or same as source")
                
                # Reset connection creation state
                self.creating_connection = False
                self.connection_source = None
                self.update()
                
                # Accept the event to prevent context menu
                event.accept()
    
    def mouseDoubleClickEvent(self, event):
        # Transform mouse position to account for zoom and pan
        scene_pos = self.transform_point_to_scene(event.pos())
        
        # Check if double-clicking on a container title
        for element in self.elements:
            if element.children:
                # Calculate container bounds
                min_x = element.x
                min_y = element.y
                max_x = element.x + element.width
                max_y = element.y + element.height
                
                # Define title padding
                title_padding = 40  # Extra space below the header
                
                # Adjust the parent element's position if it's too close to the top of its own container
                if element.y < min_y + title_padding:
                    # Create space between the parent element and the container title
                    element.y = min_y + title_padding
                    max_y = element.y + element.height  # Update max_y after moving the element
                
                for child in element.children:
                    # Apply extra top padding to child elements to prevent them from touching the title
                    # Adjust child positions if they're too close to the top of the container
                    if child.y < min_y + title_padding:
                        # Push the child element down if it's too close to the title
                        child.y = min_y + title_padding
                    
                    min_x = min(min_x, child.x)
                    min_y = min(min_y, child.y)
                    max_x = max(max_x, child.x + child.width)
                    max_y = max(max_y, child.y + child.height)
                
                # Add padding
                padding = 20  # Increased padding
                min_x -= padding
                min_y -= padding
                max_x += padding
                max_y += padding
                
                # Check if clicked in the title area (top 20 pixels of container)
                title_rect = QRect(min_x, min_y, max_x - min_x, 20)
                if title_rect.contains(scene_pos):
                    # Get current container title or default
                    current_title = element.container_title if element.container_title else f"{element.label}"
                    # Edit container title
                    text, ok = QInputDialog.getText(self, "Container Title", "Enter container name:", 
                                                QLineEdit.Normal, current_title)
                    if ok:
                        element.container_title = text
                        # Title changed, update the D2 code
                        self.diagram_changed.emit()
                        self.update()
                    return
        
        # Double-clicking on a connection to edit its label
        for connection in self.connections:
            source_center = QPoint(connection.source.x + connection.source.width//2, 
                                  connection.source.y + connection.source.height//2)
            target_center = QPoint(connection.target.x + connection.target.width//2, 
                                  connection.target.y + connection.target.height//2)
            
            # Simple line hit test
            line_rect = QRect(min(source_center.x(), target_center.x()) - 5,
                             min(source_center.y(), target_center.y()) - 5,
                             abs(source_center.x() - target_center.x()) + 10,
                             abs(source_center.y() - target_center.y()) + 10)
            
            if line_rect.contains(event.pos()):
                # Edit connection label
                text, ok = QLineEdit.getText(self, "Connection Label", "Enter label:", 
                                             QLineEdit.Normal, connection.label)
                if ok:
                    connection.label = text
                    # Label changed, update the D2 code
                    self.diagram_changed.emit()
                    self.update()
                break
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill the background with a dark color
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        # Apply zoom and pan transformations
        painter.translate(self.pan_offset)
        painter.scale(self.scale_factor, self.scale_factor)
        
        # Draw the grid
        self.draw_grid(painter)
        
        # Draw containers first (so they appear behind elements)
        for element in self.elements:
            if element.children:
                # Calculate container bounds
                min_x = element.x
                min_y = element.y
                max_x = element.x + element.width
                max_y = element.y + element.height
                
                for child in element.children:
                    min_x = min(min_x, child.x)
                    min_y = min(min_y, child.y)
                    max_x = max(max_x, child.x + child.width)
                    max_y = max(max_y, child.y + child.height)
                
                # Add padding
                padding = 20
                min_x -= padding
                min_y -= padding
                max_x += padding
                max_y += padding
                
                # Create container rectangle
                container_rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
                
                # Draw the container with a style similar to regular elements
                container_pen = QPen(QColor(100, 150, 100), 1.5, Qt.SolidLine)  # Solid line instead of dashed
                painter.setPen(container_pen)
                
                # Use a gradient background for a more polished look
                gradient = QRadialGradient(
                    (min_x + max_x) / 2, (min_y + max_y) / 2,  # Center of the container
                    max((max_x - min_x), (max_y - min_y)) / 2   # Radius
                )
                gradient.setColorAt(0, QColor(60, 80, 60, 40))  # Center color (semi-transparent)
                gradient.setColorAt(1, QColor(50, 70, 50, 60))  # Edge color (slightly more opaque)
                
                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(container_rect, 10, 10)  # More rounded corners
                
                # Draw a header bar at the top of the container
                header_height = 30  # Increased height for more space
                header_rect = QRectF(min_x, min_y, max_x - min_x, header_height)
                header_gradient = QLinearGradient(min_x, min_y, min_x, min_y + header_height)
                header_gradient.setColorAt(0, QColor(80, 120, 80, 180))  # Top color
                header_gradient.setColorAt(1, QColor(60, 100, 60, 150))  # Bottom color
                
                painter.setBrush(QBrush(header_gradient))
                painter.drawRoundedRect(header_rect, 10, 10)
                
                # Draw the container title with a better font
                container_text = element.container_title if element.container_title else f"{element.label} Container"
                painter.setPen(QPen(QColor(220, 240, 220)))
                
                # Use a slightly larger font for the title
                font = painter.font()
                original_font = QFont(font)
                font.setBold(True)
                font.setPointSize(font.pointSize() + 1)
                painter.setFont(font)
                
                # Center the text in the header
                text_rect = QRectF(min_x + 10, min_y, max_x - min_x - 20, header_height)
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, container_text)
                
                # Restore the original font
                painter.setFont(original_font)
        
        # Draw all connections
        for connection in self.connections:
            # Set the selected state based on whether the connection is in the selected_connections list
            connection.selected = connection in self.selected_connections
            connection.draw(painter)
        
        # Draw all elements (on top of connections and containers)
        for element in self.elements:
            element.draw(painter)
            
            # Draw highlight for selected elements
            if element in self.selected_elements:
                # Create a glowing highlight effect around selected elements
                highlight_rect = QRectF(element.x - 5, element.y - 5, 
                                     element.width + 10, element.height + 10)
                
                # Use a solid line with a bright color for the highlight (70% opacity)
                highlight_pen = QPen(QColor(0, 160, 255, 178), 2.5)  # 255 * 0.7 = 178
                painter.setPen(highlight_pen)
                painter.setBrush(Qt.NoBrush)
                
                # Draw rounded rectangle for the highlight
                painter.drawRoundedRect(highlight_rect, 8, 8)
                
                # Add a second, outer glow effect (70% opacity)
                outer_glow_rect = QRectF(element.x - 8, element.y - 8, 
                                     element.width + 16, element.height + 16)
                outer_glow_pen = QPen(QColor(0, 160, 255, 56), 1.5, Qt.DashLine)  # 80 * 0.7 = 56
                painter.setPen(outer_glow_pen)
                painter.drawRoundedRect(outer_glow_rect, 10, 10)
                
                # If this is a container, draw a small indicator
                if element.children:
                    indicator_rect = QRectF(element.x - 5, element.y - 5, 10, 10)
                    painter.setPen(QPen(QColor(100, 200, 100)))
                    painter.setBrush(QBrush(QColor(100, 200, 100)))
                    painter.drawRect(indicator_rect)
        
        # Draw temporary connection line if creating a connection
        if self.creating_connection and self.connection_source:
            # Get the start point (center of the start element)
            start_x = self.connection_source.x + self.connection_source.width / 2
            start_y = self.connection_source.y + self.connection_source.height / 2
            start_point = QPoint(int(start_x), int(start_y))
            
            # Get the current mouse position
            current_point = self.transform_point_to_scene(self.mapFromGlobal(self.cursor().pos()))
            
            # Draw a dashed line
            painter.setPen(QPen(QColor(200, 200, 200), 2, Qt.DashLine))
            painter.drawLine(start_point, current_point)
        
        # Draw temporary nesting line if creating a nesting relationship
        if self.creating_nesting and self.nesting_parent:
            # Get the start point (center of the parent element)
            start_x = self.nesting_parent.x + self.nesting_parent.width / 2
            start_y = self.nesting_parent.y + self.nesting_parent.height / 2
            start_point = QPoint(int(start_x), int(start_y))
            
            # Get the current mouse position
            current_point = self.transform_point_to_scene(self.mapFromGlobal(self.cursor().pos()))
            
            # Draw a dashed line with a different color
            painter.setPen(QPen(QColor(100, 200, 100), 2, Qt.DashLine))
            painter.drawLine(start_point, current_point)
        
        # Draw cutting line if in cutting mode
        if self.cutting and self.cut_start and self.cut_current:
            painter.setPen(QPen(QColor(255, 100, 100), 2, Qt.DashLine))
            painter.drawLine(self.cut_start, self.cut_current)
        
        # Draw selection rectangle if selecting
        if hasattr(self, 'selecting') and self.selecting and hasattr(self, 'selection_rect') and self.selection_rect is not None:
            # Transform the selection rectangle to account for zoom and pan
            transformed_rect = QRect(
                self.transform_point_from_scene(QPoint(self.selection_rect.left(), self.selection_rect.top())),
                self.transform_point_from_scene(QPoint(self.selection_rect.right(), self.selection_rect.bottom()))
            ).normalized()
            
            # Draw the selection rectangle
            painter.setPen(QPen(QColor(100, 150, 255), 1, Qt.DashLine))
            painter.setBrush(QBrush(QColor(100, 150, 255, 50)))
            painter.drawRect(transformed_rect)
    
    def draw_grid(self, painter):
        # Draw a light grid with dark mode colors
        painter.setPen(QPen(DARK_GRID, 1, Qt.SolidLine))
        
        # Save the current transformation to restore it later
        painter.save()
        
        # Reset the transformation to draw grid in screen coordinates
        painter.resetTransform()
        
        # Get the widget size
        widget_width = self.width()
        widget_height = self.height()
        
        # Calculate the grid size in screen coordinates
        base_grid_size = 20
        screen_grid_size = base_grid_size * self.scale_factor
        
        # Adjust grid size based on zoom level for better visibility
        if self.scale_factor < 0.5:
            screen_grid_size = base_grid_size * self.scale_factor * 2
        elif self.scale_factor > 2:
            screen_grid_size = base_grid_size * self.scale_factor / 2
        
        # Ensure grid size is at least 10 pixels and at most 50 pixels
        screen_grid_size = max(10, min(50, screen_grid_size))
        
        # Calculate offset for grid alignment based on pan
        offset_x = self.pan_offset.x() % screen_grid_size
        offset_y = self.pan_offset.y() % screen_grid_size
        
        # Draw vertical grid lines
        x = offset_x
        while x < widget_width:
            painter.drawLine(int(x), 0, int(x), widget_height)
            x += screen_grid_size
        
        # Draw horizontal grid lines
        y = offset_y
        while y < widget_height:
            painter.drawLine(0, int(y), widget_width, int(y))
            y += screen_grid_size
        
        # Restore the original transformation
        painter.restore()
    
    def generate_d2_code(self):
        """Generate D2 code from the current diagram"""
        print(f"GENERATE D2 CODE - Elements: {len(self.elements)}, Connections: {len(self.connections)}")
        
        # Debug print for all elements
        for i, element in enumerate(self.elements):
            print(f"  Element {i}: {element.__class__.__name__}, Label: '{element.label}', Pos: ({element.x}, {element.y})")
        
        # Debug print for all connections
        for i, connection in enumerate(self.connections):
            print(f"  Connection {i}: {connection.source.label} -> {connection.target.label}")
        
        # If no elements, show instructions
        if len(self.elements) == 0:
            return "# Create a diagram by dragging elements from the top panel\n# Right-click between elements to create connections"
        
        # Generate D2 code
        code_parts = []
        
        # Track elements that have been added to the D2 code
        added_elements = set()
        
        # Add only top-level elements (elements that are not children of other elements)
        for element in self.elements:
            # Skip elements that are children of other elements
            if element.parent is not None:
                print(f"  Skipping child element: {element.label} (parent: {element.parent.label})")
                continue
                
            try:
                element_code = element.to_d2()
                code_parts.append(element_code)
                added_elements.add(element.label)
                print(f"  Added element code: {element_code}")
            except Exception as e:
                print(f"Error generating D2 code for element {element.label}: {e}")
        
        # Add all connections
        for connection in self.connections:
            try:
                # Check if both source and target elements are already added
                if connection.source.label not in added_elements:
                    source_code = connection.source.to_d2()
                    code_parts.append(source_code)
                    added_elements.add(connection.source.label)
                    print(f"  Added source element code: {source_code}")
                
                if connection.target.label not in added_elements:
                    target_code = connection.target.to_d2()
                    code_parts.append(target_code)
                    added_elements.add(connection.target.label)
                    print(f"  Added target element code: {target_code}")
                
                connection_code = connection.to_d2()
                code_parts.append(connection_code)
                print(f"  Added connection code: {connection_code}")
            except Exception as e:
                print(f"Error generating D2 code for connection: {e}")
        
        # Join all code parts
        result = "\n".join(code_parts)
        
        # Print the final D2 code
        print(f"Final D2 code ({len(code_parts)} parts):\n{result}")
        
        return result
    
    def keyPressEvent(self, event):
        # Handle keyboard shortcuts
        if event.key() == Qt.Key_Delete:
            # Delete selected elements
            if self.selected_elements or self.selected_connections:
                # Save the current state for undo
                parent_window = self.window()
                if isinstance(parent_window, DiagramDesigner):
                    parent_window.save_state()
                
                if self.selected_elements:
                    for element in list(self.selected_elements):
                        # Remove any connections to/from this element
                        for connection in list(self.connections):
                            if connection.source == element or connection.target == element:
                                self.connections.remove(connection)
                        
                        # Remove the element from its parent if it has one
                        if element.parent:
                            element.parent.children.remove(element)
                            element.parent = None
                        
                        # Remove any children of this element
                        for child in list(element.children):
                            child.parent = None
                            element.children.remove(child)
                        
                        # Remove the element from the canvas
                        self.elements.remove(element)
                    
                    # Clear selection
                    self.selected_elements.clear()
                    
                    # Emit signal to update D2 code
                    self.diagram_changed.emit()
                    
                    # Update the canvas
                    self.update()
                
                # Delete selected connections
                if self.selected_connections:
                    for connection in list(self.selected_connections):
                        self.connections.remove(connection)
                    
                    # Clear selection
                    self.selected_connections.clear()
                    
                    # Emit signal to update D2 code
                    self.diagram_changed.emit()
                    
                    # Update the canvas
                    self.update()
        
        # 'X' key also deletes elements (same as Delete key)
        elif event.key() == Qt.Key_X and not event.modifiers() & Qt.ControlModifier:
            # Delete selected elements
            if self.selected_elements:
                for element in list(self.selected_elements):
                    # Remove any connections to/from this element
                    for connection in list(self.connections):
                        if connection.source == element or connection.target == element:
                            self.connections.remove(connection)
                    
                    # Remove the element from its parent if it has one
                    if element.parent:
                        element.parent.children.remove(element)
                        element.parent = None
                    
                    # Remove any children of this element
                    for child in list(element.children):
                        child.parent = None
                        element.children.remove(child)
                    
                    # Remove the element from the canvas
                    self.elements.remove(element)
                
                # Clear selection
                self.selected_elements.clear()
                
                # Emit signal to update D2 code
                self.diagram_changed.emit()
                
                # Update the canvas
                self.update()
            
            # Delete selected connections
            if self.selected_connections:
                for connection in list(self.selected_connections):
                    self.connections.remove(connection)
                
                # Clear selection
                self.selected_connections.clear()
                
                # Emit signal to update D2 code
                self.diagram_changed.emit()
                
                # Update the canvas
                self.update()
        
        # Cancel current operations with Escape key
        elif event.key() == Qt.Key_Escape:
            # Cancel connection creation
            if self.creating_connection:
                self.creating_connection = False
                self.connection_source = None
                self.update()
            
            # Cancel nesting creation
            if self.creating_nesting:
                self.creating_nesting = False
                self.nesting_parent = None
                self.update()
                
            # Cancel cutting mode
            if self.cutting:
                self.cutting = False
                self.cut_start = None
                self.cut_current = None
                self.setCursor(Qt.ArrowCursor)
                self.update()
            
            # Clear selection
            self.selected_elements.clear()
            self.selected_connections.clear()
            self.update()
        
        # Ctrl+D to duplicate selected elements
        elif event.key() == Qt.Key_D and event.modifiers() & Qt.ControlModifier:
            if self.selected_elements:
                # Save the current state for undo
                parent_window = self.window()
                if isinstance(parent_window, DiagramDesigner):
                    parent_window.save_state()
                
                new_elements = []
                
                for element in self.selected_elements:
                    # Create a new element of the same type
                    if isinstance(element, BoxElement):
                        new_element = BoxElement(element.x + 20, element.y + 20, element.width, element.height, element.label + " (copy)")
                    elif isinstance(element, CircleElement):
                        new_element = CircleElement(element.x + 20, element.y + 20, element.width, element.height, element.label + " (copy)")
                    elif isinstance(element, DiamondElement):
                        new_element = DiamondElement(element.x + 20, element.y + 20, element.width, element.height, element.label + " (copy)")
                    elif isinstance(element, HexagonElement):
                        new_element = HexagonElement(element.x + 20, element.y + 20, element.width, element.height, element.label + " (copy)")
                    else:
                        continue
                    
                    # Copy properties
                    new_element.color = QColor(element.color)
                    new_element.border_color = QColor(element.border_color)
                    
                    # Add to canvas
                    self.elements.append(new_element)
                    new_elements.append(new_element)
                
                # Update selection to the new elements
                self.selected_elements = new_elements
                
                # Emit signal to update D2 code
                self.diagram_changed.emit()
                
                # Update the canvas
                self.update()
        
        # Ctrl+X to disconnect from parent
        elif event.key() == Qt.Key_X and event.modifiers() & Qt.ControlModifier:
            if self.selected_elements:
                # Save the current state for undo
                parent_window = self.window()
                if isinstance(parent_window, DiagramDesigner):
                    parent_window.save_state()
                
                for element in self.selected_elements:
                    self.disconnect_from_parent(element)
        
        # Ctrl+Z for undo (handled by the main window)
        elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            print("Ctrl+Z pressed - Calling undo_action")
            parent_window = self.window()
            if isinstance(parent_window, DiagramDesigner):
                parent_window.undo_action()
        
        # Ctrl+Y for redo (handled by the main window)
        elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            print("Ctrl+Y pressed - Calling redo_action")
            parent_window = self.window()
            if isinstance(parent_window, DiagramDesigner):
                parent_window.redo_action()
        
        # Ctrl+S for save
        elif event.key() == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
            parent_window = self.window()
            if isinstance(parent_window, DiagramDesigner):
                parent_window.save_diagram()
        
        # Ctrl+O for open/load
        elif event.key() == Qt.Key_O and event.modifiers() & Qt.ControlModifier:
            parent_window = self.window()
            if isinstance(parent_window, DiagramDesigner):
                parent_window.load_diagram()
        
        else:
            # Pass the event to the parent class
            super().keyPressEvent(event)
    
    def transform_point_to_scene(self, point):
        """Transform a point from screen coordinates to scene coordinates"""
        # Adjust for pan
        adjusted_point = QPoint(point.x() - self.pan_offset.x(), point.y() - self.pan_offset.y())
        # Adjust for zoom
        return QPoint(int(adjusted_point.x() / self.scale_factor), int(adjusted_point.y() / self.scale_factor))
    
    def transform_point_from_scene(self, point):
        """Transform a point from scene coordinates to screen coordinates"""
        # Adjust for zoom
        scaled_point = QPoint(int(point.x() * self.scale_factor), int(point.y() * self.scale_factor))
        # Adjust for pan
        return QPoint(scaled_point.x() + self.pan_offset.x(), scaled_point.y() + self.pan_offset.y())
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming"""
        # Store the mouse position in screen coordinates
        mouse_pos = event.pos()
        
        # Convert mouse position to scene coordinates before zoom
        scene_pos = self.transform_point_to_scene(mouse_pos)
        
        # Store old scale factor
        old_scale = self.scale_factor
        
        # Calculate zoom factor
        zoom_factor = 1.15  # Slightly increased for more noticeable zoom
        if event.angleDelta().y() < 0:
            # Zoom out
            self.scale_factor /= zoom_factor
        else:
            # Zoom in
            self.scale_factor *= zoom_factor
        
        # Clamp scale factor to min/max values
        self.scale_factor = max(self.min_scale, min(self.max_scale, self.scale_factor))
        
        # Calculate how the scene point would be positioned after zoom
        # This is the key to zooming at the mouse position
        new_screen_x = int(scene_pos.x() * self.scale_factor + self.pan_offset.x())
        new_screen_y = int(scene_pos.y() * self.scale_factor + self.pan_offset.y())
        
        # Adjust pan offset to keep the point under the cursor fixed
        delta_x = new_screen_x - mouse_pos.x()
        delta_y = new_screen_y - mouse_pos.y()
        
        self.pan_offset.setX(self.pan_offset.x() - delta_x)
        self.pan_offset.setY(self.pan_offset.y() - delta_y)
        
        # Force immediate repaint to ensure real-time updates
        self.repaint()
        
        # Debug print
        print(f"Zoom: {self.scale_factor:.2f}, Pan: ({self.pan_offset.x()}, {self.pan_offset.y()})")
        
        # Accept the event to prevent it from being passed to parent widgets
        event.accept()

    def zoom_to_fit(self):
        """Zoom to fit the diagram in the canvas"""
        if not self.elements:
            # Reset to default view if no elements
            self.scale_factor = 1.0
            self.pan_offset = QPoint(0, 0)
            self.update()
            return
            
        # Find the bounding box of all elements
        min_x = min(element.x for element in self.elements)
        max_x = max(element.x + element.width for element in self.elements)
        min_y = min(element.y for element in self.elements)
        max_y = max(element.y + element.height for element in self.elements)
        
        # Add padding (10% on each side)
        padding_x = (max_x - min_x) * 0.1
        padding_y = (max_y - min_y) * 0.1
        min_x -= padding_x
        max_x += padding_x
        min_y -= padding_y
        max_y += padding_y
        
        # Calculate dimensions
        width = max_x - min_x
        height = max_y - min_y
        
        if width <= 0 or height <= 0:
            return
            
        # Calculate scale factor to fit the diagram
        scale_x = self.width() / width
        scale_y = self.height() / height
        self.scale_factor = min(scale_x, scale_y, self.max_scale)  # Limit maximum zoom
        
        # Calculate pan offset to center the diagram
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        viewport_center_x = self.width() / 2
        viewport_center_y = self.height() / 2
        
        self.pan_offset.setX(int(viewport_center_x - center_x * self.scale_factor))
        self.pan_offset.setY(int(viewport_center_y - center_y * self.scale_factor))
        
        self.update()
        print(f"Zoom to fit: scale={self.scale_factor}, pan=({self.pan_offset.x()}, {self.pan_offset.y()})")

    def find_intersected_connections(self, start_point, end_point):
        """Find connections that intersect with the line from start_point to end_point"""
        intersected_connections = []
        
        for connection in self.connections:
            # Get the source and target points of the connection
            source_center = QPoint(
                int(connection.source.x + connection.source.width / 2),
                int(connection.source.y + connection.source.height / 2)
            )
            target_center = QPoint(
                int(connection.target.x + connection.target.width / 2),
                int(connection.target.y + connection.target.height / 2)
            )
            
            # Find the actual connection points (where the arrow intersects with the elements)
            source_point = connection._find_intersection_point(connection.source, target_center, source_center)
            target_point = connection._find_intersection_point(connection.target, source_center, target_center)
            
            # Check if the cutting line intersects with the connection line
            if self._lines_intersect(start_point, end_point, source_point, target_point):
                intersected_connections.append(connection)
                print(f"Connection intersected: {connection.source.label} -> {connection.target.label}")
        
        return intersected_connections
        
    def _lines_intersect(self, p1, p2, p3, p4):
        """Check if two line segments (p1-p2 and p3-p4) intersect"""
        # Convert QPoint to coordinates
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        x3, y3 = p3.x(), p3.y()
        x4, y4 = p4.x(), p4.y()
        
        # Calculate the direction vectors
        dx1 = x2 - x1
        dy1 = y2 - y1
        dx2 = x4 - x3
        dy2 = y4 - y3
        
        # Calculate the determinant
        det = dx1 * dy2 - dy1 * dx2
        
        # If determinant is zero, lines are parallel
        if abs(det) < 1e-10:
            return False
            
        # Calculate parameters for the intersection point
        t1 = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / det
        t2 = ((x3 - x1) * dy1 - (y3 - y1) * dx1) / det
        
        # Check if the intersection point is within both line segments
        return 0 <= t1 <= 1 and 0 <= t2 <= 1

    def push_away_elements(self, resized_element, original_width, original_height):
        """
        Push away elements that would overlap with the resized element.
        
        Args:
            resized_element: The element that was resized
            original_width: The original width of the element before resizing
            original_height: The original height of the element before resizing
        """
        # Calculate how much the element has grown in each direction
        width_increase = resized_element.width - original_width
        height_increase = resized_element.height - original_height
        
        # If the element didn't grow, no need to push anything
        if width_increase <= 0 and height_increase <= 0:
            return
        
        # Check each element for potential overlap
        for element in self.elements:
            # Skip the resized element itself
            if element == resized_element or element in resized_element.children:
                continue
                
            # Skip if the element is a parent of the resized element
            if resized_element.parent == element:
                continue
                
            # Check if the elements now overlap
            if resized_element.overlaps_with(element, self.ELEMENT_PADDING):
                # Calculate the center points of both elements
                resized_center_x = resized_element.x + resized_element.width / 2
                resized_center_y = resized_element.y + resized_element.height / 2
                element_center_x = element.x + element.width / 2
                element_center_y = element.y + element.height / 2
                
                # Calculate the direction vector from resized element to the other element
                dx = element_center_x - resized_center_x
                dy = element_center_y - resized_center_y
                
                # Normalize the direction vector if it's not zero
                length = (dx**2 + dy**2)**0.5
                if length < 0.001:  # Avoid division by zero
                    # If centers are too close, push directly to the right
                    dx, dy = 1, 0
                else:
                    dx /= length
                    dy /= length
                
                # Calculate the minimum distance needed to push away
                # This includes the half-widths/heights of both elements plus padding
                min_dist_x = (resized_element.width + element.width) / 2 + self.ELEMENT_PADDING
                min_dist_y = (resized_element.height + element.height) / 2 + self.ELEMENT_PADDING
                
                # Calculate the actual distance between centers
                actual_dist = length
                
                # Calculate how much to push in each direction
                # We push more in the direction of the larger component (dx or dy)
                if abs(dx) > abs(dy):
                    # Pushing horizontally is preferred
                    push_x = dx * (min_dist_x - actual_dist * abs(dx)) / abs(dx) if abs(dx) > 0.001 else 0
                    push_y = 0
                else:
                    # Pushing vertically is preferred
                    push_x = 0
                    push_y = dy * (min_dist_y - actual_dist * abs(dy)) / abs(dy) if abs(dy) > 0.001 else 0
                
                # Apply the push
                element.move(int(push_x), int(push_y))
                
                # Recursively push away any elements that might now overlap with the pushed element
                self.push_away_elements(element, element.width, element.height)

    def resize_element(self, element, new_width, new_height):
        """
        Resize an element and push away other elements if needed.
        
        Args:
            element: The element to resize
            new_width: The new width for the element
            new_height: The new height for the element
        """
        # Store original dimensions
        original_width = element.width
        original_height = element.height
        
        # Resize the element using its resize method to respect minimum text size
        element.resize(new_width, new_height)
        
        # Push away other elements if needed
        self.push_away_elements(element, original_width, original_height)
        
        # Update the canvas
        self.update()
        
        # Emit signal to update D2 code
        self.diagram_changed.emit()


class DiagramDesigner(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("D2 Diagram Designer")
        
        # Set window flags for a minimal frame
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        
        # Create and set a box icon for the window
        icon = QIcon()
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(220, 220, 220), 2))
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.drawRect(4, 4, 24, 24)
        painter.end()
        icon.addPixmap(pixmap)
        self.setWindowIcon(icon)
        
        # Initialize undo and redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 20  # Maximum number of undo steps
        
        # Apply dark mode to the application
        self.setup_dark_mode()
        self.setup_ui()
    
    def setup_dark_mode(self):
        """Apply dark mode styling to the application"""
        # Set the application style to dark mode
        app = QApplication.instance()
        
        # Set dark palette for the application
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, DARK_BG)
        dark_palette.setColor(QPalette.WindowText, QColor(220, 220, 220))  # Keep UI text light
        dark_palette.setColor(QPalette.Base, DARK_WIDGET_BG)
        dark_palette.setColor(QPalette.AlternateBase, DARK_BG)
        dark_palette.setColor(QPalette.ToolTipBase, DARK_WIDGET_BG)  # Dark background for tooltips
        dark_palette.setColor(QPalette.ToolTipText, QColor(240, 240, 240))  # White text for tooltips
        dark_palette.setColor(QPalette.Text, QColor(220, 220, 220))  # Keep input text light
        dark_palette.setColor(QPalette.Button, DARK_WIDGET_BG)
        dark_palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))  # Keep button text light
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, DARK_SELECTION)
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        
        # Apply the palette
        app.setPalette(dark_palette)
        
        # Set stylesheet for additional customization
        QApplication.setStyle("Fusion")  # Use Fusion style for better dark mode support
        
        # Apply stylesheet for scrollbars and other elements
        app.setStyleSheet("""
            /* Custom window frame styling */
            QMainWindow {
                border: 1px solid #505050;
            }
            
            /* Title bar styling */
            QWidget#titleBar {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border-bottom: 1px solid #505050;
                min-height: 28px;
                max-height: 28px;
            }
            
            /* Improved scrollbar styling */
            QScrollBar:vertical {
                background: #2a2a2a;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #505050;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #606060;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            QScrollBar:horizontal {
                background: #2a2a2a;
                height: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #505050;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #606060;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            
            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3c3c3c;
            }
            QToolButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #505050;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #505050;
            }
            QSplitter::handle {
                background-color: #3c3c3c;
            }
            QMainWindow::separator {
                background-color: #3c3c3c;
                width: 1px;
                height: 1px;
            }
            QToolTip {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #505050;
                padding: 2px;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #505050;
            }
            QMenu::item:selected {
                background-color: #3a6ea5;
            }
        """)
    
    def setup_ui(self):
        # Create the central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 2, 5, 5)  # Reduce margins
        main_layout.setSpacing(2)  # Reduce spacing between widgets
        
        # Add custom title bar
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(5, 0, 5, 0)
        
        # Add window icon to title bar
        icon_label = QLabel()
        icon_pixmap = QPixmap(16, 16)
        icon_pixmap.fill(Qt.transparent)
        painter = QPainter(icon_pixmap)
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.drawRect(2, 2, 12, 12)
        painter.end()
        icon_label.setPixmap(icon_pixmap)
        title_bar_layout.addWidget(icon_label)
        
        # Add title to title bar
        title_label = QLabel("D2 Diagram Designer")
        title_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        
        # Add minimize, maximize, and close buttons
        min_button = QPushButton("—")
        min_button.setFixedSize(24, 24)
        min_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        min_button.clicked.connect(self.showMinimized)
        
        max_button = QPushButton("□")
        max_button.setFixedSize(24, 24)
        max_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        max_button.clicked.connect(self.toggle_maximize)
        
        close_button = QPushButton("×")
        close_button.setFixedSize(24, 24)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e04040;
                color: white;
            }
        """)
        close_button.clicked.connect(self.close)
        
        title_bar_layout.addWidget(min_button)
        title_bar_layout.addWidget(max_button)
        title_bar_layout.addWidget(close_button)
        
        # Make title bar draggable
        title_bar.mousePressEvent = self.title_bar_mouse_press
        title_bar.mouseMoveEvent = self.title_bar_mouse_move
        
        main_layout.addWidget(title_bar)
        
        # Add keyboard shortcuts
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(lambda: print("Ctrl+Z shortcut activated") or self.undo_action())
        
        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(lambda: print("Ctrl+Y shortcut activated") or self.redo_action())
        
        # Create splitter for canvas and code panel
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Middle panel (canvas)
        self.canvas = DiagramCanvas()
        
        # Set status tip for the canvas
        self.canvas.setStatusTip("Hold Alt + Left Click and drag to cut connections. Right-click to create connections between elements.")
        
        # Right panel (D2 code)
        code_panel = QWidget()
        code_layout = QVBoxLayout(code_panel)
        code_layout.setContentsMargins(5, 0, 5, 5)  # Remove top margin to extend to top of window
        
        # Create the code edit
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(False)  # Make the code panel editable
        self.code_edit.setFont(QFont("Courier New", 10))
        self.code_edit.setMinimumWidth(300)  # Ensure code panel has minimum width
        self.code_edit.setStyleSheet("background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3c3c3c;")
        
        # Connect the textChanged signal to update the diagram
        self.code_edit.textChanged.connect(self.on_code_changed)
        
        code_layout.addWidget(self.code_edit)
        
        # Add copy to clipboard button in a separate layout aligned to the right
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        copy_button = QPushButton("Copy to Clipboard")
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: #e0e0e0;
                border: 1px solid #646464;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
        """)
        copy_button.clicked.connect(self.copy_code_to_clipboard)
        
        button_layout.addWidget(copy_button)
        code_layout.addLayout(button_layout)
        
        # Add panels to splitter
        content_splitter.addWidget(self.canvas)
        content_splitter.addWidget(code_panel)
        
        # Set initial sizes - make canvas 2/3 and code panel 1/3
        content_splitter.setSizes([2, 1])
        
        # Top panel (toolbox) - now horizontal and thinner
        toolbox = QWidget()
        toolbox.setMaximumHeight(80)  # Increase the height of the toolbox from 40 to 80
        toolbox.setStyleSheet("background-color: #3c3c3c;")
        
        # Create a horizontal layout for the toolbox
        toolbox_layout = QHBoxLayout(toolbox)
        toolbox_layout.setContentsMargins(10, 4, 10, 4)  # Double the margins (from 5,2,5,2 to 10,4,10,4)
        toolbox_layout.setSpacing(4)  # Double the spacing between items (from 2 to 4)
        
        # Add toolbox items with icons
        box_item = ToolboxItem("box", "Box")
        circle_item = ToolboxItem("circle", "Circle")
        diamond_item = ToolboxItem("diamond", "Diamond")
        # triangle_item = ToolboxItem("triangle", "Triangle") - Removed as triangle is not supported in D2
        hexagon_item = ToolboxItem("hexagon", "Hexagon")
        
        # Ensure the toolbox items have a reference to the designer
        box_item.designer = self
        circle_item.designer = self
        diamond_item.designer = self
        hexagon_item.designer = self
        
        toolbox_layout.addWidget(box_item)
        toolbox_layout.addWidget(circle_item)
        toolbox_layout.addWidget(diamond_item)
        # toolbox_layout.addWidget(triangle_item) - Removed as triangle is not supported in D2
        toolbox_layout.addWidget(hexagon_item)
        
        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #505050;")
        separator.setMaximumHeight(40)  # Double the separator height (from 20 to 40)
        toolbox_layout.addWidget(separator)
        
        # Add inline properties panel
        self.properties_panel = InlinePropertiesPanel()
        self.properties_panel.property_changed.connect(self.on_property_changed)
        toolbox_layout.addWidget(self.properties_panel)
        
        # Connect the canvas to the properties panel
        self.canvas.element_selected.connect(self.show_element_properties)
        
        toolbox_layout.addStretch()
        
        # Add New button to the toolbox on the far right
        new_button = ToolboxItem("new", "New Diagram")
        new_button.designer = self
        new_button.createCustomIcon("new")  # This will be overridden below
        
        # Create a custom icon for the New button
        new_icon = QPixmap(40, 40)  # Double size (from 20x20 to 40x40)
        new_icon.fill(Qt.transparent)
        painter = QPainter(new_icon)
        painter.setPen(QPen(QColor(220, 220, 220), 3))  # Double line width (from 2 to 3)
        painter.drawRect(8, 8, 24, 24)  # Double size (from 4,4,12,12 to 8,8,24,24)
        painter.drawLine(16, 16, 24, 16)  # Double position
        painter.drawLine(20, 12, 20, 20)  # Double position
        painter.end()
        
        new_button.setIcon(QIcon(new_icon))
        new_button.clicked.connect(self.new_diagram)
        
        # Add save button to the toolbox (now on the right side)
        save_button = ToolboxItem("save", "Save/Load/Export Diagram")
        save_button.designer = self
        
        # Create a custom icon for the Save button
        save_icon = QPixmap(40, 40)  # Double size (from 20x20 to 40x40)
        save_icon.fill(Qt.transparent)
        painter = QPainter(save_icon)
        painter.setPen(QPen(QColor(220, 220, 220), 3))  # Double line width (from 1.5 to 3)
        # Draw a floppy disk icon
        painter.drawRect(6, 6, 28, 28)  # Double size (from 3,3,14,14 to 6,6,28,28)
        painter.drawRect(24, 6, 10, 10)  # Double size (from 12,3,5,5 to 24,6,10,10)
        painter.drawLine(12, 20, 28, 20)  # Double position (from 6,10,14,10 to 12,20,28,20)
        painter.drawLine(12, 26, 28, 26)  # Double position (from 6,13,14,13 to 12,26,28,26)
        painter.end()
        
        save_button.setIcon(QIcon(save_icon))
        save_button.clicked.connect(self.show_save_load_menu)
        
        # Export button removed - functionality moved to save/load menu
        
        # Add buttons to the right side of the toolbar
        toolbox_layout.addWidget(new_button)
        toolbox_layout.addWidget(save_button)
        # Export button removed - functionality moved to save/load menu
        
        # Add toolbox and content splitter to main layout
        main_layout.addWidget(toolbox)
        main_layout.addWidget(content_splitter, 1)  # Give the content splitter a stretch factor
        
        # IMPORTANT: Connect the signal to update D2 code
        self.canvas.diagram_changed.connect(self.update_d2_code)
        print("Connected diagram_changed signal to update_d2_code slot")
        
        # Force an initial update of the D2 code panel
        QTimer.singleShot(100, self.update_d2_code)
        
        # Set the central widget
        self.setCentralWidget(central_widget)
        
        # Set window size
        self.resize(1200, 800)
    
    def show_element_properties(self, element):
        """Show the properties panel for the selected element"""
        # Make sure the properties panel has a reference to the canvas
        self.properties_panel.canvas = self.canvas
        self.properties_panel.set_element(element)
    
    def on_property_changed(self):
        """Update the D2 code when properties change"""
        self.update_d2_code()
    
    def update_d2_code(self):
        """Update the D2 code panel with the current diagram"""
        print("UPDATE_D2_CODE called - Canvas has", len(self.canvas.elements), "elements")
        
        # We don't need to save state here as it's already saved when elements are added/modified
        # self.save_state()
        
        # Generate D2 code from the diagram
        d2_code = self.canvas.generate_d2_code()
        
        # Temporarily disconnect the textChanged signal to avoid recursion
        self.code_edit.textChanged.disconnect(self.on_code_changed)
        
        # Update the code panel
        self.code_edit.setPlainText(d2_code)
        
        # Reconnect the textChanged signal
        self.code_edit.textChanged.connect(self.on_code_changed)
        
        # Print a sample of the code for debugging
        print("Code panel updated. Text length:", len(d2_code))
        if d2_code:
            print("Code panel text sample:", d2_code.split('\n')[0])
            if len(d2_code.split('\n')) > 1:
                print(d2_code.split('\n')[1])
    
    def on_code_changed(self):
        """Handle changes to the D2 code panel"""
        # This is a placeholder for future implementation
        # In a full implementation, this would parse the D2 code and update the diagram
        # For now, we'll just print a message
        print("Code panel changed - This feature is not fully implemented yet")
        
        # In a future version, we could implement a D2 parser to update the diagram
        # based on the code, but that's beyond the scope of this current implementation
    
    def new_diagram(self):
        """Clear the current diagram"""
        self.canvas.elements.clear()
        self.canvas.connections.clear()
        self.canvas.selected_elements.clear()
        self.canvas.selected_connections.clear()
        self.properties_panel.set_element(None)  # Hide the properties panel
        self.canvas.update()
        self.update_d2_code()
        
    def showEvent(self, event):
        """Called when the window is shown"""
        super().showEvent(event)
        # Force an update of the D2 code when the window is shown
        QTimer.singleShot(500, self.update_d2_code)
        
        # Apply dark mode to the window title bar
        if hasattr(self, 'winId'):
            try:
                hwnd = int(self.winId())
                set_window_dark_mode(hwnd)
            except Exception as e:
                print(f"Failed to set dark mode for title bar: {e}")
    
    def copy_code_to_clipboard(self):
        """Copy the D2 code to the clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code_edit.toPlainText())
        print("D2 code copied to clipboard")
    
    def save_diagram(self):
        """Save the diagram to a file"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", "D2 Files (*.d2)")
        if file_path:
            # Save the current state for undo
            self.save_state()
            
            # If the user didn't add .d2 extension, add it
            if not file_path.lower().endswith('.d2'):
                file_path += '.d2'
                
            # Get the D2 code
            d2_code = self.code_edit.toPlainText()
            
            # Write the D2 code to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(d2_code)
            
            QMessageBox.information(self, "Save Successful", f"Diagram saved to {file_path}")
    
    def load_diagram(self):
        """Load a diagram from a .d2 file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Diagram", "", "D2 Files (*.d2)")
        if file_path:
            try:
                # Read the D2 code from the file
                with open(file_path, 'r', encoding='utf-8') as f:
                    d2_code = f.read()
                
                # Save the current state for undo
                self.save_state()
                
                # Clear the current diagram
                self.canvas.elements.clear()
                self.canvas.connections.clear()
                self.canvas.selected_elements.clear()
                self.canvas.selected_connections.clear()
                
                # Update the code panel with the loaded code
                self.code_edit.setPlainText(d2_code)
                
                # Parse the D2 code and create visual elements
                self.parse_d2_code(d2_code)
                
                # Update the canvas
                self.canvas.update()
                
                QMessageBox.information(self, "Load Successful", f"Diagram loaded from {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Error loading diagram: {str(e)}")
    
    def parse_d2_code(self, d2_code):
        """Parse D2 code and create visual elements"""
        try:
            # Split the code into lines and process each line
            lines = d2_code.split('\n')
            
            # Track elements by their names
            element_map = {}
            
            # Track parent-child relationships
            parent_child_map = {}
            
            # Track connections
            connections = []
            
            # Current parent being processed
            current_parent = None
            current_parent_name = None
            
            # Process each line
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    i += 1
                    continue
                
                # Check for element definitions (e.g., "Box: {")
                if ':' in line and '{' in line:
                    # Extract element name
                    element_name = line.split(':', 1)[0].strip()
                    
                    # Check if this is a child element (indented)
                    is_child = False
                    if current_parent and lines[i].startswith('  '):
                        is_child = True
                    
                    # Default properties
                    shape_type = "box"  # Default shape
                    label = element_name
                    x = 100 + len(element_map) * 50  # Stagger elements
                    y = 100 + len(element_map) * 30
                    width = 100
                    height = 60
                    color = QColor(180, 180, 180)
                    
                    # Look ahead for properties
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().endswith('}'):
                        prop_line = lines[j].strip()
                        
                        # Check for shape property
                        if 'shape:' in prop_line:
                            shape_value = prop_line.split(':', 1)[1].strip().replace('"', '').replace("'", "")
                            if 'circle' in shape_value:
                                shape_type = "circle"
                                width = height = 80  # Circles are typically square
                            elif 'diamond' in shape_value:
                                shape_type = "diamond"
                            elif 'hexagon' in shape_value:
                                shape_type = "hexagon"
                        
                        # Check for label property
                        elif 'label:' in prop_line:
                            label = prop_line.split(':', 1)[1].strip().replace('"', '').replace("'", "")
                        
                        # Check for fill color
                        elif 'style.fill:' in prop_line:
                            color_str = prop_line.split(':', 1)[1].strip().replace('"', '').replace("'", "")
                            color = QColor(color_str)
                        
                        # Check for position information in comments
                        elif '# position:' in prop_line:
                            try:
                                # Extract position data: x,y,width,height
                                pos_data = prop_line.split('# position:', 1)[1].strip().split(',')
                                if len(pos_data) == 4:
                                    x = int(pos_data[0])
                                    y = int(pos_data[1])
                                    width = int(pos_data[2])
                                    height = int(pos_data[3])
                                    print(f"Found position data for {element_name}: x={x}, y={y}, width={width}, height={height}")
                            except Exception as e:
                                print(f"Error parsing position data: {e}")
                        
                        j += 1
                    
                    # Create the element based on shape type
                    new_element = None
                    if shape_type == "box":
                        new_element = BoxElement(x, y, width, height, label)
                    elif shape_type == "circle":
                        new_element = CircleElement(x, y, width, height, label)
                    elif shape_type == "diamond":
                        new_element = DiamondElement(x, y, width, height, label)
                    elif shape_type == "hexagon":
                        new_element = HexagonElement(x, y, width, height, label)
                    
                    if new_element:
                        new_element.color = color
                        
                        # If position was explicitly specified in the file, use those dimensions
                        # instead of the auto-calculated ones based on text
                        position_specified = False
                        for line_j in range(i + 1, j):
                            if '# position:' in lines[line_j]:
                                position_specified = True
                                break
                                
                        if position_specified:
                            new_element.x = x
                            new_element.y = y
                            new_element.width = width
                            new_element.height = height
                        
                        self.canvas.elements.append(new_element)
                        element_map[element_name] = new_element
                        
                        # Handle parent-child relationship
                        if is_child and current_parent:
                            parent_child_map.setdefault(current_parent_name, []).append(element_name)
                    
                    # Check if this element has children (next line has '{')
                    if j < len(lines) and '{' in lines[j]:
                        current_parent = new_element
                        current_parent_name = element_name
                    
                    i = j + 1
                    continue
                
                # Check for connections (e.g., "Box -> Circle")
                if '->' in line:
                    parts = line.split('->')
                    if len(parts) == 2:
                        source_name = parts[0].strip()
                        
                        # Extract target name and any label
                        target_part = parts[1].strip()
                        
                        # Remove any comments from the target part
                        if '#' in target_part:
                            target_part = target_part.split('#')[0].strip()
                        
                        # Extract target name and label
                        if ':' in target_part:
                            target_name, label = target_part.split(':', 1)
                            target_name = target_name.strip()
                            label = label.strip()
                        else:
                            target_name = target_part.split(' ')[0].strip()  # Remove any trailing properties
                            label = ""
                        
                        # Check for connection ID information in comments
                        source_id = None
                        target_id = None
                        if '# connection:' in line:
                            try:
                                # Extract connection data: source_id,target_id
                                conn_data = line.split('# connection:', 1)[1].strip().split(',')
                                if len(conn_data) == 2:
                                    source_id = int(conn_data[0])
                                    target_id = int(conn_data[1])
                                    print(f"Found connection data: source_id={source_id}, target_id={target_id}")
                            except Exception as e:
                                print(f"Error parsing connection data: {e}")
                        
                        # Store connection to create later when all elements are processed
                        connections.append((source_name, target_name, label, source_id, target_id))
                
                i += 1
            
            # Process parent-child relationships
            for parent_name, child_names in parent_child_map.items():
                parent = element_map.get(parent_name)
                if parent:
                    for child_name in child_names:
                        child = element_map.get(child_name)
                        if child:
                            child.parent = parent
                            parent.children.append(child)
            
            # Create connections
            for source_name, target_name, label, source_id, target_id in connections:
                source = element_map.get(source_name)
                target = element_map.get(target_name)
                if source and target:
                    # Clean up the label to remove any ID information
                    clean_label = label
                    if '#' in clean_label:
                        clean_label = clean_label.split('#')[0].strip()
                        
                    connection = ArrowConnection(source, target, clean_label)
                    self.canvas.connections.append(connection)
            
            # Signal that the diagram has changed
            self.canvas.diagram_changed.emit()
            
        except Exception as e:
            print(f"Error parsing D2 code: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def arrange_elements(self):
        """Arrange elements to avoid overlaps"""
        # Simple arrangement - place elements in a grid
        grid_size = 150
        cols = 4  # Number of columns in the grid
        
        # Group elements by their parent
        grouped_elements = {}
        root_elements = []
        
        for element in self.canvas.elements:
            if element.parent:
                parent_id = id(element.parent)
                grouped_elements.setdefault(parent_id, []).append(element)
            else:
                root_elements.append(element)
        
        # Arrange root elements in a grid
        for i, element in enumerate(root_elements):
            row = i // cols
            col = i % cols
            element.x = 50 + col * grid_size
            element.y = 50 + row * grid_size
        
        # Arrange child elements around their parents
        for parent_id, children in grouped_elements.items():
            parent = next((e for e in self.canvas.elements if id(e) == parent_id), None)
            if parent:
                # Arrange children in a circle around the parent
                radius = max(parent.width, parent.height) + 100
                angle_step = 2 * math.pi / len(children)
                
                for i, child in enumerate(children):
                    angle = i * angle_step
                    child.x = parent.x + parent.width/2 + radius * math.cos(angle) - child.width/2
                    child.y = parent.y + parent.height/2 + radius * math.sin(angle) - child.height/2
        
        # Update the canvas
        self.canvas.update()
    
    def show_save_load_menu(self):
        """Show a popup menu with save, load, and export options"""
        save_load_menu = QMenu(self)
        
        # Save option
        save_action = QAction('Save Diagram', self)
        save_action.triggered.connect(self.save_diagram)
        save_load_menu.addAction(save_action)
        
        # Load option
        load_action = QAction('Load Diagram', self)
        load_action.triggered.connect(self.load_diagram)
        save_load_menu.addAction(load_action)
        
        # Add a separator
        save_load_menu.addSeparator()
        
        # Add Export submenu
        export_submenu = QMenu('Export', self)
        
        # Export as SVG
        svg_action = QAction('Export as SVG', self)
        svg_action.triggered.connect(self.export_svg)
        export_submenu.addAction(svg_action)
        
        # Export as PNG
        png_action = QAction('Export as PNG', self)
        png_action.triggered.connect(self.export_png)
        export_submenu.addAction(png_action)
        
        # Export as JPEG
        jpeg_action = QAction('Export as JPEG', self)
        jpeg_action.triggered.connect(self.export_jpeg)
        export_submenu.addAction(jpeg_action)
        
        # Export as HTML
        html_action = QAction('Export as HTML', self)
        html_action.triggered.connect(self.export_html)
        export_submenu.addAction(html_action)
        
        # Add the export submenu to the main menu
        save_load_menu.addMenu(export_submenu)
        
        # Show the menu at the position of the save button
        save_load_menu.exec_(self.sender().mapToGlobal(QPoint(0, self.sender().height())))
    
    def show_export_menu(self):
        """Show a popup menu with export options (kept for backward compatibility)
        Export functionality is now primarily accessed through the Save/Load menu"""
        export_menu = QMenu(self)
        
        # Export as SVG
        svg_action = QAction('Export as SVG', self)
        svg_action.triggered.connect(self.export_svg)
        export_menu.addAction(svg_action)
        
        # Export as PNG
        png_action = QAction('Export as PNG', self)
        png_action.triggered.connect(self.export_png)
        export_menu.addAction(png_action)
        
        # Export as JPEG
        jpeg_action = QAction('Export as JPEG', self)
        jpeg_action.triggered.connect(self.export_jpeg)
        export_menu.addAction(jpeg_action)
        
        # Export as HTML
        html_action = QAction('Export as HTML', self)
        html_action.triggered.connect(self.export_html)
        export_menu.addAction(html_action)
        
        # Show the menu at the position of the export button
        export_menu.exec_(self.sender().mapToGlobal(QPoint(0, self.sender().height())))
    
    def export_svg(self):
        """Export the diagram as SVG"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "", "SVG Files (*.svg)")
        if file_path:
            # If the user didn't add .svg extension, add it
            if not file_path.lower().endswith('.svg'):
                file_path += '.svg'
                
            # Create a QSvgGenerator to render the diagram
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            
            # Calculate the diagram bounds
            min_x, min_y, max_x, max_y = self._calculate_diagram_bounds()
            
            # Add some padding
            padding = 50
            width = max(max_x - min_x + 2 * padding, 100)
            height = max(max_y - min_y + 2 * padding, 100)
            
            # Set the size and viewbox
            generator.setSize(QSize(width, height))
            generator.setViewBox(QRect(-padding, -padding, width, height))
            generator.setTitle("D2 Diagram")
            generator.setDescription("Generated from D2 Diagram Designer")
            
            # Create a painter to paint on the SVG
            painter = QPainter()
            painter.begin(generator)
            
            # Enable antialiasing for smoother shapes
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            
            # Set the font to ensure it's embedded in the SVG
            font = QFont("Arial", 10)
            painter.setFont(font)
            
            # Translate to center the diagram
            painter.translate(-min_x + padding, -min_y + padding)
            
            # Draw a background matching the canvas color
            painter.fillRect(QRect(min_x - padding, min_y - padding, width, height), DARK_WIDGET_BG)
            
            # Draw the diagram elements
            for element in self.canvas.elements:
                # Draw containers first
                if element.children:
                    # Calculate container bounds
                    container_min_x = element.x
                    container_min_y = element.y
                    container_max_x = element.x + element.width
                    container_max_y = element.y + element.height
                    
                    for child in element.children:
                        container_min_x = min(container_min_x, child.x)
                        container_min_y = min(container_min_y, child.y)
                        container_max_x = max(container_max_x, child.x + child.width)
                        container_max_y = max(container_max_y, child.y + child.height)
                    
                    # Add padding
                    container_padding = 20
                    container_min_x -= container_padding
                    container_min_y -= container_padding
                    container_max_x += container_padding
                    container_max_y += container_padding
                    
                    # Draw container rectangle
                    container_rect = QRectF(container_min_x, container_min_y, 
                                          container_max_x - container_min_x, 
                                          container_max_y - container_min_y)
                    
                    # Use a light gray fill for containers
                    painter.setPen(QPen(QColor(100, 150, 100), 1.5))
                    painter.setBrush(QBrush(QColor(240, 245, 240)))
                    painter.drawRoundedRect(container_rect, 10, 10)
                    
                    # Draw container header
                    header_height = 30
                    header_rect = QRectF(container_min_x, container_min_y, 
                                       container_max_x - container_min_x, header_height)
                    painter.setBrush(QBrush(QColor(200, 220, 200)))
                    painter.drawRoundedRect(header_rect, 10, 10)
                    
                    # Draw container title
                    container_text = element.container_title if element.container_title else f"{element.label} Container"
                    painter.setPen(QPen(QColor(0, 0, 0)))
                    
                    # Use a bold font for the container title
                    title_font = QFont(font)
                    title_font.setBold(True)
                    title_font.setPointSize(11)
                    painter.setFont(title_font)
                    
                    # Draw the title text
                    text_rect = QRectF(container_min_x + 10, container_min_y, 
                                     container_max_x - container_min_x - 20, header_height)
                    painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, container_text)
                    
                    # Reset font
                    painter.setFont(font)
            
            # Draw connections
            for connection in self.canvas.connections:
                # Calculate connection points
                source_center = QPoint(connection.source.x + connection.source.width//2, 
                                     connection.source.y + connection.source.height//2)
                target_center = QPoint(connection.target.x + connection.target.width//2, 
                                     connection.target.y + connection.target.height//2)
                
                # Find intersection points with shape boundaries
                source_edge = connection._find_intersection_point(connection.source, source_center, target_center)
                target_edge = connection._find_intersection_point(connection.target, target_center, source_center)
                
                if source_edge and target_edge:
                    # Draw the connection line
                    painter.setPen(QPen(ARROW_COLOR, 1.5))
                    painter.drawLine(source_edge, target_edge)
                    
                    # Draw arrowhead
                    angle = connection._calculate_angle(source_edge, target_edge)
                    connection._draw_arrow_head(painter, target_edge, angle)
                    
                    # Draw label
                    if connection.label:
                        mid_point = QPoint((source_edge.x() + target_edge.x()) // 2,
                                         (source_edge.y() + target_edge.y()) // 2)
                        
                        # Set text color
                        painter.setPen(QPen(DARK_TEXT))
                        
                        # Use a standard font for connection labels
                        label_font = QFont(font)
                        label_font.setPointSize(9)
                        painter.setFont(label_font)
                        
                        # Calculate text rectangle for positioning
                        text_rect = painter.fontMetrics().boundingRect(connection.label)
                        text_rect.moveCenter(mid_point)
                        
                        # Add a small background for better readability
                        bg_rect = QRectF(text_rect)
                        bg_rect.adjust(-5, -2, 5, 2)
                        painter.fillRect(bg_rect, QColor(60, 60, 60, 220))
                        
                        # Draw text directly without background
                        painter.drawText(text_rect, Qt.AlignCenter, connection.label)
                        
                        # Reset font
                        painter.setFont(font)
            
            # Draw elements on top
            for element in self.canvas.elements:
                # Set pen based on element properties
                painter.setPen(QPen(element.border_color, 1))
                painter.setBrush(QBrush(element.color))
                
                # Draw the appropriate shape based on element type
                if isinstance(element, BoxElement):
                    painter.drawRect(element.x, element.y, element.width, element.height)
                elif isinstance(element, CircleElement):
                    painter.drawEllipse(element.x, element.y, element.width, element.height)
                elif isinstance(element, DiamondElement):
                    # Create a diamond shape using a polygon
                    points = [
                        QPoint(element.x + element.width // 2, element.y),  # Top
                        QPoint(element.x + element.width, element.y + element.height // 2),  # Right
                        QPoint(element.x + element.width // 2, element.y + element.height),  # Bottom
                        QPoint(element.x, element.y + element.height // 2)  # Left
                    ]
                    painter.drawPolygon(QPolygon(points))
                elif isinstance(element, HexagonElement):
                    # Create a hexagon shape using a polygon
                    w, h = element.width, element.height
                    points = [
                        QPoint(element.x + w // 4, element.y),  # Top left
                        QPoint(element.x + w * 3 // 4, element.y),  # Top right
                        QPoint(element.x + w, element.y + h // 2),  # Right
                        QPoint(element.x + w * 3 // 4, element.y + h),  # Bottom right
                        QPoint(element.x + w // 4, element.y + h),  # Bottom left
                        QPoint(element.x, element.y + h // 2)  # Left
                    ]
                    painter.drawPolygon(QPolygon(points))
                
                # Draw element label
                painter.setPen(QPen(ELEMENT_TEXT_COLOR))
                
                # Use a specific font for element labels
                element_font = QFont(font)
                element_font.setPointSize(10)
                painter.setFont(element_font)
                
                # Draw the text centered in the element
                painter.drawText(QRect(element.x, element.y, element.width, element.height), 
                               Qt.AlignCenter, element.label)
                
                # Reset font
                painter.setFont(font)
            
            # End painting
            painter.end()
            
            QMessageBox.information(self, "Export Successful", f"Diagram exported to {file_path}")
    
    def _calculate_diagram_bounds(self):
        """Calculate the bounds of the entire diagram"""
        if not self.canvas.elements:
            return 0, 0, 800, 600  # Default size if no elements
        
        # Start with the first element's bounds
        min_x = self.canvas.elements[0].x
        min_y = self.canvas.elements[0].y
        max_x = self.canvas.elements[0].x + self.canvas.elements[0].width
        max_y = self.canvas.elements[0].y + self.canvas.elements[0].height
        
        # Check all elements
        for element in self.canvas.elements:
            min_x = min(min_x, element.x)
            min_y = min(min_y, element.y)
            max_x = max(max_x, element.x + element.width)
            max_y = max(max_y, element.y + element.height)
        
        return min_x, min_y, max_x, max_y
    
    def export_png(self):
        """Export the diagram as PNG"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG Files (*.png)")
        if file_path:
            # If the user didn't add .png extension, add it
            if not file_path.lower().endswith('.png'):
                file_path += '.png'
                
            # Create a pixmap to render the diagram
            pixmap = QPixmap(self.canvas.size())
            pixmap.fill(Qt.transparent)
            
            # Create a painter to paint on the pixmap
            painter = QPainter(pixmap)
            
            # Render the canvas to the pixmap
            self.canvas.render(painter)
            
            # End painting
            painter.end()
            
            # Save the pixmap as PNG
            pixmap.save(file_path, "PNG")
            
            QMessageBox.information(self, "Export Successful", f"Diagram exported to {file_path}")
    
    def export_jpeg(self):
        """Export the diagram as JPEG"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export JPEG", "", "JPEG Files (*.jpg *.jpeg)")
        if file_path:
            # If the user didn't add .jpg extension, add it
            if not (file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg')):
                file_path += '.jpg'
                
            # Create a pixmap to render the diagram
            pixmap = QPixmap(self.canvas.size())
            pixmap.fill(QColor(40, 40, 40))  # Fill with dark background
            
            # Create a painter to paint on the pixmap
            painter = QPainter(pixmap)
            
            # Render the canvas to the pixmap
            self.canvas.render(painter)
            
            # End painting
            painter.end()
            
            # Save the pixmap as JPEG
            pixmap.save(file_path, "JPEG", 90)  # 90 is the quality (0-100)
            
            QMessageBox.information(self, "Export Successful", f"Diagram exported to {file_path}")
    
    def export_html(self):
        """Export the diagram as HTML with embedded SVG"""
        # Check if there are any elements to export
        if not self.canvas.elements and not self.canvas.connections:
            QMessageBox.warning(self, "Empty Diagram", "There are no elements to export. Please create a diagram first.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Export HTML", "", "HTML Files (*.html)")
        if file_path:
            # If the user didn't add .html extension, add it
            if not file_path.lower().endswith('.html'):
                file_path += '.html'
                
            # Get the D2 code
            d2_code = self.code_edit.toPlainText()
            
            # Generate SVG content with proper zoom to fit
            svg_content = self._generate_svg_for_html(ensure_fit=True)
            
            # Create HTML content with embedded SVG
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>D2 Diagram</title>
    <meta charset="utf-8">
    <style>
        body {{ background-color: #2d2d2d; color: #e0e0e0; font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        body.fullscreen {{ padding: 0; }}
        .container {{ display: flex; flex-direction: column; max-width: 1200px; margin: 0 auto; }}
        .container.fullscreen {{ max-width: 100%; height: 100vh; margin: 0; }}
        .diagram-container {{ background-color: #3c3c3c; padding: 20px; border-radius: 5px; margin-bottom: 20px; min-height: 400px; position: relative; overflow: hidden; }}
        .container.fullscreen .diagram-container {{ height: 100%; margin-bottom: 0; border-radius: 0; }}
        .diagram-controls {{ position: absolute; top: 10px; right: 10px; z-index: 10; background-color: rgba(60, 60, 60, 0.7); padding: 5px; border-radius: 5px; }}
        .diagram-controls button {{ background-color: #555; color: white; border: none; border-radius: 3px; margin: 2px; padding: 5px 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; }}
        .diagram-controls button:hover {{ background-color: #666; }}
        .diagram-controls button svg {{ width: 16px; height: 16px; }}
        .diagram-controls button svg path {{ fill: #e0e0e0; }}
        .diagram-wrapper {{ width: 100%; height: 100%; overflow: hidden; position: relative; }}
        .diagram {{ position: relative; transform-origin: 0 0; }}
        .code-container {{ background-color: #1e1e1e; padding: 20px; border-radius: 5px; position: relative; }}
        .container.fullscreen .code-container {{ display: none; }}
        .code {{ white-space: pre-wrap; font-family: monospace; margin: 0; }}
        .copy-button {{ position: absolute; top: 10px; right: 10px; background-color: #555; border: none; border-radius: 3px; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; z-index: 5; }}
        .copy-button:hover {{ background-color: #666; }}
        .copy-button svg {{ width: 16px; height: 16px; }}
        .copy-button svg path {{ fill: #e0e0e0; }}
        .copy-tooltip {{ position: absolute; top: 15px; right: 50px; background-color: #333; color: white; padding: 5px 10px; border-radius: 3px; display: none; font-size: 12px; }}
        h1, h2 {{ color: #e0e0e0; }}
        .container.fullscreen h1 {{ display: none; }}
        .container.fullscreen h2 {{ display: none; }}
        svg {{ max-width: 100%; height: auto; display: block; }}
    </style>
</head>
<body>
    <div class="container" id="main-container">
        <h1>D2 Diagram</h1>
        <div class="diagram-container">
            <div class="diagram-controls">
                <button id="zoom-in" title="Zoom In">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
                    </svg>
                </button>
                <button id="zoom-out" title="Zoom Out">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 13H5v-2h14v2z"/>
                    </svg>
                </button>
                <button id="zoom-fit" title="Zoom to Fit">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 4H6c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H6V6h12v12z"/>
                    </svg>
                </button>
                <button id="fullscreen" title="Toggle Fullscreen">
                    <svg id="fullscreen-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                    </svg>
                    <svg id="exit-fullscreen-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="display: none;">
                        <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
                    </svg>
                </button>
            </div>
            <div class="diagram-wrapper">
                <div class="diagram" id="diagram">
                    {svg_content}
                </div>
            </div>
        </div>
        <h2>D2 Code</h2>
        <div class="code-container">
            <button class="copy-button" id="copy-button" title="Copy to clipboard">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M16 1H4C2.9 1 2 1.9 2 3v14h2V3h12V1zm3 4H8C6.9 5 6 5.9 6 7v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                </svg>
            </button>
            <div class="copy-tooltip" id="copy-tooltip">Copied!</div>
            <pre class="code" id="d2-code">{d2_code.replace('<', '&lt;').replace('>', '&gt;')}</pre>
        </div>
    </div>
    
    <script>
        // Pan and zoom functionality
        (function() {{
            const container = document.getElementById('main-container');
            const diagramContainer = document.querySelector('.diagram-container');
            const diagramWrapper = document.querySelector('.diagram-wrapper');
            const diagram = document.getElementById('diagram');
            const zoomInBtn = document.getElementById('zoom-in');
            const zoomOutBtn = document.getElementById('zoom-out');
            const zoomFitBtn = document.getElementById('zoom-fit');
            const fullscreenBtn = document.getElementById('fullscreen');
            const fullscreenIcon = document.getElementById('fullscreen-icon');
            const exitFullscreenIcon = document.getElementById('exit-fullscreen-icon');
            
            let scale = 1;
            let translateX = 0;
            let translateY = 0;
            let isDragging = false;
            let startX, startY;
            let lastTranslateX = 0;
            let lastTranslateY = 0;
            let isFullscreen = false;
            
            // Apply transform
            function applyTransform() {{
                diagram.style.transform = `translate(${{translateX}}px, ${{translateY}}px) scale(${{scale}})`;
            }}
            
            // Reset transform
            function resetTransform() {{
                scale = 1;
                translateX = 0;
                translateY = 0;
                applyTransform();
            }}
            
            // Zoom to fit
            function zoomToFit() {{
                const svgElement = diagram.querySelector('svg');
                if (svgElement) {{
                    // Get container dimensions
                    const containerWidth = diagramWrapper.clientWidth;
                    const containerHeight = diagramWrapper.clientHeight;
                    
                    // Find diagram bounds by examining actual elements
                    // This is more precise than using SVG dimensions which may have empty space
                    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                    
                    // Check all diagram elements (shapes, text, etc)
                    const elements = svgElement.querySelectorAll('rect, circle, ellipse, polygon, path, text, g');
                    elements.forEach(el => {{
                        // Try to get element bounding box
                        try {{
                            const bbox = el.getBBox();
                            minX = Math.min(minX, bbox.x);
                            minY = Math.min(minY, bbox.y);
                            maxX = Math.max(maxX, bbox.x + bbox.width);
                            maxY = Math.max(maxY, bbox.y + bbox.height);
                        }} catch (e) {{
                            // Some elements might not have bbox, ignore them
                        }}
                    }});
                    
                    // Fallback to SVG dimensions if we couldn't find elements
                    if (minX === Infinity || maxX === -Infinity) {{
                        minX = 0;
                        minY = 0;
                        maxX = svgElement.width.baseVal.value;
                        maxY = svgElement.height.baseVal.value;
                    }}
                    
                    // Calculate the actual content width and height
                    const contentWidth = maxX - minX;
                    const contentHeight = maxY - minY;
                    
                    // Add padding (5% on each side)
                    const padding = 0.1;
                    const paddedWidth = contentWidth * (1 + padding);
                    const paddedHeight = contentHeight * (1 + padding);
                    
                    // Calculate scale to fit the padded content
                    const scaleX = containerWidth / paddedWidth;
                    const scaleY = containerHeight / paddedHeight;
                    scale = Math.min(scaleX, scaleY);
                    
                    // Calculate center of content
                    const contentCenterX = minX + contentWidth / 2;
                    const contentCenterY = minY + contentHeight / 2;
                    
                    // Center the diagram - translate to container center, then offset by scaled content center
                    translateX = containerWidth / 2 - contentCenterX * scale;
                    translateY = containerHeight / 2 - contentCenterY * scale;
                    
                    applyTransform();
                }}
            }}
            
            // Toggle fullscreen
            function toggleFullscreen() {{
                isFullscreen = !isFullscreen;
                
                if (isFullscreen) {{
                    container.classList.add('fullscreen');
                    document.body.classList.add('fullscreen');
                    fullscreenIcon.style.display = 'none';
                    exitFullscreenIcon.style.display = 'block';
                }} else {{
                    container.classList.remove('fullscreen');
                    document.body.classList.remove('fullscreen');
                    fullscreenIcon.style.display = 'block';
                    exitFullscreenIcon.style.display = 'none';
                }}
                
                // Adjust view when toggling fullscreen
                setTimeout(zoomToFit, 100);
            }}
            
            // Zoom in
            zoomInBtn.addEventListener('click', function() {{
                scale += 0.1;
                applyTransform();
            }});
            
            // Zoom out
            zoomOutBtn.addEventListener('click', function() {{
                if (scale > 0.2) {{
                    scale -= 0.1;
                    applyTransform();
                }}
            }});
            
            // Zoom to fit
            zoomFitBtn.addEventListener('click', zoomToFit);
            
            // Fullscreen
            fullscreenBtn.addEventListener('click', toggleFullscreen);
            
            // Keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'f' || e.key === 'F') {{
                    toggleFullscreen();
                }} else if (e.key === '0') {{
                    zoomToFit();
                }} else if (e.key === 'Escape' && isFullscreen) {{
                    toggleFullscreen();
                }}
            }});
            
            // Mouse wheel zoom
            diagramContainer.addEventListener('wheel', function(e) {{
                e.preventDefault();
                
                // Get mouse position relative to diagram
                const rect = diagramWrapper.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                // Calculate zoom
                const delta = e.deltaY > 0 ? -0.1 : 0.1;
                const newScale = Math.max(0.2, scale + delta);
                
                // Calculate new translate to zoom at mouse position
                const scaleRatio = newScale / scale;
                const newTranslateX = mouseX - (mouseX - translateX) * scaleRatio;
                const newTranslateY = mouseY - (mouseY - translateY) * scaleRatio;
                
                // Apply new values
                scale = newScale;
                translateX = newTranslateX;
                translateY = newTranslateY;
                
                applyTransform();
            }});
            
            // Mouse drag
            diagramContainer.addEventListener('mousedown', function(e) {{
                if (e.button === 0) {{ // Left mouse button
                    isDragging = true;
                    startX = e.clientX;
                    startY = e.clientY;
                    lastTranslateX = translateX;
                    lastTranslateY = translateY;
                    diagramContainer.style.cursor = 'grabbing';
                }}
            }});
            
            document.addEventListener('mousemove', function(e) {{
                if (isDragging) {{
                    translateX = lastTranslateX + (e.clientX - startX);
                    translateY = lastTranslateY + (e.clientY - startY);
                    applyTransform();
                }}
            }});
            
            document.addEventListener('mouseup', function() {{
                isDragging = false;
                diagramContainer.style.cursor = 'default';
            }});
            
            // Touch support for mobile devices
            diagramContainer.addEventListener('touchstart', function(e) {{
                if (e.touches.length === 1) {{
                    isDragging = true;
                    startX = e.touches[0].clientX;
                    startY = e.touches[0].clientY;
                    lastTranslateX = translateX;
                    lastTranslateY = translateY;
                    e.preventDefault();
                }}
            }});
            
            diagramContainer.addEventListener('touchmove', function(e) {{
                if (isDragging && e.touches.length === 1) {{
                    translateX = lastTranslateX + (e.touches[0].clientX - startX);
                    translateY = lastTranslateY + (e.touches[0].clientY - startY);
                    applyTransform();
                    e.preventDefault();
                }}
            }});
            
            diagramContainer.addEventListener('touchend', function() {{
                isDragging = false;
            }});
            
            // Initialize with a slight delay to ensure SVG is loaded
            setTimeout(zoomToFit, 100);
        }})();
        
        // Copy to clipboard functionality
        (function() {{
            const copyButton = document.getElementById('copy-button');
            const codeElement = document.getElementById('d2-code');
            const tooltip = document.getElementById('copy-tooltip');
            
            copyButton.addEventListener('click', function() {{
                // Create a temporary textarea element to copy the text
                const textarea = document.createElement('textarea');
                textarea.value = codeElement.textContent;
                document.body.appendChild(textarea);
                textarea.select();
                
                try {{
                    // Execute the copy command
                    const successful = document.execCommand('copy');
                    
                    // Show the tooltip
                    if (successful) {{
                        tooltip.style.display = 'block';
                        
                        // Hide the tooltip after 2 seconds
                        setTimeout(function() {{
                            tooltip.style.display = 'none';
                        }}, 2000);
                    }}
                }} catch (err) {{
                    console.error('Unable to copy', err);
                }}
                
                // Remove the temporary textarea
                document.body.removeChild(textarea);
            }});
        }})();
    </script>
</body>
</html>"""
            
            # Write the HTML content to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            QMessageBox.information(self, "Export Successful", f"Diagram exported to {file_path}")
    
    def _generate_svg_for_html(self, ensure_fit=False):
        """Generate SVG content for embedding in HTML
        
        Args:
            ensure_fit: If True, ensures the diagram is properly scaled to fit all elements
        """
        # Create a QSvgGenerator to render the diagram to a string
        svg_bytes = QByteArray()
        buffer = QBuffer(svg_bytes)
        buffer.open(QIODevice.WriteOnly)
        
        generator = QSvgGenerator()
        generator.setOutputDevice(buffer)
        
        # Calculate the diagram bounds
        min_x, min_y, max_x, max_y = self._calculate_diagram_bounds()
        
        # Add generous padding
        padding = 80
        width = max(max_x - min_x + 2 * padding, 100)
        height = max(max_y - min_y + 2 * padding, 100)
        
        # Set the size and viewbox
        generator.setSize(QSize(width, height))
        generator.setViewBox(QRect(-padding, -padding, width, height))
        generator.setTitle("D2 Diagram")
        generator.setDescription("Generated from D2 Diagram Designer")
        
        # Create a painter to paint on the SVG
        painter = QPainter()
        painter.begin(generator)
        
        # Enable antialiasing for smoother shapes
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # Set the font to ensure it's embedded in the SVG
        font = QFont("Arial", 10)
        painter.setFont(font)
        
        # Translate to center the diagram
        painter.translate(-min_x + padding, -min_y + padding)
        
        # Draw the background matching the canvas background color
        painter.fillRect(QRect(min_x - padding, min_y - padding, width, height), DARK_WIDGET_BG)
        
        # Draw the diagram elements
        for element in self.canvas.elements:
            # Draw containers first
            if hasattr(element, 'children') and element.children:
                # Calculate container bounds
                container_min_x = element.x
                container_min_y = element.y
                container_max_x = element.x + element.width
                container_max_y = element.y + element.height
                
                for child in element.children:
                    container_min_x = min(container_min_x, child.x)
                    container_min_y = min(container_min_y, child.y)
                    container_max_x = max(container_max_x, child.x + child.width)
                    container_max_y = max(container_max_y, child.y + child.height)
                
                # Add padding
                container_padding = 20
                container_min_x -= container_padding
                container_min_y -= container_padding
                container_max_x += container_padding
                container_max_y += container_padding
                
                # Draw container rectangle
                container_rect = QRectF(container_min_x, container_min_y, 
                                      container_max_x - container_min_x, 
                                      container_max_y - container_min_y)
                
                # Use a light gray fill for containers
                painter.setPen(QPen(QColor(100, 150, 100), 1.5))
                painter.setBrush(QBrush(QColor(240, 245, 240)))
                painter.drawRoundedRect(container_rect, 10, 10)
                
                # Draw container header
                header_height = 30
                header_rect = QRectF(container_min_x, container_min_y, 
                                   container_max_x - container_min_x, header_height)
                painter.setBrush(QBrush(QColor(200, 220, 200)))
                painter.drawRoundedRect(header_rect, 10, 10)
                
                # Draw container title
                container_text = element.container_title if hasattr(element, 'container_title') and element.container_title else f"{element.label} Container"
                painter.setPen(QPen(QColor(0, 0, 0)))
                
                # Use a bold font for the container title
                title_font = QFont(font)
                title_font.setBold(True)
                title_font.setPointSize(11)
                painter.setFont(title_font)
                
                # Draw the title text
                text_rect = QRectF(container_min_x + 10, container_min_y, 
                                 container_max_x - container_min_x - 20, header_height)
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, container_text)
                
                # Reset font
                painter.setFont(font)
        
        # Draw connections
        for connection in self.canvas.connections:
            # Calculate connection points
            source_center = QPoint(connection.source.x + connection.source.width//2, 
                                 connection.source.y + connection.source.height//2)
            target_center = QPoint(connection.target.x + connection.target.width//2, 
                                 connection.target.y + connection.target.height//2)
            
            # Find intersection points with shape boundaries
            source_edge = connection._find_intersection_point(connection.source, source_center, target_center)
            target_edge = connection._find_intersection_point(connection.target, target_center, source_center)
            
            if source_edge and target_edge:
                # Draw the connection line
                painter.setPen(QPen(ARROW_COLOR, 1.5))
                painter.drawLine(source_edge, target_edge)
                
                # Draw arrowhead
                angle = connection._calculate_angle(source_edge, target_edge)
                connection._draw_arrow_head(painter, target_edge, angle)
                
                # Draw label
                if connection.label:
                    mid_point = QPoint((source_edge.x() + target_edge.x()) // 2,
                                     (source_edge.y() + target_edge.y()) // 2)
                    
                    # Set text color
                    painter.setPen(QPen(DARK_TEXT))
                    
                    # Use a standard font for connection labels
                    label_font = QFont(font)
                    label_font.setPointSize(9)
                    painter.setFont(label_font)
                    
                    # Calculate text rectangle for positioning
                    text_rect = painter.fontMetrics().boundingRect(connection.label)
                    text_rect.moveCenter(mid_point)
                    
                    # Add a small white background for better readability
                    bg_rect = QRectF(text_rect)
                    bg_rect.adjust(-5, -2, 5, 2)
                    painter.fillRect(bg_rect, QColor(60, 60, 60, 220))
                    
                    # Draw text
                    painter.drawText(text_rect, Qt.AlignCenter, connection.label)
                    
                    # Reset font
                    painter.setFont(font)
        
        # Draw elements on top
        for element in self.canvas.elements:
            # Set pen based on element properties
            painter.setPen(QPen(element.border_color, 1))
            painter.setBrush(QBrush(element.color))
            
            # Draw the appropriate shape based on element type
            if isinstance(element, BoxElement):
                painter.drawRect(element.x, element.y, element.width, element.height)
            elif isinstance(element, CircleElement):
                painter.drawEllipse(element.x, element.y, element.width, element.height)
            elif isinstance(element, DiamondElement):
                # Create a diamond shape using a polygon
                points = [
                    QPoint(element.x + element.width // 2, element.y),  # Top
                    QPoint(element.x + element.width, element.y + element.height // 2),  # Right
                    QPoint(element.x + element.width // 2, element.y + element.height),  # Bottom
                    QPoint(element.x, element.y + element.height // 2)  # Left
                ]
                painter.drawPolygon(QPolygon(points))
            elif isinstance(element, HexagonElement):
                # Create a hexagon shape using a polygon
                w, h = element.width, element.height
                points = [
                    QPoint(element.x + w // 4, element.y),  # Top left
                    QPoint(element.x + w * 3 // 4, element.y),  # Top right
                    QPoint(element.x + w, element.y + h // 2),  # Right
                    QPoint(element.x + w * 3 // 4, element.y + h),  # Bottom right
                    QPoint(element.x + w // 4, element.y + h),  # Bottom left
                    QPoint(element.x, element.y + h // 2)  # Left
                ]
                painter.drawPolygon(QPolygon(points))
            
            # Draw element label
            painter.setPen(QPen(ELEMENT_TEXT_COLOR))
            
            # Use a specific font for element labels
            element_font = QFont(font)
            element_font.setPointSize(10)
            painter.setFont(element_font)
            
            # Draw the text centered in the element
            painter.drawText(QRect(element.x, element.y, element.width, element.height), 
                           Qt.AlignCenter, element.label)
            
            # Reset font
            painter.setFont(font)
        
        # End painting
        painter.end()
        buffer.close()
        
        # Convert the SVG bytes to a string and return
        svg_string = str(svg_bytes.data(), 'utf-8')
        return svg_string
        
    def _draw_grid_for_svg(self, painter, x, y, width, height):
        """Draw a grid similar to the canvas grid for SVG export"""
        # Grid is now hidden in exports
        pass
        
    def save_state(self):
        """Save the current state of the diagram for undo functionality"""
        print("SAVE_STATE called - Elements:", len(self.canvas.elements), "Connections:", len(self.canvas.connections))
        
        # Don't save state if there are no elements or connections
        if not self.canvas.elements and not self.canvas.connections:
            print("Not saving empty state")
            return
        
        # Create a deep copy of the current state
        state = {
            'elements': [],
            'connections': []
        }
        
        # Save elements
        for element in self.canvas.elements:
            element_data = {
                'type': type(element).__name__,
                'x': element.x,
                'y': element.y,
                'width': element.width,
                'height': element.height,
                'label': element.label,
                'color': element.color.name(),
                'border_color': element.border_color.name(),
                'id': element.id,
                'parent_id': element.parent.id if element.parent else None,
                'children_ids': [child.id for child in element.children],
                'container_title': element.container_title
            }
            state['elements'].append(element_data)
        
        # Save connections
        for connection in self.canvas.connections:
            connection_data = {
                'source_id': connection.source.id,
                'target_id': connection.target.id,
                'label': connection.label
            }
            state['connections'].append(connection_data)
        
        # Add to undo stack
        self.undo_stack.append(state)
        print("Added state to undo stack - Stack size:", len(self.undo_stack))
        
        # Clear redo stack when a new action is performed
        if self.redo_stack:
            self.redo_stack.clear()
            print("Cleared redo stack")
        
        # Limit the size of the undo stack
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
            print("Removed oldest state from undo stack - Stack size:", len(self.undo_stack))
    
    def undo_action(self):
        """Undo the last action"""
        print("UNDO_ACTION called - Undo stack size:", len(self.undo_stack))
        
        if not self.undo_stack:
            print("Nothing to undo - undo stack is empty")
            return  # Nothing to undo
        
        # Save current state to redo stack
        current_state = {
            'elements': [],
            'connections': []
        }
        
        # Save current elements
        for element in self.canvas.elements:
            element_data = {
                'type': type(element).__name__,
                'x': element.x,
                'y': element.y,
                'width': element.width,
                'height': element.height,
                'label': element.label,
                'color': element.color.name(),
                'border_color': element.border_color.name(),
                'id': element.id,
                'parent_id': element.parent.id if element.parent else None,
                'children_ids': [child.id for child in element.children],
                'container_title': element.container_title
            }
            current_state['elements'].append(element_data)
        
        # Save current connections
        for connection in self.canvas.connections:
            connection_data = {
                'source_id': connection.source.id,
                'target_id': connection.target.id,
                'label': connection.label
            }
            current_state['connections'].append(connection_data)
        
        # Add current state to redo stack
        self.redo_stack.append(current_state)
        print("Added current state to redo stack - Redo stack size:", len(self.redo_stack))
        
        # Get the previous state
        previous_state = self.undo_stack.pop()
        print("Popped state from undo stack - Elements:", len(previous_state['elements']), "Connections:", len(previous_state['connections']))
        
        # Temporarily disconnect the diagram_changed signal to avoid recursion
        self.canvas.diagram_changed.disconnect(self.update_d2_code)
        
        # Clear current canvas
        self.canvas.elements.clear()
        self.canvas.connections.clear()
        self.canvas.selected_elements.clear()
        self.canvas.selected_connections.clear()
        
        # Create a mapping from old IDs to new elements
        id_to_element = {}
        
        # Recreate elements from the previous state
        for element_data in previous_state['elements']:
            # Create the element based on its type
            element_type = element_data['type']
            if element_type == 'BoxElement':
                element = BoxElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            elif element_type == 'CircleElement':
                element = CircleElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            elif element_type == 'DiamondElement':
                element = DiamondElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            elif element_type == 'HexagonElement':
                element = HexagonElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            else:
                continue  # Skip unknown element types
            
            # Set properties
            element.id = element_data['id']
            element.color = QColor(element_data['color'])
            element.border_color = QColor(element_data['border_color'])
            element.container_title = element_data['container_title']
            
            # Add to canvas
            self.canvas.elements.append(element)
            
            # Store in mapping
            id_to_element[element.id] = element
        
        # Restore parent-child relationships
        for element_data in previous_state['elements']:
            if element_data['parent_id'] is not None and element_data['id'] in id_to_element and element_data['parent_id'] in id_to_element:
                child = id_to_element[element_data['id']]
                parent = id_to_element[element_data['parent_id']]
                child.parent = parent
                parent.children.append(child)
        
        # Recreate connections
        for connection_data in previous_state['connections']:
            if connection_data['source_id'] in id_to_element and connection_data['target_id'] in id_to_element:
                source = id_to_element[connection_data['source_id']]
                target = id_to_element[connection_data['target_id']]
                connection = ArrowConnection(source, target, connection_data['label'])
                self.canvas.connections.append(connection)
        
        # Update the canvas
        self.canvas.update()
        
        # Generate D2 code from the diagram
        d2_code = self.canvas.generate_d2_code()
        
        # Temporarily disconnect the textChanged signal to avoid recursion
        self.code_edit.textChanged.disconnect(self.on_code_changed)
        
        # Update the code panel
        self.code_edit.setPlainText(d2_code)
        
        # Reconnect the signals
        self.code_edit.textChanged.connect(self.on_code_changed)
        self.canvas.diagram_changed.connect(self.update_d2_code)
        
        print("Undo completed - Canvas now has", len(self.canvas.elements), "elements and", len(self.canvas.connections), "connections")

    def redo_action(self):
        """Redo the last undone action"""
        print("REDO_ACTION called - Redo stack size:", len(self.redo_stack))
        
        if not self.redo_stack:
            print("Nothing to redo - redo stack is empty")
            return  # Nothing to redo
        
        # Save current state to undo stack
        current_state = {
            'elements': [],
            'connections': []
        }
        
        # Save current elements
        for element in self.canvas.elements:
            element_data = {
                'type': type(element).__name__,
                'x': element.x,
                'y': element.y,
                'width': element.width,
                'height': element.height,
                'label': element.label,
                'color': element.color.name(),
                'border_color': element.border_color.name(),
                'id': element.id,
                'parent_id': element.parent.id if element.parent else None,
                'children_ids': [child.id for child in element.children],
                'container_title': element.container_title
            }
            current_state['elements'].append(element_data)
        
        # Save current connections
        for connection in self.canvas.connections:
            connection_data = {
                'source_id': connection.source.id,
                'target_id': connection.target.id,
                'label': connection.label
            }
            current_state['connections'].append(connection_data)
        
        # Add current state to undo stack
        self.undo_stack.append(current_state)
        print("Added current state to undo stack - Undo stack size:", len(self.undo_stack))
        
        # Get the next state from redo stack
        next_state = self.redo_stack.pop()
        print("Popped state from redo stack - Elements:", len(next_state['elements']), "Connections:", len(next_state['connections']))
        
        # Temporarily disconnect the diagram_changed signal to avoid recursion
        self.canvas.diagram_changed.disconnect(self.update_d2_code)
        
        # Clear current canvas
        self.canvas.elements.clear()
        self.canvas.connections.clear()
        self.canvas.selected_elements.clear()
        self.canvas.selected_connections.clear()
        
        # Create a mapping from old IDs to new elements
        id_to_element = {}
        
        # Recreate elements from the next state
        for element_data in next_state['elements']:
            # Create the element based on its type
            element_type = element_data['type']
            if element_type == 'BoxElement':
                element = BoxElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            elif element_type == 'CircleElement':
                element = CircleElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            elif element_type == 'DiamondElement':
                element = DiamondElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            elif element_type == 'HexagonElement':
                element = HexagonElement(element_data['x'], element_data['y'], element_data['width'], element_data['height'], element_data['label'])
            else:
                continue  # Skip unknown element types
            
            # Set properties
            element.id = element_data['id']
            element.color = QColor(element_data['color'])
            element.border_color = QColor(element_data['border_color'])
            element.container_title = element_data['container_title']
            
            # Add to canvas
            self.canvas.elements.append(element)
            
            # Store in mapping
            id_to_element[element.id] = element
        
        # Restore parent-child relationships
        for element_data in next_state['elements']:
            if element_data['parent_id'] is not None and element_data['id'] in id_to_element and element_data['parent_id'] in id_to_element:
                child = id_to_element[element_data['id']]
                parent = id_to_element[element_data['parent_id']]
                child.parent = parent
                parent.children.append(child)
        
        # Recreate connections
        for connection_data in next_state['connections']:
            if connection_data['source_id'] in id_to_element and connection_data['target_id'] in id_to_element:
                source = id_to_element[connection_data['source_id']]
                target = id_to_element[connection_data['target_id']]
                connection = ArrowConnection(source, target, connection_data['label'])
                self.canvas.connections.append(connection)
        
        # Update the canvas
        self.canvas.update()
        
        # Generate D2 code from the diagram
        d2_code = self.canvas.generate_d2_code()
        
        # Temporarily disconnect the textChanged signal to avoid recursion
        self.code_edit.textChanged.disconnect(self.on_code_changed)
        
        # Update the code panel
        self.code_edit.setPlainText(d2_code)
        
        # Reconnect the signals
        self.code_edit.textChanged.connect(self.on_code_changed)
        self.canvas.diagram_changed.connect(self.update_d2_code)
        
        print("Redo completed - Canvas now has", len(self.canvas.elements), "elements and", len(self.canvas.connections), "connections")

    def title_bar_mouse_press(self, event):
        """Handle mouse press events on the title bar for window dragging"""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def title_bar_mouse_move(self, event):
        """Handle mouse move events on the title bar for window dragging"""
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
    
    def toggle_maximize(self):
        """Toggle between maximized and normal window state"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


class InlinePropertiesPanel(QWidget):
    """Compact inline properties panel for the toolbar"""
    property_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.element = None
        self.canvas = None  # Reference to the canvas
        self.setup_ui()
        self.setVisible(False)  # Hidden by default
    
    def setup_ui(self):
        # Create a horizontal layout for the panel
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(4)
        
        # Label field
        label_layout = QHBoxLayout()
        label_layout.setSpacing(2)
        label_label = QLabel("Label:")
        label_label.setStyleSheet("color: #e0e0e0; font-size: 11px; background: transparent;")
        self.label_edit = QLineEdit()
        self.label_edit.setFixedWidth(100)
        self.label_edit.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3c3c3c;
                border-radius: 2px;
                padding: 2px 4px;
                font-size: 11px;
                max-height: 20px;
            }
        """)
        self.label_edit.textChanged.connect(self.apply_changes)
        label_layout.addWidget(label_label)
        label_layout.addWidget(self.label_edit)
        layout.addLayout(label_layout)
        
        # Add a small separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setStyleSheet("background-color: #505050;")
        separator1.setFixedHeight(20)  # Limit separator height
        layout.addWidget(separator1)
        
        # Size controls with +/- buttons
        size_layout = QHBoxLayout()
        size_layout.setSpacing(2)
        
        # Width controls
        width_label = QLabel("W:")
        width_label.setStyleSheet("color: #e0e0e0; font-size: 11px; background: transparent;")
        self.width_value = QLabel("100")
        self.width_value.setStyleSheet("color: #e0e0e0; font-size: 11px; min-width: 25px; background: transparent;")
        self.width_value.setAlignment(Qt.AlignCenter)
        
        width_minus_btn = QPushButton("-")
        width_minus_btn.setFixedSize(20, 20)
        width_minus_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 2px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """)
        width_minus_btn.clicked.connect(self.decrease_width)
        
        width_plus_btn = QPushButton("+")
        width_plus_btn.setFixedSize(20, 20)
        width_plus_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 2px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """)
        width_plus_btn.clicked.connect(self.increase_width)
        
        size_layout.addWidget(width_label)
        size_layout.addWidget(width_minus_btn)
        size_layout.addWidget(self.width_value)
        size_layout.addWidget(width_plus_btn)
        
        # Height controls
        height_label = QLabel("H:")
        height_label.setStyleSheet("color: #e0e0e0; font-size: 11px; background: transparent;")
        self.height_value = QLabel("60")
        self.height_value.setStyleSheet("color: #e0e0e0; font-size: 11px; min-width: 25px; background: transparent;")
        self.height_value.setAlignment(Qt.AlignCenter)
        
        height_minus_btn = QPushButton("-")
        height_minus_btn.setFixedSize(20, 20)
        height_minus_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 2px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """)
        height_minus_btn.clicked.connect(self.decrease_height)
        
        height_plus_btn = QPushButton("+")
        height_plus_btn.setFixedSize(20, 20)
        height_plus_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 2px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """)
        height_plus_btn.clicked.connect(self.increase_height)
        
        size_layout.addWidget(height_label)
        size_layout.addWidget(height_minus_btn)
        size_layout.addWidget(self.height_value)
        size_layout.addWidget(height_plus_btn)
        
        layout.addLayout(size_layout)
        
        # Add a small separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setStyleSheet("background-color: #505050;")
        separator2.setFixedHeight(20)
        layout.addWidget(separator2)
        
        # Color selection with desaturated colors
        color_layout = QHBoxLayout()
        color_layout.setSpacing(2)
        
        color_label = QLabel("Color:")
        color_label.setStyleSheet("color: #e0e0e0; font-size: 11px; background: transparent;")
        color_layout.addWidget(color_label)
        
        # Define a set of bright vibrant colors for the toolbar
        self.colors = [
            QColor(180, 180, 180),    # Light Grey
            QColor(100, 181, 246),    # Bright Blue
            QColor(129, 199, 132),    # Bright Green
            QColor(255, 241, 118),    # Bright Yellow
            QColor(255, 183, 77),     # Bright Orange
            QColor(244, 67, 54),      # Bright Red
            QColor(149, 117, 205)     # Bright Purple
        ]
        
        self.color_buttons = []
        for color in self.colors:
            # Use our custom ColorButton class instead of QPushButton
            color_btn = ColorButton(color, self)
            color_btn.colorSelected.connect(self.set_color_and_update)
            color_layout.addWidget(color_btn)
            self.color_buttons.append(color_btn)
        
        layout.addLayout(color_layout)
        
        # Set the layout
        self.setLayout(layout)
        self.setStyleSheet("background-color: #333333; border-radius: 3px;")
    
    def set_element(self, element):
        """Set the element to edit and update the UI"""
        self.element = element
        
        # Find the canvas in the parent hierarchy
        parent = self.parent()
        while parent and not isinstance(parent, DiagramDesigner):
            parent = parent.parent()
        
        if parent and isinstance(parent, DiagramDesigner):
            self.canvas = parent.canvas
        
        if element:
            self.label_edit.setText(element.label)
            self.width_value.setText(str(element.width))
            self.height_value.setText(str(element.height))
            self.update_color_buttons()
            self.setVisible(True)
        else:
            self.setVisible(False)
    
    def update_color_buttons(self):
        """Update the color buttons to show which one is selected"""
        if not self.element:
            return
            
        # Find the closest color in our palette
        closest_color = self.colors[0]
        closest_distance = self.color_distance(self.element.color, closest_color)
        
        for color in self.colors:
            distance = self.color_distance(self.element.color, color)
            if distance < closest_distance:
                closest_distance = distance
                closest_color = color
        
        # Update button styles
        for i, color in enumerate(self.colors):
            self.color_buttons[i].updateStyleSheet(color == closest_color)
    
    def color_distance(self, color1, color2):
        """Calculate the distance between two colors in RGB space"""
        return (color1.red() - color2.red())**2 + \
               (color1.green() - color2.green())**2 + \
               (color1.blue() - color2.blue())**2
    
    def increase_width(self):
        """Increase the element width by 10px"""
        if self.element and self.canvas:
            new_width = min(500, self.element.width + 10)  # Increased max width to 500px
            self.canvas.resize_element(self.element, new_width, self.element.height)
            self.width_value.setText(str(self.element.width))
            self.apply_changes()
    
    def decrease_width(self):
        """Decrease the element width by 10px"""
        if self.element and self.canvas:
            # Calculate the minimum width based on text content
            min_width, _ = self.element._calculate_min_size_for_text(self.element.label)
            
            # Ensure we don't go below the minimum width needed for text
            new_width = max(min_width, self.element.width - 10)
            
            self.canvas.resize_element(self.element, new_width, self.element.height)
            self.width_value.setText(str(self.element.width))
            self.apply_changes()
    
    def increase_height(self):
        """Increase the element height by 10px"""
        if self.element and self.canvas:
            new_height = min(500, self.element.height + 10)  # Increased max height to 500px
            self.canvas.resize_element(self.element, self.element.width, new_height)
            self.height_value.setText(str(self.element.height))
            self.apply_changes()
    
    def decrease_height(self):
        """Decrease the element height by 10px"""
        if self.element and self.canvas:
            # Calculate the minimum height based on text content
            _, min_height = self.element._calculate_min_size_for_text(self.element.label)
            
            # Ensure we don't go below the minimum height needed for text
            new_height = max(min_height, self.element.height - 10)
            
            self.canvas.resize_element(self.element, self.element.width, new_height)
            self.height_value.setText(str(self.element.height))
            self.apply_changes()
    
    def set_color(self, color):
        """Set the element color"""
        if self.element:
            self.element.color = color
            self.update_color_buttons()
            self.apply_changes()
    
    def set_color_and_update(self, color):
        """Set the element color and immediately update the canvas"""
        if self.element:
            self.element.color = color
            self.update_color_buttons()
            self.apply_changes()
            
            # Force an immediate canvas update
            if self.canvas:
                self.canvas.update()
    
    def apply_changes(self):
        """Apply changes to the element"""
        if self.element:
            old_label = self.element.label
            new_label = self.label_edit.text()
            
            # Update the element properties
            self.element.label = new_label
            
            # If the label changed, recalculate the element size
            if old_label != new_label:
                # Calculate minimum size based on new text
                min_width, min_height = self.element._calculate_min_size_for_text(new_label)
                
                # Use the larger of the current size or the minimum required size
                self.element.width = max(self.element.width, min_width)
                self.element.height = max(self.element.height, min_height)
            
            # Notify that properties have changed
            self.property_changed.emit()
    
    def hide_panel(self):
        """Hide the panel"""
        self.setVisible(False)
        self.element = None


class ColorButton(QPushButton):
    """Custom button that shows a dropdown of color shades when held"""
    colorSelected = pyqtSignal(QColor)
    
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.base_color = color
        self.shade_popup = None
        self.long_press_timer = None
        self.pressed = False
        self.setFixedSize(16, 16)
        self.updateStyleSheet()
        
    def updateStyleSheet(self, selected=False):
        """Update the button style based on selection state"""
        border = "2px solid #00FFFF" if selected else "1px solid #646464"
        hover = "" if selected else "QPushButton:hover { border: 1px solid #e0e0e0; }"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({self.base_color.red()}, {self.base_color.green()}, {self.base_color.blue()});
                border: {border};
                border-radius: 2px;
                padding: 0px;
            }}
            {hover}
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = True
            # Start a timer to detect long press (300ms)
            self.long_press_timer = QTimer()
            self.long_press_timer.setSingleShot(True)
            self.long_press_timer.timeout.connect(self.showColorShades)
            self.long_press_timer.start(300)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = False
            # If released before the long press timer, treat as a normal click
            if self.long_press_timer and self.long_press_timer.isActive():
                self.long_press_timer.stop()
                self.colorSelected.emit(self.base_color)
            
            # If shade popup is visible, it will handle its own selection on release
            # No need to do anything here
        super().mouseReleaseEvent(event)
    
    def showColorShades(self):
        """Show the color shade popup"""
        if not self.pressed:
            return  # Don't show if mouse is no longer pressed
            
        # Create the popup widget
        self.shade_popup = ColorShadePopup(self.base_color, self)
        self.shade_popup.colorSelected.connect(self.onShadeSelected)
        
        # Position the popup below the button
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.shade_popup.move(pos)
        self.shade_popup.show()
    
    def onShadeSelected(self, color):
        """Handle color selection from the popup"""
        self.colorSelected.emit(color)
        self.shade_popup = None


class ColorShadePopup(QWidget):
    """Custom popup widget for displaying and selecting color shades"""
    colorSelected = pyqtSignal(QColor)
    
    def __init__(self, color, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.base_color = color
        self.hoveredIndex = -1
        self.shades = self.generateShades(color)
        self.setMouseTracking(True)  # Enable mouse tracking
        self.setMinimumWidth(30)
        self.setMinimumHeight(len(self.shades) * 22)
        self.setStyleSheet("""
            background-color: #2d2d2d;
            border: 1px solid #505050;
        """)
        
    def generateShades(self, base_color, num_shades=5):
        """Generate various shades and tints of the base color"""
        shades = []
        
        # Get HSL values to manipulate
        hue = base_color.hue()
        saturation = base_color.saturation()
        lightness = base_color.lightness()
        
        # Create darker shades (lower lightness)
        for i in range(1, num_shades):
            new_lightness = max(0, lightness - (i * 25))
            color = QColor()
            color.setHsl(hue, saturation, new_lightness)
            shades.append(color)
        
        # Add original color
        shades.append(base_color)
        
        # Create lighter tints (higher lightness)
        for i in range(1, num_shades):
            new_lightness = min(255, lightness + (i * 25))
            color = QColor()
            color.setHsl(hue, saturation, new_lightness)
            shades.append(color)
        
        return shades
    
    def paintEvent(self, event):
        """Draw the color shade swatches"""
        painter = QPainter(self)
        width = self.width()
        
        # Draw each color swatch
        for i, shade in enumerate(self.shades):
            rect = QRect(2, i * 22 + 2, width - 4, 20)
            
            # Set border based on hover state
            if i == self.hoveredIndex:
                painter.setPen(QPen(QColor(224, 224, 224), 2))
            else:
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                
            # Fill with color
            painter.setBrush(QBrush(shade))
            painter.drawRect(rect)
            
    def mouseMoveEvent(self, event):
        """Track mouse movement to highlight the color being hovered"""
        y = event.pos().y()
        index = int(y / 22)
        
        # Ensure index is in bounds
        if 0 <= index < len(self.shades):
            if index != self.hoveredIndex:
                self.hoveredIndex = index
                self.update()  # Repaint to show highlight
        else:
            if self.hoveredIndex != -1:
                self.hoveredIndex = -1
                self.update()
    
    def mouseReleaseEvent(self, event):
        """Select the color on mouse release"""
        if event.button() == Qt.LeftButton:
            y = event.pos().y()
            index = int(y / 22)
            
            # Ensure index is in bounds
            if 0 <= index < len(self.shades):
                self.colorSelected.emit(self.shades[index])
            
            self.close()


def exception_hook(exctype, value, traceback):
    import traceback as tb
    print(f"Exception: {exctype.__name__}, {value}")
    print("Traceback:")
    for line in tb.format_tb(traceback):
        print(line)
    sys.__excepthook__(exctype, value, traceback)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set up exception hook to print detailed exceptions
    sys.excepthook = exception_hook
    
    try:
        from PyQt5.QtCore import QTimer  # Import QTimer here
        
        designer = DiagramDesigner()
        designer.show()
        
        # Force an update after the window is shown
        QTimer.singleShot(1000, designer.update_d2_code)
        
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        print(f"Application error: {e}")
        traceback.print_exc()
        
