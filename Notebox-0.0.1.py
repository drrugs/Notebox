import sys
import os
import json
import subprocess
import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
    QGraphicsItem, QGraphicsTextItem, QVBoxLayout, QHBoxLayout, 
    QPushButton, QWidget, QFrame, QLabel, QShortcut, QUndoCommand, 
    QUndoStack, QFileDialog, QMessageBox, QGraphicsRectItem, QMenu,
    QAction, QComboBox
)
from PyQt5.QtCore import Qt, QRectF, QTimer, QPoint, QPointF, QEvent, QLineF, QSizeF, QSize
from PyQt5.QtGui import (
    QBrush, QPen, QColor, QFont, QTextCursor, QKeySequence, 
    QPainter, QImage, QPixmap, QTextDocument, QIcon, QCursor
)
from PyQt5.QtSvg import QSvgGenerator
from PyQt5.QtPrintSupport import QPrinter

class DiagramView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.NoDrag)
        
        # Pan settings
        self.setInteractive(True)
        self.panning = False
        self.last_pan_point = None
        
        # Zoom settings
        self.zoom_factor_base = 1.15  # How fast we zoom
        self.min_zoom = 0.1  # Minimum zoom factor (10%)
        self.max_zoom = 3.0  # Maximum zoom factor (300%)
        self.current_zoom = 1.0
        
        # Set the cursor to an open hand when not panning
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Set scene rect to something very large to allow panning beyond content
        self.setSceneRect(-10000, -10000, 20000, 20000)
        
    def mousePressEvent(self, event):
        # If middle mouse button is pressed, start panning
        if event.button() == Qt.MiddleButton:
            self.panning = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)  # Use the cursor enum directly
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        # If panning is active, move the view
        if self.panning and self.last_pan_point:
            delta = event.pos() - self.last_pan_point
            self.last_pan_point = event.pos()
            
            # Move the scene in the direction of mouse movement
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            
            event.accept()
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        # Stop panning when middle mouse button is released
        if event.button() == Qt.MiddleButton:
            self.panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event):
        # Handle zoom with mouse wheel
        zoom_in = event.angleDelta().y() > 0
        
        # Calculate zoom factor
        if zoom_in:
            zoom_factor = self.zoom_factor_base
        else:
            zoom_factor = 1 / self.zoom_factor_base
            
        # Calculate new zoom level
        new_zoom = self.current_zoom * zoom_factor
        
        # Check if we're within zoom limits
        if new_zoom < self.min_zoom:
            zoom_factor = self.min_zoom / self.current_zoom
            new_zoom = self.min_zoom
        elif new_zoom > self.max_zoom:
            zoom_factor = self.max_zoom / self.current_zoom
            new_zoom = self.max_zoom
            
        # Update current zoom
        self.current_zoom = new_zoom
        
        # Set the transformation anchor to the position of the mouse
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Scale the view
        self.scale(zoom_factor, zoom_factor)
        
        # Show current zoom level in window title (optional)
        if hasattr(self, 'parent') and self.parent() and isinstance(self.parent(), MainWindow):
            title = f"Sticky Notes - Zoom: {int(self.current_zoom * 100)}%"
            self.parent().setWindowTitle(title)
            
        event.accept()
        
    def reset_view(self):
        """Fit all notes in view at once"""
        # Find the bounding rectangle of all notes
        items_rect = self.scene().itemsBoundingRect()
        
        # Only proceed if we have items
        if not items_rect.isEmpty():
            # Add some padding (10% on each side)
            padding_x = items_rect.width() * 0.1
            padding_y = items_rect.height() * 0.1
            items_rect.adjust(-padding_x, -padding_y, padding_x, padding_y)
            
            # Fit the view to this rectangle
            self.fitInView(items_rect, Qt.KeepAspectRatio)
            
            # Store the current zoom level based on the fit
            viewport_rect = self.viewport().rect()
            zoom_x = viewport_rect.width() / items_rect.width()
            zoom_y = viewport_rect.height() / items_rect.height()
            self.current_zoom = min(zoom_x, zoom_y)
        else:
            # If no items, just reset to default
            self.resetTransform()
            self.current_zoom = 1.0
            self.centerOn(0, 0)
        
        # Update window title
        if hasattr(self, 'parent') and self.parent() and isinstance(self.parent(), MainWindow):
            self.parent().setWindowTitle("Sticky Notes")

class AddNoteCommand(QUndoCommand):
    def __init__(self, scene, note):
        super().__init__()
        self.scene = scene
        self.note = note

    def undo(self):
        self.scene.removeItem(self.note)

    def redo(self):
        # Set highest Z value to ensure it's on top
        highest_z = max((item.zValue() for item in self.scene.items()), default=0)
        self.note.setZValue(highest_z + 1)
        self.scene.addItem(self.note)

class DuplicateNoteCommand(QUndoCommand):
    def __init__(self, scene, original_note, new_note):
        super().__init__()
        self.scene = scene
        self.original_note = original_note
        self.new_note = new_note
        
    def undo(self):
        self.scene.removeItem(self.new_note)
        
    def redo(self):
        # Set highest Z value to ensure it's on top
        highest_z = max((item.zValue() for item in self.scene.items()), default=0)
        self.new_note.setZValue(highest_z + 1)
        self.scene.addItem(self.new_note)

class DeleteNoteCommand(QUndoCommand):
    def __init__(self, scene, note, parent_note=None):
        super().__init__()
        self.scene = scene
        self.note = note
        self.parent_note = parent_note
        self.child_notes = []
        self.child_positions = []
        self.old_scene_pos = note.scenePos()
        
        # Store info about any child notes that will also be deleted
        if self.scene:
            for item in self.scene.items():
                if isinstance(item, StickyNote) and item.contained_by == self.note:
                    self.child_notes.append(item)
                    self.child_positions.append(item.pos())
        
    def undo(self):
        try:
            # Re-add the main note
            if self.note not in self.scene.items():
                self.scene.addItem(self.note)
                
                # Restore original position
                if not self.parent_note:
                    self.note.setPos(self.old_scene_pos)
                    
                # Re-add any child notes
                for i, child in enumerate(self.child_notes):
                    if child not in self.scene.items():
                        self.scene.addItem(child)
                        child.contained_by = self.note
                        child.setParentItem(self.note)
                        if i < len(self.child_positions):
                            child.setPos(self.child_positions[i])
                
                # If this note was in a container, re-establish that relationship
                if self.parent_note and self.parent_note in self.scene.items():
                    self.note.contained_by = self.parent_note
                    self.note.setParentItem(self.parent_note)
                    if not hasattr(self.parent_note, '_resizing'):
                        self.parent_note.check_and_resize()
                
                # Update colors for the restored hierarchy
                self.note.update_color_for_nesting()
                for child in self.child_notes:
                    if child in self.scene.items():
                        child.update_color_for_nesting()
                        
                print(f"Undo: Restored note {id(self.note)} and its {len(self.child_notes)} children")
        except Exception as e:
            print(f"Error during undo of DeleteNoteCommand: {str(e)}")
        
    def redo(self):
        try:
            # Remove the note and all its children from the scene
            if self.note in self.scene.items():
                # First save the parent for resize
                parent = self.note.contained_by
                
                # Remove children first
                for child in self.child_notes:
                    if child in self.scene.items():
                        self.scene.removeItem(child)
                
                # Remove the main note
                self.scene.removeItem(self.note)
                
                # Resize parent if needed
                if parent and parent in self.scene.items():
                    if not hasattr(parent, '_resizing'):
                        parent.check_and_resize()
                        
                print(f"Redo: Deleted note {id(self.note)} and its {len(self.child_notes)} children")
        except Exception as e:
            print(f"Error during redo of DeleteNoteCommand: {str(e)}")

