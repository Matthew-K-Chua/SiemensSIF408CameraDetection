#!/usr/bin/env python3
"""
Camera Inspection Modbus TCP Server - Hybrid Version

Workflow:
1. First view (photo_ready_step=1): Capture front photo, wait, mark done
2. Second view (photo_ready_step=2): Capture back photo, wait
3. Process all 4 containers using both photos
4. Commit all results atomically

CONFIGURATION:
    GUI_ENABLED: Set to True for manual GUI inspection, False for automated CV
    USE_PI_CAMERA: Set to True to capture from Pi camera, False to use file paths
    IMAGE_FRONT_PATH: Path to front camera image (if USE_PI_CAMERA=False)
    IMAGE_BACK_PATH: Path to back camera image (if USE_PI_CAMERA=False)
"""
import logging
import threading
import time
import sys
import os
from datetime import datetime
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSlaveContext,
    ModbusServerContext,
    ModbusSequentialDataBlock,
)

# Connection logging for Modbus (uncomment for debugging)
# logging.basicConfig(level=logging.DEBUG)


# Configuration
GUI_ENABLED = False
USE_PI_CAMERA = True

# Paths for file-based mode
IMAGE_FRONT_PATH = r'C:\Users\mattk\Downloads\rightTilt.jpg'
IMAGE_BACK_PATH = r'C:\Users\mattk\Downloads\rightTilt.jpg'

# Crop regions for automated detection (optional)
CROP_REGIONS_FRONT = None
CROP_REGIONS_BACK = None

# Import based on mode
if GUI_ENABLED:
    from PySide6.QtWidgets import QApplication
    from inspection_gui import process_containers_gui
    print("[CONFIG] GUI mode enabled")
else:
    from imgDetection import process_containers_automated
    print("[CONFIG] Automated mode enabled")

if USE_PI_CAMERA:
    try:
        from picamera2 import Picamera2
        import tempfile
        print("[CONFIG] Pi Camera enabled")
    except ImportError:
        print("[CONFIG] WARNING: picamera2 not found. Set USE_PI_CAMERA=False")
        USE_PI_CAMERA = False

# Robot writes to holding registers
MM_RECEIVED_INSTRUCTION_ADDR = 135
PHOTO_READY_STEP_ADDR        = 136

# Server writes to input registers
INSPECTION_ID_ADDR           = 128
PHOTO_STEP_DONE_ADDR         = 129
RESULTS_VERSION_ADDR         = 130
C1_RECORRECT_ADDR            = 131
C2_RECORRECT_ADDR            = 132
C3_RECORRECT_ADDR            = 133
C4_RECORRECT_ADDR            = 134

# Create data store
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 200),
    ir=ModbusSequentialDataBlock(0, [0] * 200),
    di=ModbusSequentialDataBlock(0, [0] * 200),
    co=ModbusSequentialDataBlock(0, [0] * 200),
)
context = ModbusServerContext(slaves=store, single=True)

# Thread safety lock for Modbus context access
context_lock = threading.Lock()

SAVE_IMAGES_DIR = '/home/admin/Desktop/mm/SiemensSIF408CameraDetection/Test/imgs'
if not os.path.exists(SAVE_IMAGES_DIR):
    os.makedirs(SAVE_IMAGES_DIR)

def _hr_get(addr: int, count: int = 1):
    """Read from holding registers (thread-safe)"""
    slave_id = 0x00
    with context_lock:
        return context[slave_id].getValues(3, addr, count=count)


def _hr_set(addr: int, values):
    """Write to holding registers (thread-safe)"""
    slave_id = 0x00
    with context_lock:
        context[slave_id].setValues(3, addr, values)


def _ir_set(addr: int, values):
    """Write to input registers (thread-safe)"""
    slave_id = 0x00
    with context_lock:
        context[slave_id].setValues(4, addr, values)


def read_mm_received_instruction() -> int:
    return _hr_get(MM_RECEIVED_INSTRUCTION_ADDR, 1)[0]


def read_photo_ready_step() -> int:
    return _hr_get(PHOTO_READY_STEP_ADDR, 1)[0]


