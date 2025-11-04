#!/usr/bin/env python3
"""
inspection_gui.py

Standalone GUI module for container inspection.
Can process specific containers (C1+C3 or C2+C4) per view.
"""

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, 
    QPushButton, QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen
import sys


class CircleWidget(QWidget):
    """A clickable circular widget that toggles between green and red"""
    
    clicked = Signal()
    
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.is_red = False  # Start as green (FALSE)
        self.setMinimumSize(150, 150)
        self.setCursor(Qt.PointingHandCursor)
        self.enabled = True  # Can be disabled to grey out
        
    def paintEvent(self, event):
        """Draw the circle with the current colour"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set colour based on state and enabled status
        if not self.enabled:
            fill_colour = QColor(200, 200, 200)  # Grey
            border_colour = QColor(150, 150, 150)
        elif self.is_red:
            fill_colour = QColor(220, 160, 160)  # Red/pink
            border_colour = QColor(180, 100, 100)
        else:
            fill_colour = QColor(180, 220, 180)  # Green
            border_colour = QColor(100, 150, 100)
        
        # Draw circle
        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.setPen(QPen(border_colour, 3))
        painter.setBrush(fill_colour)
        painter.drawEllipse(rect)
        
        # Draw label
        painter.setPen(Qt.black if self.enabled else QColor(150, 150, 150))
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.label)
        
    def mousePressEvent(self, event):
        """Toggle colour when clicked (only if enabled)"""
        if event.button() == Qt.LeftButton and self.enabled:
            self.toggle()
            self.clicked.emit()
            
    def toggle(self):
        """Toggle between red and green"""
        if self.enabled:
            self.is_red = not self.is_red
            self.update()
    
    def set_enabled(self, enabled):
        """Enable or disable this circle"""
        self.enabled = enabled
        if not enabled:
            self.is_red = False  # Reset to green when disabled
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)
        self.update()
        
    def reset(self):
        """Reset to green (FALSE)"""
        self.is_red = False
        self.update()
        
    def get_state(self):
        """Return True if red (needs correction), False if green (OK)"""
        return self.is_red


class InspectionGUI(QWidget):
    """
    GUI for container inspection with defect marking.
    
    Can operate in two modes:
    - Full view: All 4 containers (C1, C2, C3, C4)
    - Partial view: Specific containers only (e.g., C1+C3 or C2+C4)
    
    Signals:
        submission_complete: Emitted when user submits results.
                            Payload is dict: {'c1_recorrect': bool, ...}
    """
    
    submission_complete = Signal(dict)
    
    def __init__(self, active_containers=None, view_name="Container Inspection", parent=None):
        """
        Args:
            active_containers: List of container IDs to enable (e.g., [1, 3] for C1 and C3)
                              If None, all containers are enabled
            view_name: Name to display in window title and instructions
        """
        super().__init__(parent)
        self.active_containers = active_containers if active_containers else [1, 2, 3, 4]
        self.view_name = view_name
        self.setWindowTitle(f"{view_name} - Mark Defects")
        self.setMinimumSize(500, 600)
        self.result_ready = False
        self.results = {}
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the user interface"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions
        container_list = ", ".join([f"C{i}" for i in sorted(self.active_containers)])
        instructions = QLabel(
            f"<h2>{self.view_name}</h2>"
            f"<p><b>Processing containers: {container_list}</b></p>"
            "<p>Click <b>GREEN</b> containers that need <b>CORRECTION</b> to mark them <b>RED</b></p>"
            "<p>Click <b>RED</b> containers to mark them as <b>OK</b> (GREEN)</p>"
            "<p><i>Grey containers are not being inspected in this view</i></p>"
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(instructions)
        
        # Create grid layout for circles
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        # Create circles (C2, C1 in top row; C3, C4 in bottom row)
        self.c2_circle = CircleWidget("C2")
        self.c1_circle = CircleWidget("C1")
        self.c3_circle = CircleWidget("C3")
        self.c4_circle = CircleWidget("C4")
        
        # Enable/disable based on active_containers
        self.c1_circle.set_enabled(1 in self.active_containers)
        self.c2_circle.set_enabled(2 in self.active_containers)
        self.c3_circle.set_enabled(3 in self.active_containers)
        self.c4_circle.set_enabled(4 in self.active_containers)
        
        # Add circles to grid
        grid_layout.addWidget(self.c2_circle, 0, 1)
        grid_layout.addWidget(self.c1_circle, 0, 0)
        grid_layout.addWidget(self.c3_circle, 1, 0)
        grid_layout.addWidget(self.c4_circle, 1, 1)
        
        main_layout.addLayout(grid_layout)
        
        # Create submit button
        self.submit_button = QPushButton("Submit Inspection Results")
        self.submit_button.setMinimumHeight(60)
        self.submit_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.submit_button.clicked.connect(self.on_submit)
        main_layout.addWidget(self.submit_button)
        
    def on_submit(self):
        """Collect results and emit signal"""
        # Get states (True if red/needs correction, False if green/OK)
        # Only report results for active containers
        self.results = {
            'c1_recorrect': self.c1_circle.get_state() if 1 in self.active_containers else None,
            'c2_recorrect': self.c2_circle.get_state() if 2 in self.active_containers else None,
            'c3_recorrect': self.c3_circle.get_state() if 3 in self.active_containers else None,
            'c4_recorrect': self.c4_circle.get_state() if 4 in self.active_containers else None,
        }
        
        # Print results
        print(f"\n[GUI] === {self.view_name.upper()} RESULTS ===")
        for i in [1, 2, 3, 4]:
            key = f'c{i}_recorrect'
            if self.results[key] is not None:
                print(f"[GUI]     {key} := {self.results[key]}")
            else:
                print(f"[GUI]     {key} := (not processed)")
        print("[GUI] ============================\n")
        
        self.result_ready = True
        self.submission_complete.emit(self.results)
        
        # Reset circles for next inspection
        self._reset_circles()
        
        # Close the window
        self.close()
    
    def _reset_circles(self):
        """Reset all circles to green"""
        self.c1_circle.reset()
        self.c2_circle.reset()
        self.c3_circle.reset()
        self.c4_circle.reset()
    
    def reset(self):
        """Reset GUI for new inspection"""
        self.result_ready = False
        self.results = {}
        self._reset_circles()


def process_containers_gui(active_containers=None, view_name="Container Inspection"):
    """
    Run GUI for manual container inspection.
    This is a blocking call that returns when the user submits.
    
    Args:
        active_containers: List of container IDs to process (e.g., [1, 3])
                          If None, all containers are enabled
        view_name: Display name for this inspection view
    
    Returns:
        dict: {'c1_recorrect': bool/None, 'c2_recorrect': bool/None, ...}
              None values indicate containers not processed in this view
    """
    # Create QApplication if it doesn't exist
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create and show GUI
    gui = InspectionGUI(active_containers=active_containers, view_name=view_name)
    
    # Store results
    results = {'submitted': False}
    
    def handle_submission(data):
        results['data'] = data
        results['submitted'] = True
    
    gui.submission_complete.connect(handle_submission)
    gui.show()
    
    # Run event loop until submission
    while not results['submitted']:
        app.processEvents()
    
    # Return the full dict (with None for inactive containers)
    return results['data']


# Allow standalone testing
if __name__ == "__main__":
    def handle_submission(results):
        print(f"Received results: {results}")
    
    app = QApplication(sys.argv)
    
    # Test with only C1 and C3
    gui = InspectionGUI(active_containers=[1, 3], view_name="First View (C1, C3)")
    gui.submission_complete.connect(handle_submission)
    gui.show()
    
    sys.exit(app.exec())
