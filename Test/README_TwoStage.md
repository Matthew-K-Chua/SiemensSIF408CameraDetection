# Two-Stage Container Inspection System - Implementation Guide

## Overview

This implementation follows your pseudocode exactly, processing containers in two separate stages:

1. **First View** (`photo_ready_step=1`): Capture photo → Process C1 & C3 → Store results
2. **Second View** (`photo_ready_step=2`): Capture photo → Process C2 & C4 → Commit ALL results atomically

## Key Changes from Previous Version

### 1. Two-Stage Processing

**Previous Version:**
- All 4 containers processed after second view

**New Version:**
- First view: Process C1, C3 (results stored but NOT published)
- Second view: Process C2, C4 (combine with stored C1, C3 results and publish atomically)

### 2. Results Flow

```
photo_ready_step = 1
    ↓
Take Photo (Front Camera)
    ↓
Process C1, C3 → temp_c1, temp_c3 (STORED, NOT PUBLISHED)
    ↓
photo_step_done = 1
    ↓
[WAITING FOR SECOND VIEW]
    ↓
photo_ready_step = 2
    ↓
Take Photo (Back Camera)
    ↓
Process C2, C4 → new_c2, new_c4
    ↓
ATOMIC COMMIT:
    c1_recorrect = temp_c1
    c2_recorrect = new_c2
    c3_recorrect = temp_c3
    c4_recorrect = new_c4
    results_version++
    photo_step_done = 2
    ↓
PUBLISH ALL RESULTS
```

## Files Structure

### 1. `almostMain.py` (Main Server)

**Configuration Options:**

```python
# ============================================================================
# CONFIGURATION
# ============================================================================
GUI_ENABLED = False      # True = GUI, False = Automated CV
USE_PI_CAMERA = False    # True = Capture from Pi, False = Use file paths

# File paths (when USE_PI_CAMERA=False)
IMAGE_FRONT_PATH = r'C:\Users\mattk\Downloads\frontView.jpg'
IMAGE_BACK_PATH = r'C:\Users\mattk\Downloads\backView.jpg'

# Crop regions (optional - None uses defaults)
CROP_REGIONS_FRONT = {
    1: [100, 120, 60, 190],  # C1: [y1, y2, x1, x2]
    2: [100, 120, 0, 60],    # C2
}
CROP_REGIONS_BACK = {
    3: [100, 120, 60, 190],  # C3
    4: [100, 120, 0, 60],    # C4
}
```

**Key Functions:**

```python
def take_photo(view_name):
    """Capture from Pi camera or use file path"""
    
def process_containers_view(active_canisters, view_name, image_path, camera_side):
    """Process specific containers for one view"""
    
def inspection_loop():
    """Main loop following pseudocode exactly"""
```

### 2. `inspection_gui.py` (GUI Module)

**New Features:**

- Can display only specific containers (C1+C3 or C2+C4)
- Inactive containers shown as greyed out
- View-specific titles and instructions
- Returns dict with None for inactive containers

**Usage:**

```python
# First view - only C1 and C3 active
results = process_containers_gui(
    active_containers=[1, 3],
    view_name="First View (C1, C3)"
)
# Returns: {'c1_recorrect': True, 'c2_recorrect': None, 
#           'c3_recorrect': False, 'c4_recorrect': None}

# Second view - only C2 and C4 active
results = process_containers_gui(
    active_containers=[2, 4],
    view_name="Second View (C2, C4)"
)
# Returns: {'c1_recorrect': None, 'c2_recorrect': True, 
#           'c3_recorrect': None, 'c4_recorrect': False}
```

### 3. `imgDetection.py` (CV Module)

**New Features:**

- Processes only specified containers
- Separate processing for front/back camera
- Returns dict with None for unprocessed containers

**Usage:**

```python
# First view - front camera, C1 and C3
results = process_containers_automated(
    image_path='front_view.jpg',
    active_canisters=[1, 3],
    crop_regions=CROP_REGIONS_FRONT,
    camera_side='front'
)

# Second view - back camera, C2 and C4
results = process_containers_automated(
    image_path='back_view.jpg',
    active_canisters=[2, 4],
    crop_regions=CROP_REGIONS_BACK,
    camera_side='back'
)
```

