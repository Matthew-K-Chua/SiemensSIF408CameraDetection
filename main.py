#!/usr/bin/env python3
"""
Camera Inspection Stub - OPC UA Client with GUI Integration
Mimics camera inspection workflow using the circle selector GUI
"""

import sys
import os
import asyncio
import threading
from dataclasses import dataclass
from asyncua import Client, ua

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt, Signal, QObject

# Import the circle selector GUI
from circle_selector import CircleWidget, QWidget, QVBoxLayout, QGridLayout, QPushButton


class InspectionGUI(QWidget):
    """GUI for simulating container inspection with submit callback"""
    
    submission_complete = Signal(dict)  # Emits {c1, c2, c3, c4: bool}
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Container Inspection - Mark Defects")
        self.setMinimumSize(500, 600)
        self.result_ready = False
        self.results = {}
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions
        from PySide6.QtWidgets import QLabel
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
        
        # Add circles to grid (matching the layout from original GUI)
        grid_layout.addWidget(self.c2_circle, 0, 0)
        grid_layout.addWidget(self.c1_circle, 0, 1)
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
        # Get states (TRUE if red/needs correction, FALSE if green/OK)
        self.results = {
            'c1_recorrect': self.c1_circle.get_state(),
            'c2_recorrect': self.c2_circle.get_state(),
            'c3_recorrect': self.c3_circle.get_state(),
            'c4_recorrect': self.c4_circle.get_state(),
        }
        
        # Print results in the specified format
        print("\n=== INSPECTION RESULTS ===")
        print(f"    c1_recorrect      := {self.results['c1_recorrect']}")
        print(f"    c2_recorrect      := {self.results['c2_recorrect']}")
        print(f"    c3_recorrect      := {self.results['c3_recorrect']}")
        print(f"    c4_recorrect      := {self.results['c4_recorrect']}")
        print("=========================\n")
        
        self.result_ready = True
        self.submission_complete.emit(self.results)
        
        # Reset circles for next inspection
        self.c1_circle.reset()
        self.c2_circle.reset()
        self.c3_circle.reset()
        self.c4_circle.reset()
        
        # Close the window
        self.close()
    
    def reset(self):
        """Reset for new inspection"""
        self.result_ready = False
        self.results = {}
        self.c1_circle.reset()
        self.c2_circle.reset()
        self.c3_circle.reset()
        self.c4_circle.reset()


class GUIBridge(QObject):
    """Bridge to safely launch GUI from async code"""
    show_gui_signal = Signal()
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.gui = None
        self.gui_future = None
        self.show_gui_signal.connect(self._show_gui_slot)
        
    def _show_gui_slot(self):
        """Qt slot to show GUI (runs in main thread)"""
        if self.gui is None or not self.gui.isVisible():
            self.gui = InspectionGUI()
            self.gui.submission_complete.connect(self._on_submission)
            self.gui.show()
            
    def _on_submission(self, results):
        """Handle submission from GUI"""
        if self.gui_future and not self.gui_future.done():
            self.gui_future.set_result(results)
    
    async def get_inspection_results(self):
        """Async method to show GUI and wait for results"""
        loop = asyncio.get_event_loop()
        self.gui_future = loop.create_future()
        
        # Trigger GUI show in main thread
        self.show_gui_signal.emit()
        
        # Wait for results
        results = await self.gui_future
        return results


@dataclass
class InspectionState:
    """Internal state for camera inspection"""
    inspection_id: int = 0
    photo_step_done: int = 0  # 0 none, 1 first view, 2 second view
    results_version: int = 0
    c1_recorrect: bool = False
    c2_recorrect: bool = False
    c3_recorrect: bool = False
    c4_recorrect: bool = False


