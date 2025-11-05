#!/usr/bin/env python3
"""
Camera Inspection Modbus TCP Server - Two-Stage Processing

Follows this workflow:
1. First view (photo_ready_step=1): Capture photo, process C1+C3
2. Second view (photo_ready_step=2): Capture photo, process C2+C4, commit all results

CONFIGURATION:
    GUI_ENABLED: Set to True for manual GUI inspection, False for automated CV
    USE_PI_CAMERA: Set to True to capture from Pi camera, False to use file paths
    IMAGE_FRONT_PATH: Path to front camera image (if USE_PI_CAMERA=False)
    IMAGE_BACK_PATH: Path to back camera image (if USE_PI_CAMERA=False)
"""

import threading
import time
import sys
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSlaveContext,
    ModbusServerContext,
    ModbusSequentialDataBlock,
)

# ============================================================================
# CONFIGURATION
# ============================================================================
GUI_ENABLED = False      # Set to True to use GUI, False for automated detection
USE_PI_CAMERA = False    # Set to True to capture from Pi camera

# Paths for file-based mode (when USE_PI_CAMERA=False)
IMAGE_FRONT_PATH = r'C:\Users\mattk\Downloads\rightTilt.jpg'
IMAGE_BACK_PATH = r'C:\Users\mattk\Downloads\rightTilt.jpg'

# Crop regions for automated detection (optional)
# Format: {canister_id: [y1, y2, x1, x2], ...}
CROP_REGIONS_FRONT = None  # None uses defaults - calibrate for your setup
CROP_REGIONS_BACK = None   # None uses defaults - calibrate for your setup

# ============================================================================
# IMPORTS BASED ON MODE
# ============================================================================
if GUI_ENABLED:
    from PySide6.QtWidgets import QApplication
    from inspection_gui import process_containers_gui
    print("[CONFIG] GUI mode enabled - using manual inspection")
else:
    from imgDetection import process_containers_automated
    print("[CONFIG] Automated mode enabled - using CV detection")

if USE_PI_CAMERA:
    try:
        from picamera2 import Picamera2
        import tempfile
        import os
        print("[CONFIG] Pi Camera enabled")
    except ImportError:
        print("[CONFIG] WARNING: picamera2 not found. Set USE_PI_CAMERA=False")
        USE_PI_CAMERA = False

# ---------------------------------------------------------------------------
# Modbus address map
# Robot -> server (we READ these from holding registers)
MM_RECEIVED_INSTRUCTION_ADDR = 120   # robot writes 1 to start new inspection
PHOTO_READY_STEP_ADDR = 121          # robot writes 1 or 2

# Server -> robot (we WRITE these to input registers so robot can read)
INSPECTION_ID_ADDR = 130
PHOTO_STEP_DONE_ADDR = 131
RESULTS_VERSION_ADDR = 132
C1_RECORRECT_ADDR = 133
C2_RECORRECT_ADDR = 134
C3_RECORRECT_ADDR = 135
C4_RECORRECT_ADDR = 136
# ---------------------------------------------------------------------------

# Create data store with enough space
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 200),  # holding registers 0..199
    ir=ModbusSequentialDataBlock(0, [0] * 200),  # input registers 0..199
    di=ModbusSequentialDataBlock(0, [0] * 200),
    co=ModbusSequentialDataBlock(0, [0] * 200),
)
context = ModbusServerContext(slaves=store, single=True)


# ---------------------------------------------------------------------------
# Helpers to read robot-driven values (holding registers, fc=3)
def _hr_get(addr: int, count: int = 1):
    slave_id = 0x00
    return context[slave_id].getValues(4, addr, count=count)


def read_mm_received_instruction() -> int:
    return _hr_get(MM_RECEIVED_INSTRUCTION_ADDR, 1)[0]


def read_photo_ready_step() -> int:
    return _hr_get(PHOTO_READY_STEP_ADDR, 1)[0]


# ---------------------------------------------------------------------------
# Helpers to publish to robot (input registers, fc=4)
def _ir_set(addr: int, values):
    slave_id = 0x00
    context[slave_id].setValues(4, addr, values)

def _hr_set(addr: int, values):
    """Write to holding registers"""
    slave_id = 0x00
    context[slave_id].setValues(4, addr, values)


