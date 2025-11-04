#!/usr/bin/env python3
"""
camera_inspection_main.py

Modbus TCP client for the camera inspection system.
Handles communication with the UR3 controller and coordinates with the inspection GUI.
"""

import sys
import os
import threading
import asyncio
from dataclasses import dataclass
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

from inspection_gui import InspectionGUI


# ============================================================================
# MODBUS REGISTER MAPPING FOR UR3
# ============================================================================
# UR robots use specific Modbus register ranges:
# - Standard registers: 0-255 (reserved by UR)
# - User general purpose integer registers: 128-255 (function code 3/6/16)
# - Digital outputs (coils): 0-7 are standard outputs, 128-255 are general purpose
#
# For this application, we use general purpose registers to avoid conflicts
# ============================================================================

MODBUS_MAP = {
    # Integer values - using general purpose holding registers (start at 128+)
    # Note: pymodbus uses 0-based addressing internally
    "inspection_id": 127,      # General purpose register 0 (UR address 128)
    "photo_step_done": 128,    # General purpose register 1 (UR address 129)
    "results_version": 139,    # General purpose register 2 (UR address 130)
    
    # Boolean values - using general purpose digital outputs (128+)
    # These map to digital outputs in UR
    "c1_recorrect": 130,       # General purpose digital output 0
    "c2_recorrect": 131,       # General purpose digital output 1
    "c3_recorrect": 132,       # General purpose digital output 2
    "c4_recorrect": 133,       # General purpose digital output 3

    "mm_received_instruction": 134,  # General purpose digital output 4 (trigger)
    "photo_ready_step": 135,   # General purpose register 3 (UR address 131)5
}


class GUIBridge(QObject):
    """
    Thread-safe bridge between asyncio and the Qt GUI.

    Manages launching the GUI from asynchronous code and waiting for user input.
    """

    show_gui_signal = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.gui = None
        self.gui_future = None
        self.show_gui_signal.connect(self._show_gui_slot)

    def _show_gui_slot(self):
        """Displays the GUI in the main Qt thread."""
        if self.gui is None or not self.gui.isVisible():
            self.gui = InspectionGUI()
            self.gui.submission_complete.connect(self._on_submission)
            self.gui.show()

    def _on_submission(self, results):
        """Handles user submission from the GUI."""
        if self.gui_future and not self.gui_future.done():
            self.gui_future.set_result(results)

    async def get_inspection_results(self):
        """
        Displays the GUI and waits for user input asynchronously.

        Returns:
            dict: {'c1_recorrect': bool, 'c2_recorrect': bool, ...}
        """
        loop = asyncio.get_event_loop()
        self.gui_future = loop.create_future()
        self.show_gui_signal.emit()
        results = await self.gui_future
        return results


@dataclass
class InspectionState:
    """
    Internal state for the camera inspection workflow.

    Attributes:
        inspection_id: Increments for each new inspection.
        photo_step_done: 0 = none, 1 = first view complete, 2 = second view complete.
        results_version: Increments on each commit of new results.
        c1_recorrect–c4_recorrect: Booleans indicating whether each container needs correction.
    """
    inspection_id: int = 0
    photo_step_done: int = 0
    results_version: int = 0
    c1_recorrect: bool = False
    c2_recorrect: bool = False
    c3_recorrect: bool = False
    c4_recorrect: bool = False


