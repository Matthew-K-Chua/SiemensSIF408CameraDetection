#!/usr/bin/env python3
"""
camera_inspection_main.py

OPC UA client for camera inspection system.
Handles PLC communication and coordinates with inspection GUI.
"""

import sys
import os
import asyncio
import threading
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

from asyncua import Client, ua

# Import our GUI module
from inspection_gui import InspectionGUI


class GUIBridge(QObject):
    """
    Thread-safe bridge between asyncio OPC UA code and Qt GUI.
    
    Handles launching the GUI from async code and waiting for results.
    """
    
    show_gui_signal = Signal()
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.gui = None
        self.gui_future = None
        self.show_gui_signal.connect(self._show_gui_slot)
        
    def _show_gui_slot(self):
        """Qt slot to show GUI (runs in main Qt thread)"""
        if self.gui is None or not self.gui.isVisible():
            self.gui = InspectionGUI()
            self.gui.submission_complete.connect(self._on_submission)
            self.gui.show()
            
    def _on_submission(self, results):
        """Handle submission from GUI"""
        if self.gui_future and not self.gui_future.done():
            self.gui_future.set_result(results)
    
    async def get_inspection_results(self):
        """
        Async method to show GUI and wait for user input.
        
        Returns:
            dict: {'c1_recorrect': bool, 'c2_recorrect': bool, ...}
        """
        loop = asyncio.get_event_loop()
        self.gui_future = loop.create_future()
        
        # Trigger GUI show in main thread
        self.show_gui_signal.emit()
        
        # Wait for results
        results = await self.gui_future
        return results


@dataclass
class InspectionState:
    """
    Internal state for camera inspection workflow.
    
    Attributes:
        inspection_id: Increments on each new inspection
        photo_step_done: 0=none, 1=first view, 2=second view complete
        results_version: Increments on each result commit (atomic commit marker)
        c1_recorrect: Container 1 needs correction
        c2_recorrect: Container 2 needs correction
        c3_recorrect: Container 3 needs correction
        c4_recorrect: Container 4 needs correction
    """
    inspection_id: int = 0
    photo_step_done: int = 0
    results_version: int = 0
    c1_recorrect: bool = False
    c2_recorrect: bool = False
    c3_recorrect: bool = False
    c4_recorrect: bool = False


async def publish_state(nodes, state):
    """
    Publish all state variables to PLC.
    
    Args:
        nodes: Dict of OPC UA node references
        state: InspectionState object
    """
    try:
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
    except Exception as e:
        print(f"[ERROR] Failed to publish state: {e}")


async def inspection_loop(gui_bridge, nodes):
    """
    Main inspection state machine loop.
    
    Implements the pseudocode:
    - Continuous publishing
    - Start new inspection on trigger
    - Launch GUI for second view
    - Atomic commit of results
    
    Args:
        gui_bridge: GUIBridge instance for showing GUI
        nodes: Dict of OPC UA node references
    """
    state = InspectionState()
    
    print("\n=== CAMERA INSPECTION STARTED ===")
    print("Waiting for inspection triggers from PLC...")
    print("(Test mode: photo_ready_step=2, photo_step_done=1 simulated)\n")
    
    # For testing: simulate conditions
    # In production, read these from PLC
    simulated_photo_ready_step = 2
    simulated_mm_received = False  # Set to True to test new inspection trigger
    
    while True:
        try:
            # ---- CONTINUOUS PUBLISH ----
            await publish_state(nodes, state)
            
            # ---- START NEW INSPECTION ----
            # Read trigger from PLC (or use simulated for testing)
            try:
                mm_received = await nodes["mm_received_instruction"].read_value()
            except:
                mm_received = simulated_mm_received
            
            if mm_received:
                state.inspection_id += 1
                state.photo_step_done = 0
                print(f"\n[NEW INSPECTION] ID: {state.inspection_id}")
                # Keep previous results published until new results commit
            
            # ---- FIRST VIEW ----
            # try:
            #     photo_ready = await nodes["photo_ready_step"].read_value()
            # except:
            #     photo_ready = 0
            # 
            # if photo_ready == 1 and state.photo_step_done == 0:
            #     print("[FIRST VIEW] Processing C1 & C3...")
            #     # TakePhoto()
            #     # ProcessContainers(C1, C3)
            #     state.photo_step_done = 1
            
            # ---- SECOND VIEW + ATOMIC COMMIT ----
            # Read from PLC (or use simulated for testing)
            try:
                photo_ready = await nodes["photo_ready_step"].read_value()
            except:
                photo_ready = simulated_photo_ready_step
            
            if photo_ready == 2 and state.photo_step_done == 1:
                print("\n[SECOND VIEW] Launching inspection GUI...")
                
                # Get results from GUI (this blocks until user submits)
                results = await gui_bridge.get_inspection_results()
                
                # Compute fresh booleans locally (no publishing yet)
                new_c1 = results['c1_recorrect']
                new_c2 = results['c2_recorrect']
                new_c3 = results['c3_recorrect']
                new_c4 = results['c4_recorrect']
                
                # ATOMIC COMMIT: Write all bits, then bump version
                state.c1_recorrect = new_c1
                state.c2_recorrect = new_c2
                state.c3_recorrect = new_c3
                state.c4_recorrect = new_c4
                state.results_version += 1  # <-- COMMIT POINT
                state.photo_step_done = 2
                
                print(f"[COMMIT] Results version {state.results_version} published")
                print(f"  Inspection ID: {state.inspection_id}")
                print(f"  Corrections: C1={new_c1}, C2={new_c2}, C3={new_c3}, C4={new_c4}\n")
                
                # For testing: Reset to trigger another inspection cycle
                # In production, remove this - wait for next mm_received_instruction
                await asyncio.sleep(2)
                state.photo_step_done = 1  # Trigger another GUI launch
            
            # Wait 100ms (10 Hz publish rate)
            await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            print("\n[SHUTDOWN] Inspection loop cancelled")
            raise
        except Exception as e:
            print(f"[ERROR] Loop iteration failed: {e}")
            await asyncio.sleep(1.0)