def publish_inspection_state(
    inspection_id: int,
    photo_step_done: int,
    results_version: int,
    c1: bool,
    c2: bool,
    c3: bool,
    c4: bool,
):
    _ir_set(INSPECTION_ID_ADDR, [inspection_id])
    _ir_set(PHOTO_STEP_DONE_ADDR, [photo_step_done])
    _ir_set(RESULTS_VERSION_ADDR, [results_version])
    _ir_set(C1_RECORRECT_ADDR, [1 if c1 else 0])
    _ir_set(C2_RECORRECT_ADDR, [1 if c2 else 0])
    _ir_set(C3_RECORRECT_ADDR, [1 if c3 else 0])
    _ir_set(C4_RECORRECT_ADDR, [1 if c4 else 0])


# ---------------------------------------------------------------------------
# Camera Functions
def take_photo(view_name):
    """
    Capture photo from camera.
    Returns path to saved image.
    """
    if USE_PI_CAMERA:
        print(f"[CAMERA] Capturing {view_name} from Pi camera...")
        camera = Picamera2()
        camera.start()
        
        # Create temporary file
        temp_path = os.path.join(tempfile.gettempdir(), f'{view_name.lower().replace(" ", "_")}.jpg')
        camera.capture_file(temp_path)
        camera.stop()
        
        print(f"[CAMERA] Saved to: {temp_path}")
        return temp_path
    else:
        # Use pre-configured file paths
        if view_name == "First View":
            path = IMAGE_FRONT_PATH
        else:
            path = IMAGE_BACK_PATH
        print(f"[CAMERA] Using {view_name} image: {path}")
        return path


def process_containers_view(active_canisters, view_name, image_path, camera_side):
    """
    Process specific containers for one view.
    
    Args:
        active_canisters: List of canister IDs to process
        view_name: Display name for this view
        image_path: Path to captured image
        camera_side: 'front' or 'back'
    
    Returns:
        dict: {'c1_recorrect': bool/None, 'c2_recorrect': bool/None, ...}
    """
    if GUI_ENABLED:
        print(f"[INSPECTION] Launching GUI for {view_name}...")
        return process_containers_gui(
            active_containers=active_canisters,
            view_name=view_name
        )
    else:
        print(f"[INSPECTION] Running automated detection for {view_name}...")
        crop_regions = CROP_REGIONS_FRONT if camera_side == 'front' else CROP_REGIONS_BACK
        return process_containers_automated(
            image_path=image_path,
            active_canisters=active_canisters,
            crop_regions=crop_regions,
            camera_side=camera_side
        )