async def camera_inspection_loop(gui_bridge: GUIBridge):
    """
    Main camera inspection loop following the pseudocode
    Connects to PLC via OPC UA and publishes inspection state
    """
    
    # OPC UA Configuration
    url = os.getenv("OPC_URL", "opc.tcp://192.168.0.1:4840")
    ua_user = os.getenv("OPC_UA_USER")
    ua_pass = os.getenv("OPC_UA_PASS")
    request_timeout = float(os.getenv("OPC_TIMEOUT_SEC", "5"))
    
    # Node IDs for inspection variables
    # NOTE: Adjust these node IDs to match your PLC configuration
    nodeids = {
        # State variables to publish
        "inspection_id": "ns=6;i=1",
        "photo_step_done": "ns=6;i=2",
        "results_version": "ns=6;i=3",
        "c1_recorrect": "ns=6;i=4",
        "c2_recorrect": "ns=6;i=5",
        "c3_recorrect": "ns=6;i=6",
        "c4_recorrect": "ns=6;i=7",
        
        # Control variables to read
        "mm_received_instruction": "ns=6;i=20",  # Trigger for new inspection
        "photo_ready_step": "ns=6;i=21",         # 1 = first view, 2 = second view
    }
    
    print(f"Connecting to OPC UA server at {url}...")
    
    max_retries = 5
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            async with Client(url=url, timeout=request_timeout) as client:
                print("Connected to OPC UA server")
                
                # Set authentication if provided
                if ua_user and ua_pass:
                    await client.set_user(ua_user)
                    await client.set_password(ua_pass)
                
                # Get node references
                nodes = {k: client.get_node(v) for k, v in nodeids.items()}
                print("Node references obtained")
                
                # Initialize inspection state
                state = InspectionState()
                
                print("\n=== CAMERA INSPECTION STUB STARTED ===")
                print("Waiting for inspection triggers from PLC...")
                print("(Simulating: photo_ready_step = 2, photo_step_done = 1)\n")
                
                # Simulate the condition being met for testing
                # In real system, these would be read from PLC
                simulated_photo_ready_step = 2
                
                # Main inspection loop
                while True:
                    try:
                        # ---- CONTINUOUS PUBLISH ----
                        # Publish all state variables to PLC
                        await nodes["inspection_id"].write_value(
                            ua.DataValue(ua.Variant(state.inspection_id, ua.VariantType.Int32))
                        )
                        await nodes["photo_step_done"].write_value(
                            ua.DataValue(ua.Variant(state.photo_step_done, ua.VariantType.Int32))
                        )
                        await nodes["results_version"].write_value(
                            ua.DataValue(ua.Variant(state.results_version, ua.VariantType.Int32))
                        )
                        await nodes["c1_recorrect"].write_value(
                            ua.DataValue(ua.Variant(state.c1_recorrect, ua.VariantType.Boolean))
                        )
                        await nodes["c2_recorrect"].write_value(
                            ua.DataValue(ua.Variant(state.c2_recorrect, ua.VariantType.Boolean))
                        )
                        await nodes["c3_recorrect"].write_value(
                            ua.DataValue(ua.Variant(state.c3_recorrect, ua.VariantType.Boolean))
                        )
                        await nodes["c4_recorrect"].write_value(
                            ua.DataValue(ua.Variant(state.c4_recorrect, ua.VariantType.Boolean))
                        )
                        
                        # ---- START NEW INSPECTION ----
                        # Read instruction trigger from PLC
                        mm_received = await nodes["mm_received_instruction"].read_value()
                        if mm_received:
                            state.inspection_id += 1
                            state.photo_step_done = 0
                            print(f"\n[NEW INSPECTION] ID: {state.inspection_id}")
                            # Keep previous results published until new results commit
                        
                        # ---- FIRST VIEW (commented out in pseudocode, keeping here for completeness) ----
                        # photo_ready = await nodes["photo_ready_step"].read_value()
                        # if photo_ready == 1 and state.photo_step_done == 0:
                        #     print("[FIRST VIEW] Taking photo, processing C1 & C3...")
                        #     state.photo_step_done = 1
                        
                        # ---- SECOND VIEW + ATOMIC COMMIT ----
                        # For testing, we're simulating photo_ready_step = 2
                        # In production, read from PLC: photo_ready = await nodes["photo_ready_step"].read_value()
                        photo_ready = simulated_photo_ready_step
                        
                        if photo_ready == 2 and state.photo_step_done == 1:
                            print("\n[SECOND VIEW] Launching inspection GUI...")
                            
                            # Launch GUI and wait for user input
                            results = await gui_bridge.get_inspection_results()
                            
                            # Compute fresh booleans locally (no publishing yet)
                            new_c1 = results['c1_recorrect']
                            new_c2 = results['c2_recorrect']
                            new_c3 = results['c3_recorrect']
                            new_c4 = results['c4_recorrect']
                            
                            # ATOMIC COMMIT: update all bits, then bump version
                            state.c1_recorrect = new_c1
                            state.c2_recorrect = new_c2
                            state.c3_recorrect = new_c3
                            state.c4_recorrect = new_c4
                            state.results_version += 1  # <-- COMMIT POINT
                            state.photo_step_done = 2
                            
                            print(f"[COMMIT] Results version {state.results_version} published")
                            print(f"  Inspection ID: {state.inspection_id}")
                            print(f"  Corrections: C1={new_c1}, C2={new_c2}, C3={new_c3}, C4={new_c4}\n")
                            
                            # For testing: reset to allow another inspection
                            # In production, wait for next mm_received_instruction
                            await asyncio.sleep(2)
                            state.photo_step_done = 1  # Reset to trigger another GUI launch
                        
                        # Wait before next cycle (100ms = 10Hz publish rate)
                        await asyncio.sleep(0.1)
                        
                    except asyncio.CancelledError:
                        print("\n[SHUTDOWN] Inspection loop cancelled")
                        raise
                    except Exception as e:
                        print(f"[ERROR] Loop iteration failed: {e}")
                        await asyncio.sleep(1.0)
                        
        except asyncio.CancelledError:
            print("[SHUTDOWN] Camera inspection stopping...")
            raise
        except Exception as e:
            print(f"[ERROR] Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print("Failed to connect after maximum retries")
                raise


def main():
    """Main entry point"""
    print("=== Camera Inspection Stub ===")
    print("This stub simulates camera inspection using a GUI")
    print("Configure OPC_URL environment variable to connect to your PLC")
    print(f"Current URL: {os.getenv('OPC_URL', 'opc.tcp://192.168.0.1:4840')}\n")
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create GUI bridge for async interaction
    gui_bridge = GUIBridge(app)
    
    # Create async event loop in separate thread
    loop = asyncio.new_event_loop()
    
    def run_async_loop():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(camera_inspection_loop(gui_bridge))
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Keyboard interrupt received")
        finally:
            loop.close()
    
    # Start async loop in background thread
    async_thread = threading.Thread(target=run_async_loop, daemon=True)
    async_thread.start()
    
    # Run Qt event loop in main thread
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Keyboard interrupt in main thread")
        exit_code = 0
    finally:
        # Clean up
        if not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)
        async_thread.join(timeout=2.0)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