async def opc_ua_main(gui_bridge):
    """
    Main OPC UA connection and coordination.
    
    Handles:
    - Connection with retry logic
    - Node ID mapping
    - Starting the inspection loop
    
    Args:
        gui_bridge: GUIBridge instance for GUI coordination
    """
    # Configuration from environment
    url = os.getenv("OPC_URL", "opc.tcp://192.168.0.1:4840")
    ua_user = os.getenv("OPC_UA_USER")
    ua_pass = os.getenv("OPC_UA_PASS")
    request_timeout = float(os.getenv("OPC_TIMEOUT_SEC", "5"))
    
    # Node ID mapping - UPDATE THESE TO MATCH YOUR PLC
    nodeids = {
        # State variables (this program publishes these)
        "inspection_id": "ns=6;i=1",
        "photo_step_done": "ns=6;i=2",
        "results_version": "ns=6;i=3",
        "c1_recorrect": "ns=6;i=4",
        "c2_recorrect": "ns=6;i=5",
        "c3_recorrect": "ns=6;i=6",
        "c4_recorrect": "ns=6;i=7",
        
        # Control variables (this program reads these)
        "mm_received_instruction": "ns=6;i=20",
        "photo_ready_step": "ns=6;i=21",
    }
    
    print(f"Connecting to OPC UA server at {url}...")
    
    max_retries = 5
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            async with Client(url=url, timeout=request_timeout) as client:
                print("✓ Connected to OPC UA server")
                
                # Set authentication if provided
                if ua_user and ua_pass:
                    await client.set_user(ua_user)
                    await client.set_password(ua_pass)
                    print("✓ Authentication configured")
                
                # Get node references
                nodes = {k: client.get_node(v) for k, v in nodeids.items()}
                print("✓ Node references obtained")
                
                # Run the inspection loop
                await inspection_loop(gui_bridge, nodes)
                
                break  # If we get here, connection was successful
                
        except asyncio.CancelledError:
            print("[SHUTDOWN] OPC UA connection closing...")
            raise
        except Exception as e:
            print(f"[ERROR] Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print("✗ Failed to connect after maximum retries")
                raise


def main():
    """
    Entry point for the camera inspection program.
    
    Sets up:
    - Qt application (for GUI)
    - Async event loop (for OPC UA)
    - Threading coordination
    """
    print("=== Camera Inspection System ===")
    print("OPC UA Client with GUI Integration")
    print(f"Target: {os.getenv('OPC_URL', 'opc.tcp://192.168.0.1:4840')}\n")
    
    # Create Qt application (must be in main thread)
    app = QApplication(sys.argv)
    
    # Create GUI bridge for async/Qt coordination
    gui_bridge = GUIBridge(app)
    
    # Create async event loop
    loop = asyncio.new_event_loop()
    
    def run_async_loop():
        """Run async OPC UA code in background thread"""
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(opc_ua_main(gui_bridge))
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Keyboard interrupt received")
        except Exception as e:
            print(f"\n[FATAL ERROR] {e}")
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
        print("\n=== SHUTDOWN COMPLETE ===")
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