class StickyNote(QGraphicsItem):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptDrops(True)
        self.FIXED_WIDTH = 200  # New constant for fixed width
        self.rect = QRectF(0, 0, self.FIXED_WIDTH, height)
        self.setPos(x, y)
        self.base_color = QColor(50, 50, 70)  # Dark blue-gray base color
        self.color = QColor(50, 50, 70)  # Initial color
        self.is_container = False
        self.contained_by = None
        self.is_selected = False
        self.arrangement_mode = 'free'  # Can be 'free', 'rows', or 'columns'
        self.drag_target_index = -1  # For insertion preview
        self.is_being_dragged = False
        self.min_padding = 15  # Minimum padding between notes in pixels
        
        # Set initial Z value
        self.setZValue(1)
        
        # For handling appearance during dragging
        self.setOpacity(1.0)

        # Title text item
        self.title_item = QGraphicsTextItem(self)
        self.title_item.setTextInteractionFlags(Qt.NoTextInteraction)  # Disable text interaction by default
        self.title_item.setPos(5, 5)
        self.title_item.setFont(QFont("Arial", 12, QFont.Bold))
        self.title_item.setDefaultTextColor(Qt.white)  # White text for title
        self.title_item.setTextWidth(self.FIXED_WIDTH - 10)
        self.title_item.document().contentsChanged.connect(self.adjust_size)

        # Description text item
        self.desc_item = QGraphicsTextItem(self)
        self.desc_item.setTextInteractionFlags(Qt.NoTextInteraction)  # Disable text interaction by default
        self.desc_item.setPos(5, 30)
        self.desc_item.setFont(QFont("Arial", 11))
        self.desc_item.setDefaultTextColor(Qt.white)  # White text for description
        self.desc_item.setTextWidth(self.FIXED_WIDTH - 10)
        self.desc_item.document().contentsChanged.connect(self.adjust_size)

        # Add connection for bullet point formatting
        self.desc_item.document().contentsChanged.connect(self.handle_bullet_points)

    def boundingRect(self):
        return self.rect

    def mousePressEvent(self, event):
        # Set dragging flag regardless of where on the note the mouse is pressed
        self.is_being_dragged = True
        self.drag_target_index = -1
        
        # Make note semi-transparent while dragging
        self.setOpacity(0.4)

        # Clear selection of all other notes
        if self.scene():
            for item in self.scene().items():
                if isinstance(item, StickyNote):
                    item.is_selected = False
                    item.update()

        # Select this note
        self.is_selected = True
        self.update()

        # Update the arrangement controls in main window
        if self.scene() and hasattr(self.scene().views()[0], 'parent'):
            main_window = self.scene().views()[0].parent()
            if isinstance(main_window, MainWindow):
                # Explicitly pass this note to update controls
                print(f"Setting selected note to {id(self)}")
                main_window.update_arrangement_controls(self)

        if event.button() == Qt.LeftButton:
            # Find the highest Z value in the scene and set this note to one higher
            highest_z = 1
            if self.scene():
                for item in self.scene().items():
                    if isinstance(item, StickyNote) and item != self:
                        highest_z = max(highest_z, item.zValue())
            
            # Bring to front by setting Z value higher than all other notes
            self.setZValue(highest_z + 1)
            self.setCursor(Qt.ClosedHandCursor)  # Use the cursor enum directly
        
        # Call the parent class method to ensure proper event handling
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Only handle text editing on double-click
        if self.title_item.boundingRect().contains(event.pos() - self.title_item.pos()):
            # Enable text editing for title
            self.title_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.title_item.setFocus()
            self.is_being_dragged = False
        elif self.desc_item.boundingRect().contains(event.pos() - self.desc_item.pos()):
            # Enable text editing for description
            self.desc_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.desc_item.setFocus()
            self.is_being_dragged = False
        super().mouseDoubleClickEvent(event)

    def find_non_overlapping_position(self, pos, container):
        """Find the nearest non-overlapping position for a note in a grid pattern"""
        padding = 20
        min_y = (container.title_item.boundingRect().height() +
                 container.desc_item.boundingRect().height() + padding)

        # Get our dimensions
        our_width = self.boundingRect().width()
        our_height = self.boundingRect().height()

        # Find all existing children and their positions
        siblings = []
        for item in container.scene().items():
            if (isinstance(item, StickyNote) and
                item.contained_by == container and
                item != self):
                siblings.append(item)

        # If no siblings, place at the start position
        if not siblings:
            return QPointF(padding, min_y)

        # Calculate container width and available columns
        container_width = container.boundingRect().width()
        max_columns = max(1, int((container_width - padding) / (our_width + padding)))
        
        # Attempt to find the first non-overlapping position
        # First try a simple grid layout
        grid_positions = []
        for row in range(10):  # Limit to a reasonable number of rows
            for col in range(max_columns):
                x = padding + col * (our_width + padding)
                y = min_y + row * (our_height + padding)
                
                # Ensure we don't exceed container width
                if x + our_width > container_width - padding:
                    continue
                    
                # Create a position
                grid_positions.append((x, y))
        
        # Check each grid position for overlap
        for x, y in grid_positions:
            # Check if this position overlaps with any sibling
            position_clear = True
            test_rect = QRectF(x, y, our_width, our_height)
            
            for sibling in siblings:
                sibling_rect = QRectF(sibling.pos().x(), sibling.pos().y(), 
                                     sibling.boundingRect().width(), 
                                     sibling.boundingRect().height())
                
                # Add a small buffer to prevent notes from being too close
                buffer = 5
                sibling_rect.adjust(-buffer, -buffer, buffer, buffer)
                
                if test_rect.intersects(sibling_rect):
                    position_clear = False
                    break
            
            if position_clear:
                return QPointF(x, y)
                
        # If we couldn't find a clear position in the grid, place at the end
        # Find the lowest sibling
        max_bottom = min_y
        for sibling in siblings:
            sibling_bottom = sibling.pos().y() + sibling.boundingRect().height()
            max_bottom = max(max_bottom, sibling_bottom)
            
        # Place below the lowest sibling
        return QPointF(padding, max_bottom + padding)

    def mouseMoveEvent(self, event):
        # Handle the move using parent class first
        super().mouseMoveEvent(event)

        # If we're in a container, handle movement based on arrangement mode
        if self.contained_by and self.is_being_dragged:
            # Calculate position among siblings for insertion preview
            self.update_drag_target()

            if hasattr(self.contained_by, 'arrangement_mode') and self.contained_by.arrangement_mode == 'free':
                # Free movement mode - handle dragging within parent or disconnecting if dragged too far
                pos = self.pos()
                padding = 20
                margin = -30  # Negative margin allows dragging slightly outside before disconnecting
                
                # Calculate boundaries with margin
                min_x = margin
                min_y = (self.contained_by.title_item.boundingRect().height() +
                         self.contained_by.desc_item.boundingRect().height() + padding)
                max_x = self.contained_by.boundingRect().width() - self.boundingRect().width() - margin
                max_y = self.contained_by.boundingRect().height() - self.boundingRect().height() - margin
                
                # Check if dragged way outside parent boundaries
                disconnect_margin = -100  # Larger negative value = need to drag further to disconnect
                if (pos.x() < disconnect_margin or 
                    pos.y() < min_y - 50 or  # Allow more room at top (text area)
                    pos.x() > max_x - disconnect_margin or 
                    pos.y() > max_y - disconnect_margin):
                    
                    # Disconnect from container
                    scene_pos = self.scenePos()
                    
                    # Store old container for later reference
                    old_container = self.contained_by
                    
                    # Block signals to prevent recursive calls
                    self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
                    
                    # Disconnect
                    self.contained_by = None
                    self.setParentItem(None)
                    self.setPos(scene_pos)
                    
                    # Re-enable signals
                    self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
                    
                    # Update old container
                    if old_container and old_container.scene() and not hasattr(old_container, '_resizing'):
                        old_container.check_and_resize()
                    
                    # Update color for top-level note
                    self.update_color_for_nesting()
                    
                    # Show highlights for potential new containers
                    items = self.scene().items(scene_pos)
                    for item in items:
                        if isinstance(item, StickyNote) and item != self:
                            item.color = QColor(200, 200, 255)
                            item.update()
                            break
                else:
                    # Stay within parent with soft constraints
                    # Allow movement but softly constrain to prevent going too far out
                    soft_min_x = min_x * 2 if min_x < 0 else min_x / 2
                    soft_min_y = min_y * 0.9
                    soft_max_x = max_x * 1.1
                    soft_max_y = max_y * 1.1
                    
                    # Apply soft constraints - allows some overflow but prevents going too far
                    new_x = max(soft_min_x, min(pos.x(), soft_max_x))
                    new_y = max(soft_min_y, min(pos.y(), soft_max_y))
                    
                    # Only update if needed
                    if new_x != pos.x() or new_y != pos.y():
                        self.setPos(new_x, new_y)
                    
                    # Update container size
                    if not hasattr(self.contained_by, '_resizing'):
                        self.contained_by.check_and_resize()
            else:
                # Grid/rows mode - snap to non-overlapping position
                new_pos = self.find_non_overlapping_position(self.pos(), self.contained_by)
                self.setPos(new_pos)
                
                # Update container size
                if not hasattr(self.contained_by, '_resizing'):
                    self.contained_by.check_and_resize()
        elif self.is_being_dragged:
            # Logic for top-level notes (not in a container)
            pos = self.mapToScene(event.pos())
            items = self.scene().items(pos)

            # First reset all notes to their base color
            for item in self.scene().items():
                if isinstance(item, StickyNote) and item != self:
                    item.color = item.base_color  # Reset to base color
                    item.update()

            # Highlight potential container under cursor - only if it's a valid target
            potential_container = None
            for item in items:
                if isinstance(item, StickyNote) and item != self:
                    # Check if this note is not contained by the current note (prevents circular containment)
                    current = item
                    is_descendant = False
                    while current:
                        if current.contained_by == self:
                            is_descendant = True
                            break
                        current = current.contained_by
                    
                    if not is_descendant:
                        potential_container = item
                        break
            
            # Highlight the potential container if found
            if potential_container:
                potential_container.color = QColor(80, 100, 140)  # Bright blue for dark theme
                potential_container.update()

    def mouseReleaseEvent(self, event):
        # Keep the current Z-value (don't reset it) to maintain stacking order
        self.setCursor(Qt.ArrowCursor)
        
        # Reset opacity to fully opaque
        self.setOpacity(1.0)
        
        # Cache dragging flags before resetting
        was_dragging = self.is_being_dragged
        drag_target = self.drag_target_index
        
        # Reset dragging flags
        self.is_being_dragged = False
        self.drag_target_index = -1
        
        # Force update to remove insertion preview
        if self.contained_by:
            self.contained_by.update()
            
        # Handle rearrangement if we have a valid insertion target
        if was_dragging and self.contained_by and drag_target >= 0:
            self.rearrange_at_position(drag_target)

        # First, find if any note was highlighted during dragging
        highlighted_container = None
        for item in self.scene().items():
            if isinstance(item, StickyNote) and item != self and item.color != item.base_color:
                # This note was highlighted
                highlighted_container = item
                break
                
        # Get items under cursor for container detection
        # Use cursor position instead of note position
        cursor_scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(cursor_scene_pos)

        # Reset highlight colors (blue highlighting during drag)
        for item in self.scene().items():
            if isinstance(item, StickyNote) and item != self:
                # Only reset color for items that might have been highlighted
                item.update_color_for_nesting()
                item.update()

        # Find potential container - prefer the highlighted container if available
        container = None
        
        # If we found a highlighted container during dragging, use it
        if highlighted_container:
            # Check if this note is not contained by the current note (prevents circular containment)
            current = highlighted_container
            is_descendant = False
            while current:
                if current.contained_by == self:
                    is_descendant = True
                    break
                current = current.contained_by
            
            if not is_descendant:
                container = highlighted_container
        
        # If no highlighted container was found, fall back to items under cursor
        if not container:
            for item in items:
                if isinstance(item, StickyNote) and item != self:
                    # Check if this note is not contained by the current note (prevents circular containment)
                    current = item
                    is_descendant = False
                    while current:
                        if current.contained_by == self:
                            is_descendant = True
                            break
                        current = current.contained_by
                    
                    if not is_descendant:
                        container = item
                        break

        # Save our current container for reference
        old_container = self.contained_by
        
        if container:
            # If we're moving to a new container
            if old_container != container:
                # Remove from old container if exists
                if old_container:
                    self.contained_by = None
                    self.setParentItem(None)
                    
                    # First rearrange children in the old container
                    if old_container.scene():
                        old_container.rearrange_children_with_spacing()

                # Add to new container
                self.contained_by = container
                container.is_container = True
                self.setParentItem(container)
                
                # Find non-overlapping position
                mapped_pos = container.mapFromScene(self.scenePos())
                new_pos = self.find_non_overlapping_position(mapped_pos, container)
                self.setPos(new_pos)
                
                # Update color based on nesting
                self.update_color_for_nesting()
                
                # Rearrange notes in the new container
                container.rearrange_children_with_spacing()
            else:
                # We're staying in the same container, still rearrange
                old_container.rearrange_children_with_spacing()
        else:
            # We're being dropped outside any container
            if old_container:
                print(f"Detaching note {id(self)} from container {id(old_container)}")
                # Remember scene position before removing parent
                scene_pos = self.scenePos()
                
                # Disconnect from container
                self.contained_by = None
                self.setParentItem(None)
                self.setPos(scene_pos)
                
                # Update color for top-level note
                self.update_color_for_nesting()
                
                # Ensure old container rearranges its remaining children
                if old_container.scene():
                    old_container.rearrange_children_with_spacing()
        
        # After handling containers, check if text interaction should be disabled
        # If the mouse was released outside text areas, clear focus and disable interaction
        pos = event.pos()
        if not (self.title_item.boundingRect().contains(pos - self.title_item.pos()) or 
                self.desc_item.boundingRect().contains(pos - self.desc_item.pos())):
            # Clear any text selection and disable text interaction
            self.title_item.clearFocus()
            self.desc_item.clearFocus() 
            self.clear_text_selection()
        
        super().mouseReleaseEvent(event)

    def rearrange_children_with_spacing(self):
        """Rearrange children to ensure proper spacing and prevent overlaps"""
        if not self.is_container or not self.scene():
            return
            
        # Get all children
        children = []
        for item in self.scene().items():
            if isinstance(item, StickyNote) and item.contained_by == self:
                children.append(item)
                
        if not children:
            # No children, reset container status
            self.is_container = False
            self.prepareGeometryChange()
            self.reset_to_normal_size()
            return
            
        # Block signals while rearranging
        for child in children:
            child.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
            
        try:
            # Get text area height
            padding = 20
            title_height = self.title_item.boundingRect().height()
            desc_height = self.desc_item.boundingRect().height()
            text_area_height = title_height + desc_height + padding
            
            # Sort children by existing positions (top to bottom, then left to right)
            children.sort(key=lambda x: (x.pos().y(), x.pos().x()))
            
            # Start positioning from the top of the container
            current_y = text_area_height + padding
            max_height = 0
            
            if len(children) == 1:
                # Special case for single child - just position it at the top
                children[0].setPos(padding, text_area_height + padding)
            else:
                # Auto-arrange based on container width
                container_width = self.rect.width() if self.rect.width() > 0 else self.FIXED_WIDTH
                child_width = children[0].boundingRect().width()
                horizontal_spacing = padding
                
                # Calculate max notes per row (at least 1)
                max_notes_per_row = max(1, int((container_width - padding) / (child_width + horizontal_spacing)))
                
                # Arrange children in rows
                current_x = padding
                notes_in_current_row = 0
                
                for child in children:
                    # Start a new row if needed
                    if notes_in_current_row >= max_notes_per_row:
                        current_y += max_height + padding
                        current_x = padding
                        notes_in_current_row = 0
                        max_height = 0
                    
                    # Position this child
                    child.setPos(current_x, current_y)
                    
                    # Update trackers
                    current_x += child_width + horizontal_spacing
                    max_height = max(max_height, child.boundingRect().height())
                    notes_in_current_row += 1
            
            # After rearranging children, ensure container is properly sized
            self.check_and_resize()
        finally:
            # Restore signals
            for child in children:
                child.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # Force update
        self.update()

    def check_and_resize(self):
        """Check if we still have children and resize accordingly"""
        # Prevent recursive calls
        if hasattr(self, '_resizing'):
            return
        self._resizing = True

        try:
            # Find all children
            children = []
            for item in self.scene().items():
                if isinstance(item, StickyNote) and item.contained_by == self:
                    children.append(item)

            if not children:
                # No children, completely reset container state
                self.is_container = False
                self.prepareGeometryChange()
                self.reset_to_normal_size()
                return

            # Calculate height needed for text content
            padding = 20
            title_height = self.title_item.boundingRect().height()
            desc_height = self.desc_item.boundingRect().height()
            text_area_height = title_height + desc_height + padding
            min_height = text_area_height + padding  # Ensure space for text

            # Find the maximum extents needed for children
            max_right = padding  # Start with padding
            max_bottom = text_area_height + padding  # Start below text area

            # Examine each child's position
            for child in children:
                child_pos = child.pos()
                child_rect = child.boundingRect()
                child_right = child_pos.x() + child_rect.width() + padding
                child_bottom = child_pos.y() + child_rect.height() + padding

                # Update maximums
                max_right = max(max_right, child_right)
                max_bottom = max(max_bottom, child_bottom)

            # Final dimensions with padding
            final_width = max(self.FIXED_WIDTH, max_right)
            final_height = max(min_height, max_bottom)

            # Update geometry
            self.prepareGeometryChange()
            self.rect = QRectF(0, 0, final_width, final_height)

            # Update text widths
            self.title_item.document().blockSignals(True)
            self.desc_item.document().blockSignals(True)
            
            text_width = min(final_width - padding * 2, self.FIXED_WIDTH - padding)
            self.title_item.setTextWidth(text_width)
            self.desc_item.setTextWidth(text_width)
            self.desc_item.setPos(5, title_height + 5)
            
            self.title_item.document().blockSignals(False)
            self.desc_item.document().blockSignals(False)
        finally:
            delattr(self, '_resizing')
            self.update()

    def adjust_size(self):
        """Adjust size based on content and children"""
        # Prevent recursive calls
        if hasattr(self, '_adjusting'):
            return
        self._adjusting = True

        try:
            padding = 20
            title_height = self.title_item.boundingRect().height()
            desc_height = self.desc_item.boundingRect().height()
            text_area_height = title_height + desc_height + padding

            # Update description position
            self.desc_item.setPos(5, title_height + 5)

            # If we're a container, handle children
            if self.is_container:
                # First move any overlapping children
                self.move_overlapping_children(text_area_height)
                # Then resize to fit
                if not hasattr(self, '_resizing'):
                    self.check_and_resize()
            else:
                # For non-containers, just handle text wrapping
                self.reset_to_normal_size()

            # If we're in a container, make sure it updates too
            if (self.contained_by and
                not hasattr(self.contained_by, '_adjusting') and
                not hasattr(self.contained_by, '_resizing')):
                self.contained_by.check_and_resize()

        finally:
            delattr(self, '_adjusting')

    def move_overlapping_children(self, text_area_height):
        """Move any children that overlap with the text area"""
        padding = 20
        for item in self.scene().items():
            if isinstance(item, StickyNote) and item.contained_by == self:
                child_pos = item.pos()
                if child_pos.y() < text_area_height:
                    # Block signals temporarily to prevent recursive calls
                    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
                    item.setPos(child_pos.x(), text_area_height + padding)
                    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def paint(self, painter, option, widget):
        # Draw shadow first
        shadow_rect = self.rect.translated(3, 3)
        shadow_color = QColor(0, 0, 0, 50)  # Darker shadow for better contrast
        painter.setBrush(QBrush(shadow_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(shadow_rect)

        # Draw main note
        painter.setBrush(QBrush(self.color))
        # Use a slightly brighter border for dark notes
        painter.setPen(QPen(QColor(100, 100, 120), 1.5))
        painter.drawRect(self.rect)

        # Draw title underline
        title_height = self.title_item.boundingRect().height()
        underline_y = title_height + 5  # Position just below the title
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))  # Faint white line (80 alpha)
        start_point = QPointF(5, underline_y)
        end_point = QPointF(self.rect.width() - 5, underline_y)
        painter.drawLine(start_point, end_point)

        # Draw selection highlight
        if self.is_selected:
            # Brighter highlight for dark theme
            painter.setPen(QPen(QColor(120, 180, 255), 2))
            painter.setBrush(Qt.NoBrush)
            highlight_rect = self.rect.adjusted(1, 1, -1, -1)
            painter.drawRect(highlight_rect)

        # Draw insertion preview line if we're a container and have a child being dragged
        if self.is_container and self.scene():
            dragged_child = None
            siblings = []
            
            # Find dragged child and all siblings
            for item in self.scene().items():
                if isinstance(item, StickyNote) and item.contained_by == self:
                    if item.is_being_dragged and item.drag_target_index >= 0:
                        dragged_child = item
                    else:
                        siblings.append(item)
            
            # If we have a dragged child with valid target index, draw insertion line
            if dragged_child and dragged_child.drag_target_index >= 0:
                # Sort siblings by vertical position
                siblings.sort(key=lambda x: x.pos().y())
                
                # Calculate insertion line position
                padding = 20
                min_y = (self.title_item.boundingRect().height() +
                         self.desc_item.boundingRect().height() + padding)
                        
                line_y = 0
                target_idx = dragged_child.drag_target_index
                
                if len(siblings) == 0:
                    # Only child - line at top
                    line_y = min_y + padding / 2
                elif target_idx >= len(siblings):
                    # Insert at end - line below last sibling
                    last = siblings[-1]
                    line_y = last.pos().y() + last.boundingRect().height() + padding / 2
                elif target_idx == 0:
                    # Insert at beginning - line above first sibling
                    first = siblings[0]
                    line_y = first.pos().y() - padding / 2
                else:
                    # Insert between siblings - line between them
                    above = siblings[target_idx - 1]
                    below = siblings[target_idx]
                    above_bottom = above.pos().y() + above.boundingRect().height()
                    line_y = (above_bottom + below.pos().y()) / 2
                
                # Draw the insertion line
                if line_y > 0:
                    # Changed: Make the line more visible but shorter
                    # Use a bright cyan color with a thicker line
                    painter.setPen(QPen(QColor(0, 255, 255), 4, Qt.DashLine))
                    
                    # Make the line shorter - only 60% of the width of the note, centered
                    center_x = self.rect.width() / 2
                    line_width = self.rect.width() * 0.6
                    start_x = center_x - line_width / 2
                    end_x = center_x + line_width / 2
                    
                    # Draw the line
                    start_point = QPointF(start_x, line_y)
                    end_point = QPointF(end_x, line_y)
                    painter.drawLine(start_point, end_point)

    def itemChange(self, change, value):
        if (change == QGraphicsItem.ItemPositionChange and
            self.scene() and
            self.contained_by and
            not hasattr(self.contained_by, '_adjusting') and
            not hasattr(self.contained_by, '_resizing')):
            self.contained_by.check_and_resize()
        return super().itemChange(change, value)

    def reset_to_normal_size(self):
        """Completely reset note to its normal non-container size"""
        padding = 20
        self.is_container = False

        # Calculate height based on text
        title_height = self.title_item.boundingRect().height()
        desc_height = self.desc_item.boundingRect().height()
        height = title_height + desc_height + padding * 2

        # Force complete recreation of rectangle with fixed width
        self.prepareGeometryChange()
        self.rect = QRectF(0, 0, self.FIXED_WIDTH, height)

        # Update text items
        self.title_item.setTextWidth(self.FIXED_WIDTH - padding * 2)
        self.desc_item.setTextWidth(self.FIXED_WIDTH - padding * 2)
        self.desc_item.setPos(5, title_height + 5)

        self.update()

    def handle_bullet_points(self):
        """Handle automatic bullet point formatting in description"""
        if hasattr(self, '_formatting_bullets'):  # Prevent recursive calls
            return

        self._formatting_bullets = True
        try:
            cursor = self.desc_item.textCursor()
            current_block = cursor.block()
            block_text = current_block.text()

            # Check if we just typed "- " at start of line
            if block_text == "- ":
                # Format as bullet point
                cursor.movePosition(cursor.StartOfBlock)
                cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
                cursor.insertText("• ")

            # Check if Enter was pressed after a bullet point
            elif block_text == "" and current_block.previous().isValid():
                prev_text = current_block.previous().text()
                if prev_text.startswith("• "):
                    cursor.insertText("• ")

        finally:
            delattr(self, '_formatting_bullets')

    def arrange_children(self, mode='columns'):
        """Arrange children in the specified mode"""
        if not self.is_container or not self.scene():
            print(f"Cannot arrange: is_container={self.is_container}, has_scene={self.scene() is not None}")
            return
            
        print(f"Arranging note {id(self)} children in '{mode}' mode")
        self.arrangement_mode = mode
        
        # Get all children
        children = []
        for item in self.scene().items():
            if isinstance(item, StickyNote) and item.contained_by == self:
                children.append(item)
        
        if not children:
            print(f"Note {id(self)} has no children to arrange")
            return
            
        print(f"Arranging {len(children)} children")
        # Set a base padding
        padding = 20
        
        # Get text area height
        title_height = self.title_item.boundingRect().height()
        desc_height = self.desc_item.boundingRect().height()
        text_area_height = title_height + desc_height + padding
        
        # Disable ALL child signals temporarily
        for child in children:
            child.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
            # Set movable flag based on mode
            child.setFlag(QGraphicsItem.ItemIsMovable, mode == 'free')
            
        # Defer resize until after arrangement
        old_resizing = hasattr(self, '_resizing')
        if not old_resizing:
            self._resizing = True
            
        try:
            if mode == 'rows':
                print("Applying rows arrangement")
                # Simple row arrangement (stacked)
                y_pos = text_area_height + padding
                for child in children:
                    child.setPos(padding, y_pos)
                    y_pos += child.boundingRect().height() + padding
                
                # Calculate new container size for rows
                new_width = max(self.FIXED_WIDTH, children[0].boundingRect().width() + padding * 2)
                new_height = y_pos
                
                # Apply the new size
                self.prepareGeometryChange()
                self.rect = QRectF(0, 0, new_width, new_height)
                print(f"Container resized to {new_width} x {new_height} for rows")
            
            elif mode == 'columns':
                print("Applying columns arrangement")
                # For columns, we need to ensure there's enough width
                note_width = self.FIXED_WIDTH  # Fixed width for notes
                
                # Decide how many columns to use based on number of children
                num_children = len(children)
                desired_columns = min(max(1, num_children), 3)  # Between 1 and 3 columns
                
                # Calculate needed width for the desired number of columns
                needed_width = padding + (note_width + padding) * desired_columns
                
                print(f"Arranging {num_children} children in {desired_columns} columns")
                print(f"Each note width: {note_width}, padding: {padding}")
                print(f"Setting container width to {needed_width}")
                
                # Resize container FIRST to have enough width
                self.prepareGeometryChange()
                self.rect = QRectF(0, 0, needed_width, self.rect.height())
                
                # Sort children to ensure predictable ordering
                children.sort(key=lambda x: (x.pos().y(), x.pos().x()))
                
                # Position each child
                max_bottom = text_area_height + padding
                for i, child in enumerate(children):
                    # Calculate position in grid
                    col = i % desired_columns
                    row = i // desired_columns
                    
                    # Calculate exact coordinates
                    x = padding + col * (note_width + padding)
                    y = text_area_height + padding + row * (child.boundingRect().height() + padding)
                    
                    # Position child
                    print(f"Child {i}: col={col}, row={row}, position=({x}, {y})")
                    child.setPos(x, y)
                    
                    # Track bottom for container height
                    child_bottom = y + child.boundingRect().height()
                    max_bottom = max(max_bottom, child_bottom)
                
                # Now update container height
                self.prepareGeometryChange()
                self.rect = QRectF(0, 0, needed_width, max_bottom + padding)
                print(f"Final container dimensions: {needed_width} x {max_bottom + padding}")
            
            # For free mode, just make sure children are movable and within bounds
            elif mode == 'free':
                print("Applying free arrangement")
                # Calculate container size to fit all children at their current positions
                max_right = self.FIXED_WIDTH
                max_bottom = text_area_height
                
                for child in children:
                    child_right = child.pos().x() + child.boundingRect().width() 
                    child_bottom = child.pos().y() + child.boundingRect().height()
                    max_right = max(max_right, child_right)
                    max_bottom = max(max_bottom, child_bottom)
                
                # Resize container to fit
                self.prepareGeometryChange()
                new_width = max_right + padding
                new_height = max_bottom + padding
                self.rect = QRectF(0, 0, new_width, new_height)
                print(f"Container resized to {new_width} x {new_height} for free arrangement")
            
        finally:
            # Restore signals
            for child in children:
                child.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
            
            # Clean up resizing flag if we set it
            if not old_resizing:
                delattr(self, '_resizing')
                
        # Force update
        self.update()
        if self.scene():
            self.scene().update()

    def update_drag_target(self):
        """Update the drag target index based on current position"""
        if not self.contained_by or not self.scene():
            self.drag_target_index = -1
            return
            
        # Get all siblings
        siblings = []
        for item in self.scene().items():
            if (isinstance(item, StickyNote) and 
                item.contained_by == self.contained_by and 
                item != self):
                siblings.append(item)
                
        if not siblings:
            self.drag_target_index = 0  # Only child
            self.contained_by.update()  # Force redraw to show insertion line
            return
            
        # Get my position
        my_pos = self.pos()
        my_center_y = my_pos.y() + self.boundingRect().height() / 2
        
        # Sort siblings by vertical position
        siblings.sort(key=lambda x: x.pos().y())
        
        # Find the insertion position
        for i, sibling in enumerate(siblings):
            sibling_pos = sibling.pos()
            sibling_center_y = sibling_pos.y() + sibling.boundingRect().height() / 2
            
            # If we're above this sibling's center, we're inserting here
            if my_center_y < sibling_center_y:
                self.drag_target_index = i
                self.contained_by.update()  # Force redraw to show insertion line
                return
                
        # If we're below all siblings, insert at the end
        self.drag_target_index = len(siblings)
        self.contained_by.update()  # Force redraw to show insertion line

    def rearrange_at_position(self, target_index):
        """Rearrange the notes to insert this note at the specified index"""
        if not self.contained_by or target_index < 0:
            return
            
        # Get all siblings excluding self
        siblings = []
        for item in self.scene().items():
            if (isinstance(item, StickyNote) and 
                item.contained_by == self.contained_by and 
                item != self):
                siblings.append(item)
                
        if not siblings:
            return  # No rearrangement needed
            
        # Sort siblings by vertical position
        siblings.sort(key=lambda x: x.pos().y())
        
        # Insert self at the target position
        all_notes = siblings.copy()
        all_notes.insert(target_index, self)
        
        # Block signals while rearranging
        for note in all_notes:
            note.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
            
        try:
            # Apply arrangement based on the current mode
            if self.contained_by.arrangement_mode == 'columns':
                # Use the container's arrange_children method
                self.contained_by.arrange_children('columns')
            elif self.contained_by.arrangement_mode == 'free':
                # In free mode, just adjust vertical positions preserving horizontal
                self.apply_free_arrangement(all_notes)
            else:  # rows mode
                # In rows mode, stack notes
                self.contained_by.arrange_children('rows')
                
        finally:
            # Restore signals
            for note in all_notes:
                note.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
            
        # Update the scene to show changes
        if self.scene():
            self.scene().update()
    
    def apply_free_arrangement(self, notes):
        """Arrange notes in free mode, preserving horizontal positions but adjusting vertical"""
        if not self.contained_by:
            return
            
        padding = 20
        # Get text area height from container
        min_y = (self.contained_by.title_item.boundingRect().height() +
                 self.contained_by.desc_item.boundingRect().height() + padding)
        
        # Sort notes by vertical position
        notes.sort(key=lambda x: x.pos().y())
        
        # Reposition vertically while maintaining horizontal positions
        current_y = min_y
        for note in notes:
            # Preserve x position
            current_x = note.pos().x()
            # Set new y position
            note.setPos(current_x, current_y)
            # Move down for next note
            current_y += note.boundingRect().height() + padding
        
        # Ensure container resizes
        self.contained_by.check_and_resize()

    def calculate_nesting_level(self):
        """Calculate how many levels deep this note is nested"""
        level = 0
        parent = self.contained_by
        while parent:
            level += 1
            parent = parent.contained_by
        return level
        
    def update_color_for_nesting(self):
        """Update the note's color based on its nesting level"""
        level = self.calculate_nesting_level()
        
        # Start with the base color for all notes
        base_color = QColor(50, 50, 70)  # Dark blue-gray base color
        
        if level == 0:
            # Top level note - use base color
            self.color = QColor(base_color)
        else:
            # Get HSV components of the base color
            h, s, v, a = base_color.getHsvF()
            
            # Increase brightness by 5% per level, but ensure it stays dark enough for white text
            # Cap at 70% brightness to maintain readability with white text
            brightness_increase = min(0.05 * level, 0.3)  # Cap at 30% total increase
            new_v = min(0.7, v + brightness_increase)  # Cap at 70% brightness
            
            # Create new color with adjusted brightness
            self.color = QColor()
            self.color.setHsvF(h, s, new_v, a)
        
        # Update the appearance
        self.update()
        
        # Also update children if this is a container
        if self.scene() and self.is_container:
            for item in self.scene().items():
                if isinstance(item, StickyNote) and item.contained_by == self:
                    item.update_color_for_nesting()

    def clear_text_selection(self):
        """Clear any text selection in title and description text items"""
        # Clear title text selection if exists
        title_cursor = self.title_item.textCursor()
        title_cursor.clearSelection()
        self.title_item.setTextCursor(title_cursor)
        
        # Disable text interaction if not focused
        if not self.title_item.hasFocus():
            self.title_item.setTextInteractionFlags(Qt.NoTextInteraction)
        
        # Clear description text selection if exists
        desc_cursor = self.desc_item.textCursor()
        desc_cursor.clearSelection()
        self.desc_item.setTextCursor(desc_cursor)
        
        # Disable text interaction if not focused
        if not self.desc_item.hasFocus():
            self.desc_item.setTextInteractionFlags(Qt.NoTextInteraction)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize the scene and view
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 10000, 10000)
        self.view = DiagramView(self.scene)
        
        # Set up undo stack
        self.undo_stack = QUndoStack(self)
        
        # Initialize variables for notes management
        self.notes_data = {}
        self.selected_note = None
        self.file_path = None
        self.last_save_state = None
        
        # Initialize UI
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Sticky Notes')
        self.setGeometry(100, 100, 1000, 800)

        # Create and set the window icon (simple box)
        self.create_window_icon()
        
        # Set dark title bar (Windows-specific)
        if sys.platform == 'win32':
            try:
                # Windows-specific dark title bar
                import ctypes
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                HWND = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    HWND, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                    ctypes.byref(ctypes.c_int(1)), 
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception as e:
                print(f"Error setting dark title bar: {str(e)}")

        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)

        # Create graphics scene and view
        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QColor(45, 45, 45))
        
        # Connect scene selectionChanged signal
        self.scene.selectionChanged.connect(self.scene_selection_changed)

        # Use our custom DiagramView instead of standard QGraphicsView
        self.view = DiagramView(self.scene)
        
        # Create keyboard shortcuts
        self.create_shortcuts()
        
        # Create main layout with toolbar at top and view below
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar widget with fixed height
        toolbar = QWidget()
        toolbar.setFixedHeight(45)  # Reduced from 60 to 45 (0.75x thickness)
        toolbar.setStyleSheet("background-color: #363636;")
        
        # Create horizontal layout for toolbar
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 3, 10, 3)  # Reduced vertical margins from 5 to 3
        
        # Add Note section
        add_button = QPushButton("+ New Note")
        add_button.clicked.connect(self.addNote)
        add_button.setFixedWidth(150)  # Increased from 120
        
        # Add delete button with red color
        delete_button = QPushButton("🗑️")
        delete_button.setObjectName("delete_button")  # For CSS styling
        delete_button.clicked.connect(self.delete_selected_note)
        delete_button.setFixedWidth(50)  # Increased from 40
        delete_button.setToolTip("Delete Selected Note (Delete)")
        
        # Add refresh button
        refresh_button = QPushButton("🔄")
        refresh_button.clicked.connect(self.refresh_all_notes)
        refresh_button.setFixedWidth(50)  # Increased from 40
        refresh_button.setToolTip("Refresh all notes (reorganize and recalculate sizes)")
        refresh_button.setStyleSheet("color: #4caf50;")  # Green color for the icon
        
        # Add reset view button
        reset_view_button = QPushButton("🔍")  # Changed from 🏠 to 🔍 for zoom/fit
        reset_view_button.clicked.connect(self.view.reset_view)
        reset_view_button.setFixedWidth(50)  # Increased from 40
        reset_view_button.setToolTip("Fit all notes in view")
        
        # Add export button
        export_button = QPushButton("💾")
        export_button.clicked.connect(self.export_canvas)
        export_button.setFixedWidth(50)  # Increased from 40
        export_button.setToolTip("Export diagram (Ctrl+E)")
        
        # Add buttons to toolbar
        toolbar_layout.addWidget(add_button)
        toolbar_layout.addWidget(delete_button)
        toolbar_layout.addWidget(refresh_button)
        toolbar_layout.addWidget(reset_view_button)
        toolbar_layout.addWidget(export_button)
        
        # Add separator
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #555555;")
        toolbar_layout.addWidget(separator)
        
        # Add spacer to push alignment buttons to the right
        toolbar_layout.addSpacing(20)
        
        # Create individual buttons for each alignment mode
        self.free_button = QPushButton("🖱️ Free")
        self.free_button.setToolTip("Free alignment: Notes can be dragged anywhere")
        self.free_button.setCheckable(True)
        self.free_button.setChecked(True)  # Default to free mode
        self.free_button.clicked.connect(lambda: self.set_arrangement_mode('free'))
        self.free_button.setFixedWidth(110)  # Increased from 90
        
        self.rows_button = QPushButton("→ Rows")
        self.rows_button.setToolTip("Stack notes in rows")
        self.rows_button.setCheckable(True)
        self.rows_button.clicked.connect(lambda: self.set_arrangement_mode('rows'))
        self.rows_button.setFixedWidth(110)  # Increased from 90
        
        self.columns_button = QPushButton("↓ Columns")
        self.columns_button.setToolTip("Arrange notes in columns")
        self.columns_button.setCheckable(True)
        self.columns_button.clicked.connect(lambda: self.set_arrangement_mode('columns'))
        self.columns_button.setFixedWidth(110)  # Increased from 90
        
        # Add alignment buttons to toolbar
        toolbar_layout.addWidget(self.free_button)
        toolbar_layout.addWidget(self.rows_button)
        toolbar_layout.addWidget(self.columns_button)
        
        # Add stretch to push everything to the left
        toolbar_layout.addStretch()
        
        # Add toolbar and view to main layout
        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.view, 1)  # Give view a stretch factor of 1
        
        # Create central widget and set layout
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Center the scene's view
        self.view.centerOn(0, 0)

        # Set dark mode style
        self.setStyleSheet("""
            QMainWindow, QGraphicsView { background-color: #2d2d2d; }
            QWidget { color: #ffffff; }
            QPushButton { 
                background-color: #4a4a4a; 
                color: #ffffff; 
                border: none; 
                padding: 6px;
                border-radius: 3px;
                margin: 2px;
                font-size: 16px; /* Increased font size for toolbar text */
                font-weight: 500;
            }
            /* Special style for emoji buttons with even larger font */
            QPushButton[text="🗑️"], QPushButton[text="🔄"], QPushButton[text="🔍"], QPushButton[text="💾"] {
                font-size: 20px; /* Larger font for emoji icons */
                padding: 3px;
                line-height: 1;
            }
            QPushButton:hover { background-color: #5a5a5a; }
            QPushButton:checked { 
                background-color: #7289da; 
                color: white;
                font-weight: bold;
                font-size: 16px; /* Keep same font size when checked */
            }
            QPushButton:disabled { 
                background-color: transparent; 
                color: #aaaaaa;
                font-weight: bold;
                font-size: 16px; /* Keep same font size when disabled */
            }
            QPushButton:flat { 
                background-color: transparent;
                border: none; 
            }
            #delete_button {
                background-color: #8a3a3a;
            }
            #delete_button:hover {
                background-color: #aa4a4a;
            }
            QScrollBar:vertical {
                background-color: #121212; /* Almost black background */
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #333333; /* Dark gray handle for contrast */
                min-height: 20px;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background-color: #121212; /* Match the scrollbar background */
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background-color: #121212; /* Make sure the paging area is also black */
            }
            QScrollBar:horizontal {
                background-color: #121212; /* Almost black background */
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #333333; /* Dark gray handle for contrast */
                min-width: 20px;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background-color: #121212; /* Match the scrollbar background */
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background-color: #121212; /* Make sure the paging area is also black */
            }
        """)
        
        # Initialize the arrangement buttons as disabled
        self.update_arrangement_controls(None)
        
        # Add status tips for navigation
        self.view.setStatusTip("Middle-click and drag to pan. Scroll wheel to zoom in/out.")

    def scene_selection_changed(self):
        """Handle scene selection changes"""
        print("Scene selection changed")
        
        # Find selected StickyNotes
        selected_notes = []
        for item in self.scene.items():
            if isinstance(item, StickyNote) and item.is_selected:
                selected_notes.append(item)
                
        if selected_notes:
            # Use the first selected note as our current selection
            self.update_arrangement_controls(selected_notes[0])
            print(f"Scene selection changed - selected note: {id(selected_notes[0])}")
        else:
            # No notes selected
            self.update_arrangement_controls(None)
            print("Scene selection changed - no notes selected")

    def addNote(self):
        # Get the center of the view in scene coordinates
        view_center = self.view.mapToScene(self.view.viewport().rect().center())

        # Create note centered on the view
        note = StickyNote(view_center.x() - 100, view_center.y() - 50, 200, 100)  # Offset by half width/height

        # Set highest Z value to ensure it's on top
        highest_z = max((item.zValue() for item in self.scene.items()), default=0)
        note.setZValue(highest_z + 1)

        # Add the note with undo functionality
        command = AddNoteCommand(self.scene, note)
        self.undo_stack.push(command)
        
        # Clear selection from all other notes
        for item in self.scene.items():
            if isinstance(item, StickyNote):
                item.is_selected = False
                item.update()
        
        # Select the new note
        note.is_selected = True
        note.update()
        
        # Update the arrangement controls
        self.update_arrangement_controls(note)
        
        # Initialize note color based on nesting level
        note.update_color_for_nesting()
        
        print(f"Added new note ID: {id(note)} and selected it")

    def update_arrangement_controls(self, note):
        """Update the arrangement buttons based on the selected note"""
        # Clear selection from previously selected note if different
        if self.selected_note and self.selected_note != note:
            self.selected_note.is_selected = False
            # Clear text selection when deselecting
            self.selected_note.clear_text_selection()
            self.selected_note.update()
            
        # Set the selected note and update UI state
        print(f"Setting selected note to {id(note) if note else 'None'}")
        self.selected_note = note
        
        # Enable or disable arrangement buttons based on whether a container is selected
        enabled = False if note is None else note.is_container
        self.free_button.setEnabled(enabled)
        self.rows_button.setEnabled(enabled)
        self.columns_button.setEnabled(enabled)
        
        # Update button states if a container is selected
        if enabled:
            current_mode = note.arrangement_mode
            print(f"Container's current arrangement mode: '{current_mode}'")
            self.free_button.setChecked(current_mode == 'free')
            self.rows_button.setChecked(current_mode == 'rows')
            self.columns_button.setChecked(current_mode == 'columns')
        else:
            # Clear checked state if no container selected
            self.free_button.setChecked(False)
            self.rows_button.setChecked(False)
            self.columns_button.setChecked(False)
            
    def set_arrangement_mode(self, mode):
        """Set the arrangement mode for the selected note"""
        print(f"Setting arrangement mode to '{mode}'")
        
        if not self.selected_note:
            print("No note selected")
            return
            
        if not self.selected_note.is_container:
            print(f"Selected note {id(self.selected_note)} is not a container")
            return
            
        print(f"Applying arrangement mode '{mode}' to note {id(self.selected_note)}")
        
        # Update the selected note's arrangement mode
        self.selected_note.arrangement_mode = mode
        
        # Actually apply the arrangement
        self.selected_note.arrange_children(mode)
        
        # Update button states
        self.free_button.setChecked(mode == 'free')
        self.rows_button.setChecked(mode == 'rows')
        self.columns_button.setChecked(mode == 'columns')
        
        # Force scene update to ensure all changes are visible
        self.scene.update()

    def refresh_all_notes(self):
        """Refresh all notes by recalculating their sizes and updating the display"""
        print("===== STARTING COMPLETE REFRESH =====")
        
        # Phase 1: Reset all internal states and flags
        # First, identify all notes and their hierarchy
        top_level_notes = []
        all_notes = []
        
        for item in self.scene.items():
            if isinstance(item, StickyNote):
                all_notes.append(item)
                if not item.contained_by:
                    top_level_notes.append(item)
        
        print(f"Found {len(all_notes)} notes total, {len(top_level_notes)} top-level notes")
        
        # Reset all flags and temporary state
        for note in all_notes:
            # Clear any leftover state flags
            if hasattr(note, '_resizing'):
                delattr(note, '_resizing')
            if hasattr(note, '_adjusting'):
                delattr(note, '_adjusting')
            if hasattr(note, 'is_being_dragged'):
                note.is_being_dragged = False
            if hasattr(note, 'drag_target_index'):
                note.drag_target_index = -1
                
            # Make sure opacity is reset (in case a note was being dragged)
            note.setOpacity(1.0)
        
        print("Cleared all temporary state flags")
        
        # Phase 2: Reset all notes to clean state
        for note in all_notes:
            # Temporarily block signals to prevent cascading updates
            note.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
            
            # Force reset text item widths to ensure proper text wrapping
            padding = 20
            note.title_item.document().blockSignals(True)
            note.desc_item.document().blockSignals(True)
            
            note.title_item.setTextWidth(note.FIXED_WIDTH - padding * 2)
            note.desc_item.setTextWidth(note.FIXED_WIDTH - padding * 2)
            
            # Position text items properly
            title_height = note.title_item.boundingRect().height()
            note.desc_item.setPos(5, title_height + 5)
            
            note.title_item.document().blockSignals(False)
            note.desc_item.document().blockSignals(False)
        
        print("Reset text items")
        
        # Phase 3: Reset and verify container states
        # First verify all container flags
        for note in all_notes:
            # Reset non-containers
            if not note.is_container:
                note.reset_to_normal_size()
                print(f"Reset normal note {id(note)}")
            
            # Check if it should be a container (has children)
            has_children = False
            child_count = 0
            for child in all_notes:
                if child.contained_by == note:
                    has_children = True
                    child_count += 1
            
            # Update container status
            if has_children:
                note.is_container = True
                print(f"Verified container {id(note)} with {child_count} children")
            else:
                note.is_container = False
                print(f"Verified note {id(note)} is not a container")
        
        # Re-enable geometry change signals
        for note in all_notes:
            note.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
                
        # Phase 4: Process from bottom up to ensure proper layout
        print("Starting bottom-up processing...")
        
        # First process leaf containers (containers with no sub-containers)
        leaf_containers = [note for note in all_notes if note.is_container and 
                          not any(child.is_container for child in all_notes if child.contained_by == note)]
        
        for container in leaf_containers:
            print(f"Arranging leaf container {id(container)} in '{container.arrangement_mode}' mode")
            # Force arrangement based on current mode - this should resize the container as well
            container.arrange_children(container.arrangement_mode)
            
        # Then process top-level containers that might contain other containers
        for container in top_level_notes:
            if container.is_container:
                print(f"Arranging top-level container {id(container)} in '{container.arrangement_mode}' mode")
                container.arrange_children(container.arrangement_mode)
        
        # Phase 5: Final cleanup and update
        print("Final cleanup pass...")
        
        # Do one final check_and_resize on all containers to ensure everything fits
        for note in all_notes:
            if note.is_container:
                note.check_and_resize()
        
        # Final visual updates
        self.scene.update()
        self.view.viewport().update()
        
        # Force Qt to process the update immediately
        QApplication.processEvents()
        
        # Phase 6: Update all colors based on nesting
        print("Updating note colors based on nesting levels...")
        for note in all_notes:
            note.update_color_for_nesting()
        
        print("===== REFRESH COMPLETE =====")

    def mousePressEvent(self, event):
        """Handle mouse press in main window to clear selection when clicking outside notes"""
        # Call the parent class implementation
        super().mousePressEvent(event)
        
        # Only clear selection if mouse is clicked in the view
        if self.view.underMouse():
            # Check if the click was on a note
            view_pos = self.view.mapFromGlobal(event.globalPos())
            scene_pos = self.view.mapToScene(view_pos)
            items_at_pos = self.scene.items(scene_pos)
            
            # If no items at position, clear selection
            if not items_at_pos:
                for item in self.scene.items():
                    if isinstance(item, StickyNote):
                        item.is_selected = False
                        # Clear any text selection when the note is deselected
                        item.clear_text_selection()
                        item.update()
                self.update_arrangement_controls(None)
                print("Clear selection - clicked outside any notes")

    def create_shortcuts(self):
        """Create keyboard shortcuts for the application"""
        # Duplicate note shortcut (Ctrl+D)
        duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        duplicate_shortcut.activated.connect(self.duplicate_selected_note)
        duplicate_shortcut.setContext(Qt.ApplicationShortcut)
        
        # Save canvas as image shortcut (Ctrl+S)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_canvas_as_image)
        save_shortcut.setContext(Qt.ApplicationShortcut)
        
        # Export canvas shortcut (Ctrl+E)
        export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        export_shortcut.activated.connect(self.export_canvas)
        export_shortcut.setContext(Qt.ApplicationShortcut)
        
        # Delete note shortcut (Delete key)
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self.delete_selected_note)
        delete_shortcut.setContext(Qt.ApplicationShortcut)
        
        # Copy text shortcut (Ctrl+C)
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self.copy_text_to_clipboard)
        copy_shortcut.setContext(Qt.ApplicationShortcut)
        
        # Paste text shortcut (Ctrl+V)
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self.paste_text_from_clipboard)
        paste_shortcut.setContext(Qt.ApplicationShortcut)
        
        # Add save shortcut
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_diagram_as)

    def duplicate_selected_note(self):
        """Duplicate the currently selected note"""
        if not self.selected_note:
            print("No note selected to duplicate")
            return
            
        # Create a new note based on the selected note
        original = self.selected_note
        
        # Get the position slightly offset from the original
        original_pos = original.scenePos()
        new_pos_x = original_pos.x() + 20
        new_pos_y = original_pos.y() + 20
        
        # Create new note with same dimensions
        new_note = StickyNote(new_pos_x, new_pos_y, 
                             original.rect.width(), 
                             original.rect.height())
        
        # Copy over properties and content
        new_note.title_item.setPlainText(original.title_item.toPlainText())
        new_note.desc_item.setPlainText(original.desc_item.toPlainText())
        new_note.arrangement_mode = original.arrangement_mode
        
        # If we're duplicating a container, don't duplicate the children
        # but maintain container status if needed
        new_note.is_container = False  # Will be set automatically if children are added
        
        # Add to scene with undo support
        highest_z = max((item.zValue() for item in self.scene.items()), default=0)
        new_note.setZValue(highest_z + 1)
        
        # If the original note is inside a container, add the duplicate to the same container
        if original.contained_by:
            # Temporarily add to scene so we can get the scene coordinates
            self.scene.addItem(new_note)
            
            # Block signals temporarily
            new_note.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
            
            # Add to the same container
            container = original.contained_by
            new_note.contained_by = container
            container.is_container = True
            
            # Set parent first so coordinate mapping works correctly
            new_note.setParentItem(container)

            # Find non-overlapping position inside container
            mapped_pos = container.mapFromScene(new_note.scenePos())
            new_pos = new_note.find_non_overlapping_position(mapped_pos, container)
            new_note.setPos(new_pos)
            
            # Re-enable signals
            new_note.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
            
            # Make sure container resizes to fit
            if not hasattr(container, '_resizing'):
                container.check_and_resize()
        
        # Create the command and push it to the undo stack
        command = DuplicateNoteCommand(self.scene, original, new_note)
        self.undo_stack.push(command)
        
        # Select the new note
        for item in self.scene.items():
            if isinstance(item, StickyNote):
                item.is_selected = False
                item.update()
        
        new_note.is_selected = True
        new_note.update()
        self.update_arrangement_controls(new_note)
        
        # Update color based on nesting level
        new_note.update_color_for_nesting()
        
        print(f"Duplicated note to position ({new_pos_x}, {new_pos_y})")

    def delete_selected_note(self):
        """Delete the currently selected note"""
        if self.selected_note:
            # Create an undo command
            undo_cmd = DeleteNoteCommand(self.scene, self.selected_note)
            self.undo_stack.push(undo_cmd)
            print(f"Deleting note: {id(self.selected_note)}")
            self.selected_note = None
            
    def copy_text_to_clipboard(self):
        """Copy text from the selected note to the clipboard"""
        if not self.selected_note:
            return
            
        clipboard = QApplication.clipboard()
        # Check which text item has focus
        if self.selected_note.title_item.hasFocus():
            clipboard.setText(self.selected_note.title_item.toPlainText())
        elif self.selected_note.desc_item.hasFocus():
            clipboard.setText(self.selected_note.desc_item.toPlainText())
        else:
            # If no specific text item has focus, copy both with a separator
            title_text = self.selected_note.title_item.toPlainText()
            desc_text = self.selected_note.desc_item.toPlainText()
            combined_text = f"{title_text}\n\n{desc_text}" if title_text and desc_text else title_text or desc_text
            clipboard.setText(combined_text)
            
    def paste_text_from_clipboard(self):
        """Paste text from the clipboard to the selected note"""
        if not self.selected_note:
            return
            
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        
        if not text:
            return
            
        # Paste into whichever text item has focus
        if self.selected_note.title_item.hasFocus():
            cursor = self.selected_note.title_item.textCursor()
            cursor.insertText(text)
        elif self.selected_note.desc_item.hasFocus():
            cursor = self.selected_note.desc_item.textCursor()
            cursor.insertText(text)
        else:
            # If no specific text item has focus, paste into description by default
            self.selected_note.desc_item.setPlainText(text)
            # Set focus to the description after pasting
            self.selected_note.desc_item.setFocus()
            
    def save_canvas_as_image(self):
        """Save the current canvas as an image in various formats and open it"""
        try:
            # Get the bounding rectangle of all items in the scene
            items_rect = self.scene.itemsBoundingRect()
            
            # Add some padding
            padding = 20
            items_rect.adjust(-padding, -padding, padding, padding)
            
            # Ensure we capture at least the visible area if no items exist
            if items_rect.isEmpty():
                items_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
            
            # Show file dialog to get save location and name
            options = QFileDialog.Options()
            file_filters = "PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;BMP Images (*.bmp);;SVG Images (*.svg);;All Files (*)"
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self, "Save Canvas As", "", file_filters, options=options
            )
            
            if not file_path:
                print("Save cancelled by user")
                return
                
            # Determine the format based on the selected filter or file extension
            selected_format = ""
            if "PNG" in selected_filter:
                selected_format = "PNG"
                if not file_path.lower().endswith('.png'):
                    file_path += '.png'
            elif "JPEG" in selected_filter or "JPG" in selected_filter:
                selected_format = "JPEG"
                if not file_path.lower().endswith(('.jpg', '.jpeg')):
                    file_path += '.jpg'
            elif "BMP" in selected_filter:
                selected_format = "BMP"
                if not file_path.lower().endswith('.bmp'):
                    file_path += '.bmp'
            elif "SVG" in selected_filter:
                selected_format = "SVG"
                if not file_path.lower().endswith('.svg'):
                    file_path += '.svg'
            else:
                # Determine format from file extension
                if file_path.lower().endswith('.png'):
                    selected_format = "PNG"
                elif file_path.lower().endswith(('.jpg', '.jpeg')):
                    selected_format = "JPEG"
                elif file_path.lower().endswith('.bmp'):
                    selected_format = "BMP"
                elif file_path.lower().endswith('.svg'):
                    selected_format = "SVG"
                else:
                    # Default to PNG if no extension is recognized
                    selected_format = "PNG"
                    file_path += '.png'
            
            # Special handling for SVG (vector format)
            if selected_format == "SVG":
                # Create an SVG generator
                generator = QSvgGenerator()
                generator.setFileName(file_path)
                generator.setSize(QSizeF(items_rect.width(), items_rect.height()).toSize())
                generator.setViewBox(QRectF(0, 0, items_rect.width(), items_rect.height()))
                generator.setTitle("Sticky Notes Diagram")
                generator.setDescription("Generated from the Sticky Notes application")
                
                # Create a painter to render the scene to SVG
                painter = QPainter(generator)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                
                # Set the background color
                background_color = self.scene.backgroundBrush().color()
                painter.fillRect(QRectF(0, 0, items_rect.width(), items_rect.height()), background_color)
                
                # Render the scene
                self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
                painter.end()
                
                print(f"Canvas saved as SVG: {file_path}")
            else:
                # Handle raster formats (PNG, JPEG, BMP)
                # Create an image large enough to contain the entire scene
                image = QImage(int(items_rect.width()), int(items_rect.height()), QImage.Format_ARGB32)
                image.fill(Qt.transparent)
                
                # Create a painter to render the scene to the image
                painter = QPainter(image)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)
                
                # Set the background color
                background_color = self.scene.backgroundBrush().color()
                painter.fillRect(image.rect(), background_color)
                
                # Render the scene
                self.scene.render(painter, QRectF(image.rect()), items_rect)
                painter.end()
                
                # Save the image in the selected format
                quality = 90 if selected_format == "JPEG" else -1  # Quality for JPEG, ignored for others
                if image.save(file_path, selected_format, quality):
                    print(f"Canvas saved as {selected_format}: {file_path}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to save the image in {selected_format} format.")
                    print(f"Failed to save the image in {selected_format} format")
                    return
            
            # Open the saved file with the default application
            try:
                # Use the platform-appropriate method to open the file
                if sys.platform == 'win32':
                    os.startfile(file_path)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.call(['open', file_path])
                else:  # Linux and other Unix-like
                    subprocess.call(['xdg-open', file_path])
            except Exception as open_error:
                print(f"Warning: Could not open the file automatically: {str(open_error)}")
                QMessageBox.information(self, "File Saved", f"Image saved as:\n{file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while saving the image:\n{str(e)}")
            print(f"Error saving canvas as image: {str(e)}")

    def save_diagram_as(self):
        """Save the diagram to a JSON file"""
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", 
                                                  "JSON Files (*.json);;All Files (*)")
        if file_name:
            self.save_diagram(file_name)

    def save_diagram(self, file_path):
        """Save the diagram to the specified file path"""
        try:
            # Create a dictionary to store all notes
            diagram_data = {
                "notes": []
            }
            
            # Helper function to recursively save a note and its children
            def _save_note_recursive(note):
                # Get note position in scene coordinates
                pos = note.scenePos()
                
                # Create data dictionary for this note
                note_data = {
                    'id': id(note),
                    'x': pos.x(),
                    'y': pos.y(),
                    'width': note.rect.width(),
                    'height': note.rect.height(),
                    'title': note.title_item.toPlainText(),
                    'description': note.desc_item.toPlainText(),
                    'color': note.color.name(),
                    'arrangement_mode': note.arrangement_mode,
                    'parent': id(note.contained_by) if note.contained_by else None,
                    'z_value': note.zValue()  # Save the Z-value
                }
                
                # Process children
                for child in note.childItems():
                    if isinstance(child, StickyNote):
                        child_data = _save_note_recursive(child)
                        diagram_data["notes"].append(child_data)
                
                return note_data
            
            # Get all notes in the scene
            for item in self.scene.items():
                if isinstance(item, StickyNote):
                    # Skip child notes, we'll save them with their parents
                    if item.parentItem():
                        continue
                        
                    # Get note data
                    note_data = _save_note_recursive(item)
                    diagram_data["notes"].append(note_data)
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(diagram_data, f, indent=4)
                
            # Update current file
            self.file_path = file_path
            
            QMessageBox.information(self, "Diagram Saved", f"Diagram saved to:\n{file_path}")
            print(f"Diagram saved to {file_path}")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save diagram: {str(e)}")
            print(f"Error saving diagram: {str(e)}")
            return False

    def load_diagram(self, file_path):
        """Load a diagram from the specified file path"""
        try:
            # Clear the current scene
            self.scene.clear()
            self.selected_note = None
            print("Setting selected note to None")
            
            # Load diagram data from file
            with open(file_path, 'r') as f:
                import json
                diagram_data = json.load(f)
            
            # First pass: create all notes and store them in a dictionary
            notes_dict = {}
            for note_data in diagram_data['notes']:
                # Create new note at the specified position
                note = StickyNote(
                    note_data['x'],
                    note_data['y'],
                    note_data['width'],
                    note_data['height']
                )
                
                # Set text content
                if 'title' in note_data and 'description' in note_data:
                    # Handle new format with separate title and description
                    note.title_item.setPlainText(note_data['title'])
                    note.desc_item.setPlainText(note_data['description'])
                elif 'text' in note_data:
                    # Handle old format with single text content
                    note.title_item.setPlainText(note_data['text'])
                
                # Set z-value if it was saved, otherwise use incremental z-values
                if 'z_value' in note_data:
                    note.setZValue(note_data['z_value'])
                else:
                    # Assign sequential z-values to maintain front-to-back order
                    note.setZValue(len(notes_dict) + 1 - len(notes_dict))
                
                # Set color and arrangement mode
                note.color = QColor(note_data['color'])
                note.arrangement_mode = note_data.get('arrangement_mode', 'free')
                
                # Add to scene
                self.scene.addItem(note)
                
                # Store in dictionary with persistent ID as key
                notes_dict[note_data['id']] = note
            
            # Second pass: establish parent-child relationships
            for note_data in diagram_data['notes']:
                if note_data['parent'] is not None and note_data['parent'] in notes_dict:
                    # Set the parent for this note
                    parent_note = notes_dict[note_data['parent']]
                    child_note = notes_dict[note_data['id']]
                    
                    # Update parent-child relationship
                    child_note.setParentItem(parent_note)
                    
                    # Update container status
                    parent_note.is_container = True
                    child_note.contained_by = parent_note
            
            # Third pass: apply arrangement modes to containers
            for note_id, note in notes_dict.items():
                if note.childItems() and note.parentItem() is None:  # Only process top-level containers
                    children = [child for child in note.childItems() if isinstance(child, StickyNote)]
                    if children and note.arrangement_mode != 'free':
                        print(f"Arranging container with {len(children)} children in {note.arrangement_mode} mode")
                        note.arrange_children(note.arrangement_mode)
                
            # Final refresh to update all notes
            self.refresh_all_notes()
                    
            # Center the view
            self.view.reset_view()
            
            QMessageBox.information(self, "Diagram Loaded", f"Diagram loaded from:\n{file_path}")
            print(f"Diagram loaded from {file_path}")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load diagram: {str(e)}")
            print(f"Error loading diagram: {str(e)}")
            return False

    def export_canvas(self):
        """Export the current canvas in various formats (SVG, PNG, JPEG, PDF, HTML)"""
        try:
            # Get the bounding rectangle of all items in the scene
            items_rect = self.scene.itemsBoundingRect()
            
            # Add some padding
            padding = 20
            items_rect.adjust(-padding, -padding, padding, padding)
            
            # Ensure we capture at least the visible area if no items exist
            if items_rect.isEmpty():
                items_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
            
            # Show file dialog to get export location and format
            options = QFileDialog.Options()
            file_filters = "SVG Images (*.svg);;PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;PDF Documents (*.pdf);;HTML Documents (*.html);;All Files (*)"
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self, "Export Canvas As", "", file_filters, options=options
            )
            
            if not file_path:
                print("Export cancelled by user")
                return
                
            # Determine the format based on the selected filter or file extension
            selected_format = ""
            if "SVG" in selected_filter:
                selected_format = "SVG"
                if not file_path.lower().endswith('.svg'):
                    file_path += '.svg'
            elif "PNG" in selected_filter:
                selected_format = "PNG"
                if not file_path.lower().endswith('.png'):
                    file_path += '.png'
            elif "JPEG" in selected_filter or "JPG" in selected_filter:
                selected_format = "JPEG"
                if not file_path.lower().endswith(('.jpg', '.jpeg')):
                    file_path += '.jpg'
            elif "PDF" in selected_filter:
                selected_format = "PDF"
                if not file_path.lower().endswith('.pdf'):
                    file_path += '.pdf'
            elif "HTML" in selected_filter:
                selected_format = "HTML"
                if not file_path.lower().endswith('.html'):
                    file_path += '.html'
            else:
                # Determine format from file extension
                if file_path.lower().endswith('.svg'):
                    selected_format = "SVG"
                elif file_path.lower().endswith('.png'):
                    selected_format = "PNG"
                elif file_path.lower().endswith(('.jpg', '.jpeg')):
                    selected_format = "JPEG"
                elif file_path.lower().endswith('.pdf'):
                    selected_format = "PDF"
                elif file_path.lower().endswith('.html'):
                    selected_format = "HTML"
                else:
                    # Default to PNG if no extension is recognized
                    selected_format = "PNG"
                    file_path += '.png'
            
            # Handle SVG export (vector format)
            if selected_format == "SVG":
                # Create an SVG generator
                generator = QSvgGenerator()
                generator.setFileName(file_path)
                generator.setSize(QSizeF(items_rect.width(), items_rect.height()).toSize())
                generator.setViewBox(QRectF(0, 0, items_rect.width(), items_rect.height()))
                generator.setTitle("Sticky Notes Diagram")
                generator.setDescription("Generated from the Sticky Notes application")
                
                # Create a painter to render the scene to SVG
                painter = QPainter(generator)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                
                # Set the background color
                background_color = self.scene.backgroundBrush().color()
                painter.fillRect(QRectF(0, 0, items_rect.width(), items_rect.height()), background_color)
                
                # Render the scene
                self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
                painter.end()
                
                print(f"Canvas exported as SVG: {file_path}")
                
            # Handle PDF export
            elif selected_format == "PDF":
                # Create a PDF printer/writer
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(file_path)
                printer.setPaperSize(QSizeF(items_rect.width(), items_rect.height()), QPrinter.Point)
                printer.setPageMargins(0, 0, 0, 0, QPrinter.Point)
                
                # Create a painter to render the scene to PDF
                painter = QPainter(printer)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                
                # Set the background color
                background_color = self.scene.backgroundBrush().color()
                painter.fillRect(QRectF(0, 0, items_rect.width(), items_rect.height()), background_color)
                
                # Render the scene
                self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
                painter.end()
                
                print(f"Canvas exported as PDF: {file_path}")
                
            # Handle HTML export
            elif selected_format == "HTML":
                # First, export as SVG for embedding in HTML
                temp_svg_path = file_path.replace('.html', '.svg')
                
                # Create an SVG generator
                generator = QSvgGenerator()
                generator.setFileName(temp_svg_path)
                generator.setSize(QSizeF(items_rect.width(), items_rect.height()).toSize())
                generator.setViewBox(QRectF(0, 0, items_rect.width(), items_rect.height()))
                generator.setTitle("Sticky Notes Diagram")
                generator.setDescription("Generated from the Sticky Notes application")
                
                # Create a painter to render the scene to SVG
                painter = QPainter(generator)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                
                # Set the background color
                background_color = self.scene.backgroundBrush().color()
                painter.fillRect(QRectF(0, 0, items_rect.width(), items_rect.height()), background_color)
                
                # Render the scene
                self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
                painter.end()
                
                # Create a minimal HTML file with the SVG embedded
                # Extract the background color in hex format for HTML
                bg_color_hex = background_color.name()
                
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Notebox Diagram</title>
    <style>
        body {{ 
            margin: 0;
            padding: 0;
            overflow: hidden;
            background-color: {bg_color_hex};
        }}
        svg {{ 
            width: 100%;
            height: 100vh;
            display: block;
        }}
    </style>