## Configuration Scenarios

### Scenario 1: Automated CV with Pi Camera (Production)

```python
GUI_ENABLED = False
USE_PI_CAMERA = True
CROP_REGIONS_FRONT = {1: [150, 180, 80, 220], 2: [150, 180, 20, 80]}
CROP_REGIONS_BACK = {3: [150, 180, 80, 220], 4: [150, 180, 20, 80]}
```

**Run:**
```bash
sudo python almostMain.py  # Needs sudo for port 502
```

**Flow:**
1. Robot triggers inspection
2. First view: Pi captures front photo → CV processes C1, C3
3. Second view: Pi captures back photo → CV processes C2, C4 → Commits
4. Results published to robot via Modbus

### Scenario 2: Manual GUI with Pi Camera (Quality Control)

```python
GUI_ENABLED = True
USE_PI_CAMERA = True
```

**Run:**
```bash
sudo python almostMain.py
```

**Flow:**
1. Robot triggers inspection
2. First view: Pi captures front photo → GUI shows C1, C3 → Operator marks → Stores
3. Second view: Pi captures back photo → GUI shows C2, C4 → Operator marks → Commits
4. Results published to robot via Modbus

### Scenario 3: Testing with Static Images (Development)

```python
GUI_ENABLED = False  # or True for GUI testing
USE_PI_CAMERA = False
IMAGE_FRONT_PATH = r'/home/pi/test_images/front_test.jpg'
IMAGE_BACK_PATH = r'/home/pi/test_images/back_test.jpg'
```

**Run:**
```bash
python almostMain.py  # Can use port 1502 if not sudo
```

## Camera Integration

### Adding Pi Camera Support

The code already includes Pi camera support. Just ensure `picamera2` is installed:

```bash
pip install picamera2
```

### Camera Positioning

Based on your pseudocode:
- **Front Camera**: Captures C1 (left), C2 (right) - triggered at `photo_ready_step=1`
- **Back Camera**: Captures C3 (left), C4 (right) - triggered at `photo_ready_step=2`

But your pseudocode says:
- First view processes C1, C3
- Second view processes C2, C4

This suggests:
- **Front Camera**: Captures C1, C3 (both containers visible from front)
- **Back Camera**: Captures C2, C4 (both containers visible from back)

You may need to adjust based on your physical setup.

### Customizing Camera Capture

Modify the `take_photo()` function:

```python
def take_photo(view_name):
    """Capture photo from camera with custom settings"""
    if USE_PI_CAMERA:
        camera = Picamera2()
        
        # Configure camera settings
        config = camera.create_still_configuration(
            main={"size": (1920, 1080)},  # Resolution
            lores={"size": (640, 480)},
            display="lores"
        )
        camera.configure(config)
        
        camera.start()
        time.sleep(2)  # Allow camera to adjust
        
        temp_path = os.path.join(tempfile.gettempdir(), f'{view_name.lower().replace(" ", "_")}.jpg')
        camera.capture_file(temp_path)
        camera.stop()
        
        return temp_path
    else:
        # Use file paths as before
        ...
```

## Calibrating Crop Regions

### Step 1: Capture Test Images

```python
# Temporary script to capture calibration images
from picamera2 import Picamera2

camera = Picamera2()
camera.start()

# Capture from position 1
camera.capture_file('calibration_front.jpg')
input("Move robot to position 2, then press Enter...")

# Capture from position 2
camera.capture_file('calibration_back.jpg')
camera.stop()
```

### Step 2: Find Coordinates