# ---------------------------------------------------------------------------
def inspection_loop():
    """
    Main inspection loop following the two-stage pseudocode.
    
    Stage 1: photo_ready_step=1 → Process C1, C3
    Stage 2: photo_ready_step=2 → Process C2, C4 → Commit all results atomically
    """
    inspection_id = 0
    photo_step_done = 0   # 0 none, 1 first view, 2 second view
    results_version = 0
    
    # Published correction flags
    c1_recorrect = False
    c2_recorrect = False
    c3_recorrect = False
    c4_recorrect = False
    
    # Temporary storage for first view results (not published yet)
    temp_c1 = False
    temp_c3 = False

    print("[CAMERA] Inspection loop started.")
    print(f"[CAMERA] Mode: {'GUI' if GUI_ENABLED else 'Automated CV'}")
    print(f"[CAMERA] Camera: {'Pi Camera' if USE_PI_CAMERA else 'File-based'}")

    while True:
        # ---- CONTINUOUS PUBLISH ----
        publish_inspection_state(
            inspection_id,
            photo_step_done,
            results_version,
            c1_recorrect,
            c2_recorrect,
            c3_recorrect,
            c4_recorrect,
        )

        # Print current register values
        mm_rcvd = read_mm_received_instruction()
        photo_step = read_photo_ready_step()
        print(f"[DEBUG] mm_received_instruction={mm_rcvd}, photo_ready_step={photo_step}")

        # ---- START NEW INSPECTION ----
        if read_mm_received_instruction() == 1:
            inspection_id += 1
            photo_step_done = 0
            # Keep previous cX_recorrect values published until new commit
            print(f"\n[CAMERA] ═══════════════════════════════════════")
            print(f"[CAMERA] New inspection requested. ID = {inspection_id}")
            print(f"[CAMERA] ═══════════════════════════════════════\n")

            # Clear the trigger
            _hr_set(MM_RECEIVED_INSTRUCTION_ADDR, [0])

        # ---- FIRST VIEW: Process C1, C3 ----
        photo_ready_step = read_photo_ready_step()
        if photo_ready_step == 1 and photo_step_done == 0:
            print("[CAMERA] ─── FIRST VIEW ───")
            
            # Take photo
            photo_path = take_photo("First View")
            
            # Process C1 and C3
            results = process_containers_view(
                active_canisters=[1, 3],
                view_name="First View (C1, C3)",
                image_path=photo_path,
                camera_side='front'
            )
            
            # Store results temporarily (don't commit yet)
            temp_c1 = results['c1_recorrect'] if results['c1_recorrect'] is not None else False
            temp_c3 = results['c3_recorrect'] if results['c3_recorrect'] is not None else False
            
            print(f"[CAMERA] First view complete: C1={temp_c1}, C3={temp_c3} (stored, not committed)")
            
            # Mark first view done
            photo_step_done = 1
            
            # Publish updated photo_step_done (but not results yet)
            publish_inspection_state(
                inspection_id,
                photo_step_done,
                results_version,
                c1_recorrect,
                c2_recorrect,
                c3_recorrect,
                c4_recorrect,
            )

        # ---- SECOND VIEW: Process C2, C4 + ATOMIC COMMIT ----
        photo_ready_step = read_photo_ready_step()  # re-read in case it changed
        if photo_ready_step == 2 and photo_step_done == 1:
            print("[CAMERA] ─── SECOND VIEW ───")
            
            # Take photo
            photo_path = take_photo("Second View")
            
            # Process C2 and C4
            results = process_containers_view(
                active_canisters=[2, 4],
                view_name="Second View (C2, C4)",
                image_path=photo_path,
                camera_side='back'
            )
            
            # Get C2, C4 results
            new_c2 = results['c2_recorrect'] if results['c2_recorrect'] is not None else False
            new_c4 = results['c4_recorrect'] if results['c4_recorrect'] is not None else False
            
            print(f"[CAMERA] Second view complete: C2={new_c2}, C4={new_c4}")
            
            # ---- ATOMIC COMMIT: Combine all results ----
            # Use stored values from first view + new values from second view
            c1_recorrect = temp_c1
            c2_recorrect = new_c2
            c3_recorrect = temp_c3
            c4_recorrect = new_c4
            
            # Bump version to signal commit
            results_version += 1
            photo_step_done = 2
            
            # Publish everything atomically
            publish_inspection_state(
                inspection_id,
                photo_step_done,
                results_version,
                c1_recorrect,
                c2_recorrect,
                c3_recorrect,
                c4_recorrect,
            )
            
            print(f"\n[CAMERA] ✓ Results COMMITTED (version {results_version}):")
            print(f"[CAMERA]     C1 := {c1_recorrect}")
            print(f"[CAMERA]     C2 := {c2_recorrect}")
            print(f"[CAMERA]     C3 := {c3_recorrect}")
            print(f"[CAMERA]     C4 := {c4_recorrect}")
            print(f"[CAMERA] ═══════════════════════════════════════\n")

        # 10 Hz publish rate
        time.sleep(0.1)


# ---------------------------------------------------------------------------
def run_modbus_server():
    """Run the Modbus TCP server (blocking)"""
    print("[MODBUS] Starting server on port 502")
    StartTcpServer(context=context, address=("0.0.0.0", 502))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if GUI_ENABLED:
        # GUI mode: Need Qt event loop in main thread
        app = QApplication(sys.argv)
        
        # Start Modbus in a thread
        modbus_thread = threading.Thread(target=run_modbus_server, daemon=True)
        modbus_thread.start()
        
        # Start inspection loop in a thread
        logic_thread = threading.Thread(target=inspection_loop, daemon=True)
        logic_thread.start()
        
        print("[MAIN] GUI mode: Running Qt event loop in main thread")
        print("[MAIN] Press Ctrl+C to exit")
        
        # Run Qt event loop in main thread
        try:
            sys.exit(app.exec())
        except KeyboardInterrupt:
            print("\n[MAIN] Shutting down...")
            sys.exit(0)
    
    else:
        # Automated mode: Modbus in main thread
        logic_thread = threading.Thread(target=inspection_loop, daemon=True)
        logic_thread.start()
        
        print("[MAIN] Automated mode: Running Modbus server in main thread")
        print("[MAIN] Press Ctrl+C to exit")
        
        # Start Modbus TCP server (blocks main thread)
        try:
            run_modbus_server()
        except KeyboardInterrupt:
            print("\n[MAIN] Shutting down...")
            sys.exit(0)