#!/usr/bin/env python3
"""
inspection_gui.py

Standalone GUI module for container inspection.
Can be run independently or imported by other programs.
"""

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, 
    QPushButton, QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen


class CircleWidget(QWidget):
    """A clickable circular widget that toggles between green and red"""
    
    clicked = Signal()
    
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.is_red = False  # Start as green (FALSE)
        self.setMinimumSize(150, 150)
        self.setCursor(Qt.PointingHandCursor)
        
    def paintEvent(self, event):
        """Draw the circle with the current colour"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set colour based on state
        if self.is_red:
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
        painter.setPen(Qt.black)
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.label)
        
    def mousePressEvent(self, event):
        """Toggle colour when clicked"""
        if event.button() == Qt.LeftButton:
            self.toggle()
            self.clicked.emit()
            
    def toggle(self):
        """Toggle between red and green"""
        self.is_red = not self.is_red
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
    
    Signals:
        submission_complete: Emitted when user submits results.
                            Payload is dict: {'c1_recorrect': bool, ...}
    
    Usage:
        gui = InspectionGUI()
        gui.submission_complete.connect(handle_results)
        gui.show()
    """
    
    submission_complete = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Container Inspection - Mark Defects")
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
        instructions = QLabel(
            "<h2>Container Inspection</h2>"
            "<p>Click <b>GREEN</b> containers that need <b>CORRECTION</b> to mark them <b>RED</b></p>"
            "<p>Click <b>RED</b> containers to mark them as <b>OK</b> (GREEN)</p>"
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
        self.results = {
            'c1_recorrect': self.c1_circle.get_state(),
            'c2_recorrect': self.c2_circle.get_state(),
            'c3_recorrect': self.c3_circle.get_state(),
            'c4_recorrect': self.c4_circle.get_state(),
        }
        
        # Print results
        print("\n=== INSPECTION RESULTS ===")
        print(f"    c1_recorrect      := {self.results['c1_recorrect']}")
        print(f"    c2_recorrect      := {self.results['c2_recorrect']}")
        print(f"    c3_recorrect      := {self.results['c3_recorrect']}")
        print(f"    c4_recorrect      := {self.results['c4_recorrect']}")
        print("=========================\n")
        
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


# Allow standalone testing
if __name__ == "__main__":
    import sys
    
    def handle_submission(results):
        print(f"Received results: {results}")
    
    app = QApplication(sys.argv)
    gui = InspectionGUI()
    gui.submission_complete.connect(handle_submission)
    gui.show()
    sys.exit(app.exec())