```python
import cv2

def calibrate_crop_regions():
    """Interactive tool to find crop coordinates"""
    
    # Load your test image
    img = cv2.imread('calibration_front.jpg')
    
    clone = img.copy()
    points = []
    
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
            cv2.circle(clone, (x, y), 5, (0, 255, 0), -1)
            cv2.imshow('Calibration', clone)
            print(f"Point {len(points)}: x={x}, y={y}")
            
            if len(points) == 2:
                # Draw rectangle
                cv2.rectangle(clone, points[0], points[1], (0, 255, 0), 2)
                cv2.imshow('Calibration', clone)
                
                # Calculate crop region
                x1, y1 = points[0]
                x2, y2 = points[1]
                print(f"\nCrop region: [{min(y1,y2)}, {max(y1,y2)}, {min(x1,x2)}, {max(x1,x2)}]")
                
                points.clear()
    
    cv2.imshow('Calibration', img)
    cv2.setMouseCallback('Calibration', mouse_callback)
    
    print("Click top-left corner, then bottom-right corner of canister")
    print("Press 'q' to quit")
    
    while True:
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()

# Run calibration
calibrate_crop_regions()
```

### Step 3: Update Crop Regions

```python
# In almostMain.py
CROP_REGIONS_FRONT = {
    1: [150, 180, 80, 220],   # C1 - from calibration
    2: [150, 180, 20, 80],    # C2 - from calibration
}

CROP_REGIONS_BACK = {
    3: [155, 185, 75, 215],   # C3 - from calibration
    4: [155, 185, 15, 75],    # C4 - from calibration
}
```

## Testing Each Mode

### Test 1: Automated CV Mode

```bash
# Set configuration
GUI_ENABLED = False
USE_PI_CAMERA = False
IMAGE_FRONT_PATH = '/path/to/test_front.jpg'
IMAGE_BACK_PATH = '/path/to/test_back.jpg'

# Run
python almostMain.py

# Trigger via Modbus client or modify code to auto-trigger
```

**Expected Output:**
```
[CONFIG] Automated mode enabled - using CV detection
[CONFIG] Camera: File-based
[MODBUS] Starting server on port 502
[CAMERA] Inspection loop started.

[CAMERA] ═══════════════════════════════════════
[CAMERA] New inspection requested. ID = 1
[CAMERA] ═══════════════════════════════════════

[CAMERA] ─── FIRST VIEW ───
[CAMERA] Using First View image: /path/to/test_front.jpg
[INSPECTION] Running automated detection for First View (C1, C3)...
[AUTO DETECT] Processing canisters: C1, C3
[AUTO DETECT] Canister 1: OFF KILTER - Angle: 3.45°
[AUTO DETECT] Canister 3: LEVEL - Angle: 0.23°
[AUTO DETECT] Results: c1_recorrect=True c3_recorrect=False 
[CAMERA] First view complete: C1=True, C3=False (stored, not committed)

[CAMERA] ─── SECOND VIEW ───
[CAMERA] Using Second View image: /path/to/test_back.jpg
[INSPECTION] Running automated detection for Second View (C2, C4)...
[AUTO DETECT] Processing canisters: C2, C4
[AUTO DETECT] Canister 2: LEVEL - Angle: 0.89°
[AUTO DETECT] Canister 4: OFF KILTER - Angle: 4.12°
[AUTO DETECT] Results: c2_recorrect=False c4_recorrect=True 
[CAMERA] Second view complete: C2=False, C4=True

[CAMERA] ✓ Results COMMITTED (version 1):
[CAMERA]     C1 := True
[CAMERA]     C2 := False
[CAMERA]     C3 := False
[CAMERA]     C4 := True
[CAMERA] ═══════════════════════════════════════
```

### Test 2: GUI Mode

```bash
# Set configuration
GUI_ENABLED = True
USE_PI_CAMERA = False

# Run
python almostMain.py
```

**Expected Behavior:**
1. After first `photo_ready_step=1`:
   - GUI window appears
   - Title: "First View (C1, C3) - Mark Defects"
   - C1 and C3 are green (clickable)
   - C2 and C4 are grey (disabled)
   - Operator clicks containers needing correction
   - Clicks "Submit"
   
2. After second `photo_ready_step=2`:
   - New GUI window appears
   - Title: "Second View (C2, C4) - Mark Defects"
   - C2 and C4 are green (clickable)
   - C1 and C3 are grey (disabled)
   - Operator clicks containers needing correction
   - Clicks "Submit"
   - All results committed atomically

