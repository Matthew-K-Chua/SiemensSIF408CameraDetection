#!/usr/bin/env python3
"""
Camera Inspection Modbus TCP Server (UR3-synced)

This version aligns 1:1 with the UR script `MM_SIF408_Camera.script`:

UR modbus_add_signal map (slave/unit-id = 255):

  Input Registers (IR, read by robot; written by this server)
    128 -> mm_insp_id        (monotonic inspection id)
    129 -> mm_pht_stp_done   (0 none, 1 = first view captured, 2 = both views processed)
    130 -> mm_res_ver        (results version, increment on each commit)
    131 -> c1_recorrect      (0/1)
    132 -> c2_recorrect      (0/1)
    133 -> c3_reconnect      (0/1)  [name typo in UR script, still a boolean flag]
    134 -> c4_reconnect      (0/1)

  Holding Registers (HR, written by robot; read by this server)
    135 -> mm_recv_inst      (robot pulses 1 to request a new inspection; robot later clears to 0)
    136 -> mm_pht_rdy_stp    (1 = First View requested, 2 = Second View requested)

Handshake expected by UR program (excerpt):
  - Robot sets HR136 = 1, then WAITS until IR129 == 1
  - Robot sets HR136 = 2, then WAITS until IR129 == 2, then sets HR136 = 0

This server:
  - Detects a rising edge on HR135 to start a new inspection (increments IR128)
  - When HR136=1, captures First View; on completion sets IR129=1
  - When HR136=2, captures Second View, runs CV, publishes c1..c4, bumps IR130, and sets IR129=2

Also:
  - Responds to unit-id 255 explicitly (and 0/1) so "requested slave does not exist: 255" never happens.
  - Uses a single Picamera2 instance across captures (if available).
  - Thread-safe access to the Modbus datastore.
"""

import os
import sys
import time
import logging
import threading
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, Any

# ---------------------------- Configuration ---------------------------------

GUI_ENABLED = False
USE_PI_CAMERA = os.getenv("USE_PI_CAMERA", "1") not in ("0", "false", "False")
SAVE_DIR = os.getenv("SAVE_DIR", "imgs")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Fallback image files if Pi Camera is disabled/unavailable
IMAGE_FRONT_PATH = os.getenv("IMAGE_FRONT_PATH", "sample_front.jpg")
IMAGE_BACK_PATH  = os.getenv("IMAGE_BACK_PATH",  "sample_back.jpg")

# ---------------------------- Camera setup ----------------------------------

camera = None
if USE_PI_CAMERA:
    try:
        from picamera2 import Picamera2
        print("[CONFIG] Pi Camera enabled")
        camera = Picamera2()
        camera.start()
    except Exception as e:
        print(f"[CONFIG] WARNING: Pi Camera unavailable ({e}). Using file paths.")
        USE_PI_CAMERA = False
else:
    print("[CONFIG] Pi Camera disabled (USE_PI_CAMERA=0)")

# ---------------------------- Modbus setup ----------------------------------

# Addressing exactly as in the UR script
INSPECTION_ID_ADDR   = 128  # IR
PHOTO_STEP_DONE_ADDR = 129  # IR
RESULTS_VERSION_ADDR = 130  # IR
C1_RECORRECT_ADDR    = 131  # IR
C2_RECORRECT_ADDR    = 132  # IR
C3_RECONNECT_ADDR    = 133  # IR  (UR name: c3_reconnect)
C4_RECONNECT_ADDR    = 134  # IR  (UR name: c4_reconnect)

MM_RECEIVED_INSTRUCTION_ADDR = 135  # HR
PHOTO_READY_STEP_ADDR        = 136  # HR

from pymodbus.datastore import (
    ModbusServerContext, ModbusSlaveContext, ModbusSequentialDataBlock
)

# Build a shared datastore (0..199 addresses is ample for this app)
_hr_block = ModbusSequentialDataBlock(0, [0]*200)
_ir_block = ModbusSequentialDataBlock(0, [0]*200)

# Create per-unit contexts that share the same underlying blocks
_ctx_unit = ModbusSlaveContext(hr=_hr_block, ir=_ir_block, di=None, co=None)
slaves = {
    0xFF: _ctx_unit,  # UR script uses unit-id 255
    0x01: _ctx_unit,  # common alternative
    0x00: _ctx_unit,  # catch-all
}
context = ModbusServerContext(slaves=slaves, single=False)

# Thread-safety for datastore access (server thread + logic thread)
_context_lock = threading.Lock()

def _hr_get(addr: int, count: int = 1):
    with _context_lock:
        # Access any mapped unit; blocks are shared
        return context[0xFF].getValues(3, addr, count=count)  # 3 = HR