</head>
<body>
    <img src="{os.path.basename(temp_svg_path)}" alt="Notebox Diagram">
</body>
</html>
"""
                # Write HTML file
                with open(file_path, 'w') as f:
                    f.write(html_content)
                
                print(f"Canvas exported as HTML: {file_path} (with associated SVG image)")
            
            else:
                # Handle raster formats (PNG, JPEG)
                # Create an image large enough to contain the entire scene
                image = QImage(int(items_rect.width()), int(items_rect.height()), QImage.Format_ARGB32)
                image.fill(Qt.transparent)
                
                # Create a painter to render the scene to the image
                painter = QPainter(image)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)
                
                # Set the background color
                background_color = self.scene.backgroundBrush().color()
                painter.fillRect(image.rect(), background_color)
                
                # Render the scene
                self.scene.render(painter, QRectF(image.rect()), items_rect)
                painter.end()
                
                # Save the image in the selected format
                quality = 90 if selected_format == "JPEG" else -1  # Quality for JPEG, ignored for others
                if image.save(file_path, selected_format, quality):
                    print(f"Canvas exported as {selected_format}: {file_path}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to export the image in {selected_format} format.")
                    print(f"Failed to export the image in {selected_format} format")
                    return
            
            # Show success message
            QMessageBox.information(self, "Export Successful", f"Canvas successfully exported as {selected_format} to:\n{file_path}")
            
            # Open the exported file with the default application
            try:
                # Use the platform-appropriate method to open the file
                if sys.platform == 'win32':
                    os.startfile(file_path)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.call(['open', file_path])
                else:  # Linux
                    subprocess.call(['xdg-open', file_path])
            except Exception as e:
                print(f"Error opening exported file: {str(e)}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export the canvas: {str(e)}")
            print(f"Error exporting canvas: {str(e)}")
            import traceback
            traceback.print_exc()

    def create_window_icon(self):
        """Create a custom window icon with a simple box"""
        try:
            # Create a pixmap for the icon
            icon_size = 64
            icon_pixmap = QPixmap(icon_size, icon_size)
            icon_pixmap.fill(Qt.transparent)
            
            # Draw a box icon on the pixmap
            painter = QPainter(icon_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw a simple box
            painter.setPen(QPen(QColor(0, 0, 0), 3))
            painter.setBrush(QBrush(QColor(40, 40, 40)))
            painter.drawRect(10, 10, icon_size - 20, icon_size - 20)
            
            painter.end()
            
            # Create icon from pixmap and set as window icon
            icon = QIcon(icon_pixmap)
            self.setWindowIcon(icon)
        except Exception as e:
            print(f"Error creating window icon: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