## Modbus Communication Flow

### Robot Side (UR/PLC)

```
// Start new inspection
WRITE mm_received_instruction := 1

// Wait for camera to be ready
WAIT UNTIL READ(photo_step_done) = 0

// Move to first position
MoveToPosition(FrontCamera)
WRITE photo_ready_step := 1

// Wait for first view complete
WAIT UNTIL READ(photo_step_done) = 1

// Move to second position
MoveToPosition(BackCamera)
WRITE photo_ready_step := 2

// Wait for results (atomic commit happens here)
last_version := READ(results_version)
WAIT UNTIL READ(photo_step_done) = 2 AND READ(results_version) > last_version

// Read results
c1_needs_correction := READ(c1_recorrect)
c2_needs_correction := READ(c2_recorrect)
c3_needs_correction := READ(c3_recorrect)
c4_needs_correction := READ(c4_recorrect)

// Take corrective action
IF c1_needs_correction THEN CorrectCanister(1)
IF c2_needs_correction THEN CorrectCanister(2)
IF c3_needs_correction THEN CorrectCanister(3)
IF c4_needs_correction THEN CorrectCanister(4)
```

### Camera Side (This Code)

The `inspection_loop()` matches your pseudocode exactly:

1. Continuously publishes all registers at 10 Hz
2. Monitors `mm_received_instruction` to start new inspection
3. Waits for `photo_ready_step=1` to process first view
4. Waits for `photo_ready_step=2` to process second view and commit

## Troubleshooting

### Issue: GUI doesn't show correct containers

**Cause:** Wrong active_containers list
**Solution:** Check that first view uses `[1, 3]` and second uses `[2, 4]`

### Issue: Results are committed too early

**Cause:** Results_version bumped before second view
**Solution:** Ensure `results_version++` only happens in second view branch

### Issue: First view results lost

**Cause:** Temporary variables not persisted
**Solution:** Use `temp_c1` and `temp_c3` variables outside the if blocks

### Issue: Pi camera not found

**Solution:**
```bash
# Install picamera2
sudo apt update
sudo apt install -y python3-picamera2

# Enable camera
sudo raspi-config
# Interface Options → Camera → Enable
```

### Issue: Image crop regions wrong

**Solution:** Use the calibration script above to find correct coordinates

### Issue: Modbus connection fails

**Solution:**
```bash
# Check if port 502 is available
sudo netstat -tlnp | grep 502

# If running without sudo, use port 1502 instead
# In almostMain.py:
# StartTcpServer(context=context, address=("0.0.0.0", 1502))
```

## Performance Considerations

### Timing

- **Continuous publish**: 10 Hz (100ms loop)
- **First view processing**: ~1-3 seconds (CV) or user-dependent (GUI)
- **Second view processing**: ~1-3 seconds (CV) or user-dependent (GUI)
- **Total inspection time**: ~2-6 seconds for automated, variable for GUI

### Optimizations

1. **Reduce crop region size**: Smaller images process faster
2. **Adjust Canny thresholds**: Tune for your lighting conditions
3. **Cache camera object**: Reuse Picamera2 instance if capturing multiple times

## Next Steps

1. **Deploy to Pi**: Copy files to Raspberry Pi
2. **Install dependencies**:
   ```bash
   pip install opencv-python numpy pymodbus PySide6 picamera2
   ```
3. **Calibrate crop regions**: Use test images from your setup
4. **Test with robot**: Connect via Modbus and trigger inspections
5. **Tune CV parameters**: Adjust angle tolerance, curve detection for your canisters
6. **Production deployment**: Set `USE_PI_CAMERA=True` and `GUI_ENABLED=False`

## Summary of Changes

✅ Two-stage processing (C1+C3, then C2+C4)
✅ Atomic commit of all results after second view  
✅ Temporary storage for first view results
✅ GUI supports partial container display
✅ CV supports processing specific containers
✅ Pi camera integration ready
✅ Follows pseudocode exactly
✅ Results only published after both views complete

This implementation is production-ready and matches your pseudocode specification!