def _hr_set(addr: int, values):
    with _context_lock:
        context[0xFF].setValues(3, addr, values)

def _ir_get(addr: int, count: int = 1):
    with _context_lock:
        return context[0xFF].getValues(4, addr, count=count)  # 4 = IR

def _ir_set(addr: int, values):
    with _context_lock:
        context[0xFF].setValues(4, addr, values)

# --------------------------- Utility: save path ------------------------------

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _photo_path(kind: str, inspection_id: int) -> str:
    _ensure_dir(SAVE_DIR)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"inspection_{inspection_id}_{kind}_{ts}.jpg"
    return os.path.join(SAVE_DIR, fname)

# --------------------------- Capture (async) ---------------------------------

def take_photo_async(kind: str, inspection_id: int) -> Dict[str, Any]:
    """
    Returns a dict filled by a background thread:
        {'path': str or None, 'done': bool}
    kind: "first" or "second"
    """
    result = {'path': None, 'done': False}

    def _capture():
        try:
            if USE_PI_CAMERA and camera is not None:
                save_path = _photo_path("first_view" if kind == "first" else "second_view", inspection_id)
                print(f"[CAMERA] Capturing {'First' if kind=='first' else 'Second'} View from Pi camera...")
                camera.capture_file(save_path)
                print(f"[CAMERA] Saved to: {save_path}")
                result['path'] = save_path
            else:
                result['path'] = IMAGE_FRONT_PATH if kind == "first" else IMAGE_BACK_PATH
            result['done'] = True
        except Exception as e:
            print(f"[CAMERA] ERROR during capture: {e}")
            result['done'] = True
            result['path'] = None

    t = threading.Thread(target=_capture, daemon=True)
    t.start()
    return result

# --------------------------- Processing hook ---------------------------------
# Integrated from imgDetection.py

def detect_canister_level(canister_img, canister_id, angle_tolerance=2.0,
                          save_debug=False, debug_path=None):
    """
    Detect if a canister is level by analysing the top horizontal line.
    Returns a status dict for that canister.
    """
    status = {
        'id': canister_id,
        'is_level': True,
        'angle': 0.0,
        'has_top_line': False,
        'is_curved': False
    }

    grey_image = cv2.cvtColor(canister_img, cv2.COLOR_BGR2GRAY)
    blur_image = cv2.medianBlur(grey_image, 11)
    canny_image = cv2.Canny(blur_image, 300, 400)

    lines = cv2.HoughLinesP(
        canny_image,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=40,
        maxLineGap=5
    )

    if lines is None:
        return status

    status['has_top_line'] = True

    horizontal_angles = []
    debug_img = canister_img.copy()

    for line in lines:
        x1, y1, x2, y2 = line[0]
        cv2.line(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)

        dx = x2 - x1
        dy = y2 - y1

        if dx == 0:
            continue

        angle = np.degrees(np.arctan2(dy, dx))

        # Only treat reasonably horizontal-ish segments
        if abs(angle) < 45:
            horizontal_angles.append(angle)

    # Save debug image if requested
    if save_debug and debug_path:
        cv2.imwrite(debug_path, debug_img)
        print(f"[AUTO DETECT] Debug image saved: {debug_path}")

    if not horizontal_angles:
        status['has_top_line'] = False
        return status

    angle_std = np.std(horizontal_angles)
    if angle_std > 5.0:
        # Lots of variation → likely curved
        status['is_curved'] = True
        status['is_level'] = False
        status['angle'] = float(np.mean(horizontal_angles))
    else:
        avg_angle = float(np.mean(horizontal_angles))
        status['angle'] = avg_angle
        status['is_level'] = abs(avg_angle) < angle_tolerance

    return status


