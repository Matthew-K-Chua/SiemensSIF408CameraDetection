#!/usr/bin/env python3
"""
Circle Selection GUI - PySide6 Application
Toggle circles between green (FALSE) and red (TRUE) and submit selections
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QGridLayout, QPushButton, QLabel)
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
        """Return TRUE if red, FALSE if green"""
        return self.is_red


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circle Selection Interface")
        self.setMinimumSize(500, 600)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Create grid layout for circles
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        # Create circles (C2, C1 in top row; C3, C4 in bottom row)
        self.c2_circle = CircleWidget("C2")
        self.c1_circle = CircleWidget("C1")
        self.c3_circle = CircleWidget("C3")
        self.c4_circle = CircleWidget("C4")
        
        # Add circles to grid
        grid_layout.addWidget(self.c2_circle, 0, 0)
        grid_layout.addWidget(self.c1_circle, 0, 1)
        grid_layout.addWidget(self.c3_circle, 1, 0)
        grid_layout.addWidget(self.c4_circle, 1, 1)
        
        # Create submit button
        self.submit_button = QPushButton("Submit")
        self.submit_button.setMinimumHeight(50)
        self.submit_button.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 2px solid #999;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.submit_button.clicked.connect(self.on_submit)
        
        # Add layouts to main layout
        main_layout.addLayout(grid_layout)
        main_layout.addWidget(self.submit_button)
        
    def on_submit(self):
        """Handle submit button click - output state and reset"""
        # Get states (TRUE if red, FALSE if green)
        c1_state = "TRUE" if self.c1_circle.get_state() else "FALSE"
        c2_state = "TRUE" if self.c2_circle.get_state() else "FALSE"
        c3_state = "TRUE" if self.c3_circle.get_state() else "FALSE"
        c4_state = "TRUE" if self.c4_circle.get_state() else "FALSE"
        
        # Output in the specified format
        output = f"""    c1_recorrect      := {c1_state}
    c2_recorrect      := {c2_state}
    c3_recorrect      := {c3_state}
    c4_recorrect      := {c4_state}"""
        
        print(output)
        print()  # Blank line for readability
        
        # Reset all circles to green
        self.c1_circle.reset()
        self.c2_circle.reset()
        self.c3_circle.reset()
        self.c4_circle.reset()


def main():
    """Run the application"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