async def publish_state(client: ModbusTcpClient, state: InspectionState):
    """
    Writes the current inspection state to the Modbus server.
    
    Args:
        client: ModbusTcpClient instance
        state: Current InspectionState
        
    Note: UR robots expect 16-bit integers (0-65535) for holding registers
    """
    try:
        # Write integer values to holding registers
        # Using asyncio.to_thread to prevent blocking the event loop
        result = await asyncio.to_thread(
            client.write_register, 
            MODBUS_MAP["inspection_id"], 
            state.inspection_id
        )
        if result.isError():
            print(f"[WARN] Failed to write inspection_id: {result}")
            
        result = await asyncio.to_thread(
            client.write_register, 
            MODBUS_MAP["photo_step_done"], 
            state.photo_step_done
        )
        if result.isError():
            print(f"[WARN] Failed to write photo_step_done: {result}")
            
        result = await asyncio.to_thread(
            client.write_register, 
            MODBUS_MAP["results_version"], 
            state.results_version
        )
        if result.isError():
            print(f"[WARN] Failed to write results_version: {result}")

        # Write boolean values to coils (digital outputs)
        result = await asyncio.to_thread(
            client.write_coil, 
            MODBUS_MAP["c1_recorrect"], 
            state.c1_recorrect
        )
        if result.isError():
            print(f"[WARN] Failed to write c1_recorrect: {result}")
            
        result = await asyncio.to_thread(
            client.write_coil, 
            MODBUS_MAP["c2_recorrect"], 
            state.c2_recorrect
        )
        if result.isError():
            print(f"[WARN] Failed to write c2_recorrect: {result}")
            
        result = await asyncio.to_thread(
            client.write_coil, 
            MODBUS_MAP["c3_recorrect"], 
            state.c3_recorrect
        )
        if result.isError():
            print(f"[WARN] Failed to write c3_recorrect: {result}")
            
        result = await asyncio.to_thread(
            client.write_coil, 
            MODBUS_MAP["c4_recorrect"], 
            state.c4_recorrect
        )
        if result.isError():
            print(f"[WARN] Failed to write c4_recorrect: {result}")
            
    except ModbusException as e:
        print(f"[ERROR] Modbus exception while publishing state: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to publish Modbus state: {e}")


async def inspection_loop(gui_bridge: GUIBridge, client: ModbusTcpClient):
    """
    Main inspection loop controlling workflow and communication.

    Implements:
    - Continuous publishing of state (10 Hz)
    - Triggering new inspections
    - Launching the GUI for manual input
    - Committing inspection results atomically
    
    Args:
        gui_bridge: GUIBridge for showing inspection GUI
        client: ModbusTcpClient for UR3 communication
    """
    state = InspectionState()

    print("\n=== CAMERA INSPECTION STARTED ===")
    print("Waiting for inspection triggers from UR3 controller...")
    print("(Test mode: auto-triggering enabled)\n")

    # For testing without UR3 triggers
    simulated_photo_ready_step = 2
    simulated_mm_received = False
    test_mode = True  # Set to False when connected to real UR3

    while True:
        try:
            # ---- CONTINUOUS PUBLISH (10 Hz) ----
            await publish_state(client, state)

            # ---- START NEW INSPECTION ----
            # Read the inspection trigger from UR3
            if not test_mode:
                try:
                    result = await asyncio.to_thread(
                        client.read_coils, 
                        MODBUS_MAP["mm_received_instruction"], 
                        1
                    )
                    mm_received = result.bits[0] if not result.isError() else False
                except Exception as e:
                    print(f"[WARN] Failed to read mm_received_instruction: {e}")
                    mm_received = False
            else:
                mm_received = simulated_mm_received

            if mm_received:
                state.inspection_id += 1
                state.photo_step_done = 0
                print(f"\n[NEW INSPECTION] ID: {state.inspection_id}")
                # Keep previous results published until new results commit

            # ---- FIRST VIEW (optional, currently skipped) ----
            # Could be implemented here if needed for the workflow

            # ---- SECOND VIEW + ATOMIC COMMIT ----
            # Read the current photo step from UR3
            if not test_mode:
                try:
                    result = await asyncio.to_thread(
                        client.read_holding_registers, 
                        MODBUS_MAP["photo_ready_step"], 
                        1
                    )
                    photo_ready = result.registers[0] if not result.isError() else 0
                except Exception as e:
                    print(f"[WARN] Failed to read photo_ready_step: {e}")
                    photo_ready = 0
            else:
                photo_ready = simulated_photo_ready_step

            # Launch GUI when ready for second view
            if photo_ready == 2 and state.photo_step_done == 1:
                print("\n[SECOND VIEW] Launching inspection GUI...")
                
                # Get results from user via GUI (blocks until user submits)
                results = await gui_bridge.get_inspection_results()

                # Compute fresh booleans locally (no publishing yet)
                new_c1 = results["c1_recorrect"]
                new_c2 = results["c2_recorrect"]
                new_c3 = results["c3_recorrect"]
                new_c4 = results["c4_recorrect"]

                # Write all correction flags
                state.c1_recorrect = new_c1
                state.c2_recorrect = new_c2
                state.c3_recorrect = new_c3
                state.c4_recorrect = new_c4
                state.results_version += 1
                state.photo_step_done = 2

                print(f"[COMMIT] Results version {state.results_version} published to UR3")
                print(f"  Inspection ID: {state.inspection_id}")
                print(f"  Corrections: C1={new_c1}, C2={new_c2}, C3={new_c3}, C4={new_c4}\n")

                # For testing: trigger another inspection cycle after delay
                if test_mode:
                    await asyncio.sleep(2)
                    state.photo_step_done = 1  # Reset to trigger another GUI launch

            # Wait 100ms between cycles (10 Hz publish rate)
            await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            print("\n[SHUTDOWN] Inspection loop cancelled")
            raise
        except Exception as e:
            print(f"[ERROR] Loop iteration failed: {e}")
            await asyncio.sleep(1.0)