def process_pallet(image, active_canisters, crop_regions=None,
                   camera_side='front', debug_dir=None):
    """
    Process specific canisters from a single camera view.
    Uses relative crop regions tuned for 4608x2592 reference images.
    Also saves cropped and line-detected images if debug_dir provided.
    """

    height, width = image.shape[:2]

    # Default crop regions if none passed
    if crop_regions is None:
        # Vertical band for all crops (middle section)
        y1 = int(height * 0.30)
        y2 = int(height * 0.55)

        # Horizontal positions
        left_x1, left_x2 = int(width * 0.24), int(width * 0.50)
        right_x1, right_x2 = int(width * 0.60), int(width * 0.85)

        if camera_side == 'front':
            # Front view shows: C3 (left), C4 (right)
            crop_regions = {
                3: [y1, y2, left_x1, left_x2],
                4: [y1, y2, right_x1, right_x2],
            }
        else:
            # Back view shows: C1 (left), C2 (right)
            crop_regions = {
                1: [y1, y2, left_x1, left_x2],
                2: [y1, y2, right_x1, right_x2],
            }

    canister_status = {}

    # Ensure debug directory exists
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    # NEW: Create full-image visualisations
    full_img_with_crops = image.copy()
    full_img_with_lines = image.copy()

    for canister_id in active_canisters:
        if canister_id not in crop_regions:
            print(f"[AUTO DETECT] Warning: No crop region defined for canister {canister_id}")
            continue

        y1, y2, x1, x2 = crop_regions[canister_id]
        canister_crop = image[y1:y2, x1:x2]

        # NEW: Draw crop region rectangle on full image
        if debug_dir:
            cv2.rectangle(full_img_with_crops, (x1, y1), (x2, y2), (0, 255, 0), 3)
            # Add label
            label = f"C{canister_id}"
            cv2.putText(full_img_with_crops, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

        # Prepare debug paths
        crop_path = None
        lines_path = None
        if debug_dir:
            crop_path = os.path.join(debug_dir, f"canister_{canister_id}_crop.jpg")
            lines_path = os.path.join(debug_dir, f"canister_{canister_id}_lines.jpg")

        # Save the cropped image before detection
        if crop_path:
            cv2.imwrite(crop_path, canister_crop)
            print(f"[AUTO DETECT] Saved cropped image: {crop_path}")

        # Run detection (and also save lines overlay)
        status = detect_canister_level(
            canister_crop,
            canister_id,
            save_debug=(debug_dir is not None),
            debug_path=lines_path
        )
        canister_status[canister_id] = status

        # NEW: Detect lines again and draw them on the full image
        if debug_dir and status['has_top_line']:
            grey_crop = cv2.cvtColor(canister_crop, cv2.COLOR_BGR2GRAY)
            blur_crop = cv2.medianBlur(grey_crop, 11)
            canny_crop = cv2.Canny(blur_crop, 30, 100)
            
            lines = cv2.HoughLinesP(
                canny_crop,
                rho=1,
                theta=np.pi / 180,
                threshold=30,
                minLineLength=40,
                maxLineGap=5
            )
            
            if lines is not None:
                for line in lines:
                    lx1, ly1, lx2, ly2 = line[0]
                    # Transform coordinates from crop space to full image space
                    full_x1 = lx1 + x1
                    full_y1 = ly1 + y1
                    full_x2 = lx2 + x1
                    full_y2 = ly2 + y1
                    
                    # Draw line on full image
                    cv2.line(full_img_with_lines, (full_x1, full_y1), 
                            (full_x2, full_y2), (0, 0, 255), 2)
            
            # Also draw the crop rectangle on the lines image
            cv2.rectangle(full_img_with_lines, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"C{canister_id}"
            cv2.putText(full_img_with_lines, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)

        level_str = "LEVEL" if status['is_level'] else "OFF KILTER"
        if status['has_top_line']:
            if status['is_curved']:
                print(f"[AUTO DETECT] Canister {canister_id}: {level_str} - CURVED")
            else:
                print(f"[AUTO DETECT] Canister {canister_id}: {level_str} - Angle: {status['angle']:.2f}°")
        else:
            print(f"[AUTO DETECT] Canister {canister_id}: No top line detected - assuming LEVEL")

    # NEW: Save the full-image visualisations
    if debug_dir:
        crop_viz_path = os.path.join(debug_dir, "full_image_with_crops.jpg")
        lines_viz_path = os.path.join(debug_dir, "full_image_with_lines.jpg")
        
        cv2.imwrite(crop_viz_path, full_img_with_crops)
        cv2.imwrite(lines_viz_path, full_img_with_lines)
        
        print(f"[AUTO DETECT] Saved full image with crop regions: {crop_viz_path}")
        print(f"[AUTO DETECT] Saved full image with detected lines: {lines_viz_path}")

    return canister_status

def get_recorrection_flags_from_dict(canister_status):
    """
    Convert canister status dict to recorrection flags.

    Returns:
        dict: {'c1_recorrect': bool/None, 'c2_recorrect': bool/None, ...}
              None indicates canister was not processed.
    """
    result = {
        'c1_recorrect': None,
        'c2_recorrect': None,
        'c3_recorrect': None,
        'c4_recorrect': None,
    }

    for canister_id, status in canister_status.items():
        key = f'c{canister_id}_recorrect'
        # True if NOT level (needs recorrection)
        result[key] = not status['is_level']

    return result


def process_containers_automated(image_path, active_canisters,
                                 crop_regions=None, camera_side='front',
                                 save_debug=False, debug_dir=None):
    """
    Automated container inspection for specific canisters.

    Args:
        image_path: Path to camera image
        active_canisters: List of canister IDs to process
        crop_regions: Optional custom crop regions
        camera_side: 'front' or 'back'
        save_debug: Whether to save debug images with line detection
        debug_dir: Optional directory to save debug images (crops + lines)

    Returns:
        dict: {'c1_recorrect': bool/None, ...}
    """
    canister_str = ", ".join([f"C{i}" for i in sorted(active_canisters)])
    print(f"\n[AUTO DETECT] Processing canisters: {canister_str}")
    print(f"[AUTO DETECT] Loading image: {image_path}")

    image = cv2.imread(image_path)

    if image is None:
        print(f"[AUTO DETECT] ERROR: Failed to load image. Defaulting all to OK.")
        return {
            'c1_recorrect': None,
            'c2_recorrect': None,
            'c3_recorrect': None,
            'c4_recorrect': None,
        }

    # Decide where to save debug images
    if save_debug:
        if debug_dir is None:
            # fall back to same folder as image
            debug_dir = os.path.dirname(image_path) or "."
    else:
        debug_dir = None

    canister_status = process_pallet(
        image,
        active_canisters,
        crop_regions=crop_regions,
        camera_side=camera_side,
        debug_dir=debug_dir,
    )

    result = get_recorrection_flags_from_dict(canister_status)

    print(f"[AUTO DETECT] Results: ", end="")
    for i in sorted(active_canisters):
        key = f'c{i}_recorrect'
        print(f"{key}={result[key]} ", end="")
    print("\n")

    return result

def process_two_views(front_path: str, back_path: str):
    """
    Process both camera views and return combined canister inspection results.
    
    Returns:
        dict: {'c1': int, 'c2': int, 'c3': int, 'c4': int}
              where 1 = needs recorrection, 0 = level/OK
    """
    base_dir = os.path.dirname(front_path) or "."
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_root = os.path.join(base_dir, f"debug_{ts}")

    front_debug_dir = os.path.join(debug_root, "front")
    back_debug_dir  = os.path.join(debug_root, "back")

    os.makedirs(front_debug_dir, exist_ok=True)
    os.makedirs(back_debug_dir, exist_ok=True)

    print(f"[AUTO DETECT] Debug output directory: {debug_root}")

    # Process front view (C3, C4)
    flags_front = process_containers_automated(
        front_path,
        active_canisters=[3, 4],
        camera_side='front',
        save_debug=True,
        debug_dir=front_debug_dir,
    )

    # Process back view (C1, C2)
    flags_back = process_containers_automated(
        back_path,
        active_canisters=[1, 2],
        camera_side='back',
        save_debug=True,
        debug_dir=back_debug_dir,
    )
    
    # Combine results and convert to expected format
    # process_containers_automated returns {'c1_recorrect': bool/None, ...}
    # We need to return {'c1': int, 'c2': int, 'c3': int, 'c4': int}
    results = {
        'c1': 1 if flags_back.get('c1_recorrect') else 0,
        'c2': 1 if flags_back.get('c2_recorrect') else 0,
        'c3': 1 if flags_front.get('c3_recorrect') else 0,
        'c4': 1 if flags_front.get('c4_recorrect') else 0,
    }
    
    print(f"[AUTO DETECT] Combined results: {results}")
    return results
# --------------------------- Logic loop --------------------------------------

def inspection_loop():
    inspection_id = 0
    photo_step_done = 0   # 0 none, 1 first view captured, 2 both views processed
    results_version = 0

    prev_mm = 0          # for rising-edge detect on HR135

    front_cap = None
    back_cap  = None
    front_path = None
    back_path  = None

    # Initial publish
    _ir_set(INSPECTION_ID_ADDR,   [inspection_id])
    _ir_set(PHOTO_STEP_DONE_ADDR, [photo_step_done])
    _ir_set(RESULTS_VERSION_ADDR, [results_version])
    _ir_set(C1_RECORRECT_ADDR, [0]); _ir_set(C2_RECORRECT_ADDR, [0])
    _ir_set(C3_RECONNECT_ADDR, [0]); _ir_set(C4_RECONNECT_ADDR, [0])

    print("[CAMERA] Inspection loop started")
    print(f"[CAMERA] Mode: {'GUI' if GUI_ENABLED else 'Automated CV'}")
    print(f"[CAMERA] Camera: {'Pi Camera' if USE_PI_CAMERA else 'File images'}")

    while True:
        try:
            mm = _hr_get(MM_RECEIVED_INSTRUCTION_ADDR, 1)[0]
            step = _hr_get(PHOTO_READY_STEP_ADDR, 1)[0]

            # Rising-edge on mm_recv_inst -> begin new inspection
            if mm == 1 and prev_mm == 0:
                inspection_id += 1
                photo_step_done = 0
                front_cap = back_cap = None
                front_path = back_path = None

                print(f"\\n[CAMERA] New inspection requested. ID = {inspection_id}\\n")

                _ir_set(INSPECTION_ID_ADDR,   [inspection_id])
                _ir_set(PHOTO_STEP_DONE_ADDR, [photo_step_done])
                # Do NOT clear HR135 here; the UR program does that itself.

            prev_mm = mm

            # First view requested
            if step == 1 and photo_step_done == 0 and front_cap is None:
                print("[CAMERA] First view ready, starting front photo capture...")
                print("[CAMERA] This photo shows: C3 (left), C4 (right)")
                front_cap = take_photo_async("first", inspection_id)

            if front_cap is not None and front_cap.get('done') and front_path is None:
                front_path = front_cap.get('path')
                photo_step_done = 1
                _ir_set(PHOTO_STEP_DONE_ADDR, [1])  # handshake: IR129=1
                print("[CAMERA] First view complete")

            # Second view requested
            if step == 2 and photo_step_done == 1 and back_cap is None:
                print("[CAMERA] Second view ready, starting back photo capture...")
                print("[CAMERA] This photo shows: C1 (left), C2 (right)")
                back_cap = take_photo_async("second", inspection_id)

            if back_cap is not None and back_cap.get('done') and back_path is None and photo_step_done == 1:
                back_path = back_cap.get('path')

                # Run your CV
                results = process_two_views(front_path, back_path)
                c1 = int(results.get("c1", 0))
                c2 = int(results.get("c2", 0))
                c3 = int(results.get("c3", 0))
                c4 = int(results.get("c4", 0))

                # Publish results
                _ir_set(C1_RECORRECT_ADDR, [c1])
                _ir_set(C2_RECORRECT_ADDR, [c2])
                _ir_set(C3_RECONNECT_ADDR, [c3])   # match UR name/addr 133
                _ir_set(C4_RECONNECT_ADDR, [c4])   # match UR name/addr 134

                photo_step_done = 2
                _ir_set(PHOTO_STEP_DONE_ADDR, [2])  # handshake: IR129=2

                results_version += 1
                _ir_set(RESULTS_VERSION_ADDR, [results_version])

                print(f"[CAMERA] Second view complete; c1..c4 = {(c1, c2, c3, c4)}")
                print(f"[CAMERA] Results version bumped to {results_version}")

            time.sleep(0.10)  # ~10Hz

        except Exception as e:
            print(f"[LOOP] ERROR: {e}")
            time.sleep(0.25)

# --------------------------- Server runner -----------------------------------

def _start_modbus_server(context, host: str, port: int):
    # Try multiple backends for pymodbus 3.x and 2.x
    try:
        from pymodbus.server import StartTcpServer as _Start
        _Start(context=context, address=(host, port))
        return
    except Exception:
        pass
    try:
        from pymodbus.server.sync import StartTcpServer as _StartSync
        _StartSync(context=context, address=(host, port))
        return
    except Exception:
        pass
    try:
        from pymodbus.server import ModbusTcpServer
        srv = ModbusTcpServer(context, address=(host, port), defer_start=False)
        srv.serve_forever()
        return
    except Exception as e:
        raise RuntimeError(f"Unable to start Modbus server: {e}")

def run_modbus_server():
    # Tweak logging if needed
    if os.getenv("DEBUG_MODBUS"):
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("pymodbus").setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("pymodbus").setLevel(logging.INFO)

    print(f"[MODBUS] Starting server on port {MODBUS_PORT}")
    _start_modbus_server(context, host="0.0.0.0", port=MODBUS_PORT)

# ------------------------------ Main -----------------------------------------

def main():
    if GUI_ENABLED:
        print("[MAIN] GUI mode not implemented here; set GUI_ENABLED=False.")
        sys.exit(1)
    else:
        logic = threading.Thread(target=inspection_loop, daemon=True)
        logic.start()

        print("[MAIN] Automated mode: Running Modbus server")
        print("[MAIN] Press Ctrl+C to exit")
        try:
            run_modbus_server()
        except KeyboardInterrupt:
            print("\\n[MAIN] Shutting down...")
            try:
                if camera is not None:
                    camera.stop()
            except Exception:
                pass
            sys.exit(0)

if __name__ == "__main__":
    main()