def publish_inspection_state(
    inspection_id: int,
    photo_step_done: int,
    results_version: int,
    c1: bool,
    c2: bool,
    c3: bool,
    c4: bool,
):
    """Publish current inspection state to robot via input registers"""
    _ir_set(INSPECTION_ID_ADDR, [inspection_id])
    _ir_set(PHOTO_STEP_DONE_ADDR, [photo_step_done])
    _ir_set(C1_RECORRECT_ADDR, [1 if c1 else 0])
    _ir_set(C2_RECORRECT_ADDR, [1 if c2 else 0])
    _ir_set(C3_RECORRECT_ADDR, [1 if c3 else 0])
    _ir_set(C4_RECORRECT_ADDR, [1 if c4 else 0])
    _ir_set(RESULTS_VERSION_ADDR, [results_version])


def take_photo_async(view_name, inspection_id):
    """
    Capture photo in separate thread to avoid blocking Modbus loop.
    Returns future-like object.
    """
    result = {'path': None, 'done': False}
    
    def capture():
        if USE_PI_CAMERA:
            print(f"[CAMERA] Capturing {view_name} from Pi camera...")
            camera = Picamera2()
            camera.start()
            time.sleep(2)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'inspection_{inspection_id}_{view_name.lower().replace(" ", "_")}_{timestamp}.jpg'
            
            # Construct save path
            save_dir = os.path.join(os.path.dirname(__file__), 'imgs')
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            save_path = os.path.join(save_dir, filename)
            camera.capture_file(save_path)
            camera.stop()
            
            print(f"[CAMERA] Saved to: {save_path}")
            result['path'] = save_path
        else:
            result['path'] = IMAGE_FRONT_PATH if view_name == "First View" else IMAGE_BACK_PATH
        
        result['done'] = True
    
    thread = threading.Thread(target=capture, daemon=True)
    thread.start()
    return result


def process_all_containers(front_image_path, back_image_path):
    """
    Process all 4 containers using both images.
    
    Args:
        front_image_path: Path to first view image (shows C3, C4)
        back_image_path: Path to second view image (shows C2, C1)
    
    Returns:
        tuple: (c1, c2, c3, c4) as booleans
    """
    if GUI_ENABLED:
        print("[INSPECTION] Launching GUI for all containers...")
        results = process_containers_gui(
            active_containers=[1, 2, 3, 4],
            view_name="All Containers"
        )
        c1 = results['c1_recorrect'] if results['c1_recorrect'] is not None else False
        c2 = results['c2_recorrect'] if results['c2_recorrect'] is not None else False
        c3 = results['c3_recorrect'] if results['c3_recorrect'] is not None else False
        c4 = results['c4_recorrect'] if results['c4_recorrect'] is not None else False
        return c1, c2, c3, c4
    else:
        print("[INSPECTION] Running automated detection...")
        
        # Process front image for C3, C4
        front_results = process_containers_automated(
            image_path=front_image_path,
            active_canisters=[3, 4],
            crop_regions=CROP_REGIONS_FRONT,
            camera_side='front',
            save_debug=True
        )
        
        # Process back image for C2, C1
        back_results = process_containers_automated(
            image_path=back_image_path,
            active_canisters=[2, 1],
            crop_regions=CROP_REGIONS_BACK,
            camera_side='back',
            save_debug=True
        )
        
        # Combine results
        c1 = back_results['c1_recorrect'] if back_results['c1_recorrect'] is not None else False
        c2 = back_results['c2_recorrect'] if back_results['c2_recorrect'] is not None else False
        c3 = front_results['c3_recorrect'] if front_results['c3_recorrect'] is not None else False
        c4 = front_results['c4_recorrect'] if front_results['c4_recorrect'] is not None else False
        
        return c1, c2, c3, c4