async def modbus_main(gui_bridge: GUIBridge):
    """
    Initialises and manages the Modbus TCP connection to UR3.
    
    Args:
        gui_bridge: GUIBridge instance for GUI coordination
    """
    # Configuration from environment variables
    robot_ip = os.getenv("UR3_IP", "130.130.130.86")  # Default UR3 IP
    robot_port = int(os.getenv("UR3_MODBUS_PORT", "502"))  # Standard Modbus port
    
    print(f"Connecting to UR3 at {robot_ip}:{robot_port}...")
    
    # Create Modbus TCP client
    # Note: pymodbus v3.x syntax
    client = ModbusTcpClient(
        host=robot_ip,
        port=robot_port,
        timeout=3,  # 3 second timeout
        retries=3,
        retry_on_empty=True
    )

    # Attempt connection
    max_retries = 5
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            if client.connect():
                print(" Connected to UR3 Modbus server")
                break
            else:
                print(f" Connection attempt {attempt + 1} failed")
                if attempt < max_retries - 1:
                    print(f"  Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
        except Exception as e:
            print(f" Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
    else:
        raise ConnectionError(f"Failed to connect to UR3 after {max_retries} attempts")

    try:
        # Run the main inspection loop
        await inspection_loop(gui_bridge, client)
    except Exception as e:
        print(f"[ERROR] Inspection loop failed: {e}")
        raise
    finally:
        client.close()
        print("[SHUTDOWN] Modbus connection closed")


def main():
    """
    Entry point for the camera inspection system.

    Initialises:
    - The Qt application for the GUI
    - The asynchronous event loop for Modbus communication
    - Threading coordination between the two
    """
    print("=== Camera Inspection System ===")
    print("Modbus TCP Client with GUI Integration")
    print(f"Target: {os.getenv('UR3_IP', '192.168.1.10')}:{os.getenv('UR3_MODBUS_PORT', '502')}\n")

    # Create Qt application (must be in main thread)
    app = QApplication(sys.argv)
    
    # Create GUI bridge for async/Qt coordination
    gui_bridge = GUIBridge(app)
    
    # Create async event loop
    loop = asyncio.new_event_loop()

    def run_async_loop():
        """Runs the asynchronous Modbus code in a background thread."""
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(modbus_main(gui_bridge))
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