def inspection_loop():
    """
    Main inspection loop with non-blocking camera capture.
    Runs at 10 Hz to maintain Modbus communication.
    """
    inspection_id = 0
    photo_step_done = 0
    results_version = 0
    c1_recorrect = False
    c2_recorrect = False
    c3_recorrect = False
    c4_recorrect = False
    
    # Store image paths and capture states
    front_image_path = None
    back_image_path = None
    front_capture = None
    back_capture = None

    print("[CAMERA] Inspection loop started")
    print(f"[CAMERA] Mode: {'GUI' if GUI_ENABLED else 'Automated CV'}")
    print(f"[CAMERA] Camera: {'Pi Camera' if USE_PI_CAMERA else 'File-based'}")

    while True:
        # Continuous publish at 10 Hz to keep Modbus alive
        publish_inspection_state(
            inspection_id,
            photo_step_done,
            results_version,
            c1_recorrect,
            c2_recorrect,
            c3_recorrect,
            c4_recorrect,
        )

        # Start new inspection
        if read_mm_received_instruction() == 1:
            inspection_id += 1
            photo_step_done = 0
            front_image_path = None
            back_image_path = None
            front_capture = None
            back_capture = None
            print(f"\n[CAMERA] New inspection requested. ID = {inspection_id}\n")
            
            # Clear trigger (using holding register set)
            # _hr_set(MM_RECEIVED_INSTRUCTION_ADDR, [0])
            
        # First view: Start capturing front photo (non-blocking)
        photo_ready_step = read_photo_ready_step()
        if photo_ready_step == 1 and photo_step_done == 0 and front_capture is None:
            print("[CAMERA] First view ready, starting front photo capture...")
            print("[CAMERA] This photo shows: C3 (left), C4 (right)")
            
            # Start async capture (no blocking sleep here)
            front_capture = take_photo_async("First View", inspection_id)
        
        # Check if front capture is complete
        if front_capture is not None and front_capture['done'] and photo_step_done == 0:
            front_image_path = front_capture['path']
            photo_step_done = 1
            
            publish_inspection_state(
                inspection_id,
                photo_step_done,
                results_version,
                c1_recorrect,
                c2_recorrect,
                c3_recorrect,
                c4_recorrect,
            )
            print("[CAMERA] First view complete")

        # Second view: Start capturing back photo (non-blocking)
        photo_ready_step = read_photo_ready_step()
        if photo_ready_step == 2 and photo_step_done == 1 and back_capture is None:
            print("[CAMERA] Second view ready, starting back photo capture...")
            print("[CAMERA] This photo shows: C2 (left), C1 (right)")
            
            # Start async capture (no blocking sleep here)
            back_capture = take_photo_async("Second View", inspection_id)
        
        # Re-read photo_ready_step before processing (matches user input file pattern)
        photo_ready_step = read_photo_ready_step()

        # Check if back capture is complete and robot is still in correct state, then process
        if (back_capture is not None and back_capture['done'] and 
            photo_step_done == 1 and photo_ready_step == 2):
            
            back_image_path = back_capture['path']
            
            # Process all 4 containers using both images
            print("[CAMERA] Processing all containers...")
            c1_recorrect, c2_recorrect, c3_recorrect, c4_recorrect = process_all_containers(
                front_image_path, 
                back_image_path
            )
            
            # Atomic commit: update state then bump version
            photo_step_done = 2
            results_version += 1
            
            publish_inspection_state(
                inspection_id,
                photo_step_done,
                results_version,
                c1_recorrect,
                c2_recorrect,
                c3_recorrect,
                c4_recorrect,
            )
            
            print(f"\n[CAMERA] Results committed (version {results_version}):")
            print(f"[CAMERA]   C1={c1_recorrect}, C2={c2_recorrect}")
            print(f"[CAMERA]   C3={c3_recorrect}, C4={c4_recorrect}\n")
            
            # Reset both capture objects for next inspection
            back_capture = None
            front_capture = None

        # 10 Hz loop rate to maintain responsive Modbus communication
        time.sleep(0.1)


def run_modbus_server():
    """Run Modbus TCP server (blocking)"""
    print("[MODBUS] Starting server on port 502")
    StartTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    if GUI_ENABLED:
        # GUI mode: Qt event loop in main thread
        app = QApplication(sys.argv)
        
        modbus_thread = threading.Thread(target=run_modbus_server, daemon=True)
        modbus_thread.start()
        
        logic_thread = threading.Thread(target=inspection_loop, daemon=True)
        logic_thread.start()
        
        print("[MAIN] GUI mode: Running Qt event loop")
        print("[MAIN] Press Ctrl+C to exit")
        
        try:
            sys.exit(app.exec())
        except KeyboardInterrupt:
            print("\n[MAIN] Shutting down...")
            sys.exit(0)
    
    else:
        # Automated mode: Modbus in main thread
        logic_thread = threading.Thread(target=inspection_loop, daemon=True)
        logic_thread.start()
        
        print("[MAIN] Automated mode: Running Modbus server")
        print("[MAIN] Press Ctrl+C to exit")
        
        try:
            run_modbus_server()
        except KeyboardInterrupt:
            print("\n[MAIN] Shutting down...")
            sys.exit(0)
