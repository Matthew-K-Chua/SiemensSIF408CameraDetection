# Quick Start Guide - Two-Stage Container Inspection

## 📦 What You Have

You now have a complete two-stage inspection system that follows your pseudocode exactly:

### Core Files (Ready to Use)

1. **[almostMain.py](computer:///mnt/user-data/outputs/almostMain.py)** - Main Modbus server
   - Implements your pseudocode state machine
   - Handles two-stage processing (C1+C3, then C2+C4)
   - Atomic commit of all results

2. **[inspection_gui.py](computer:///mnt/user-data/outputs/inspection_gui.py)** - Manual inspection GUI
   - Shows only relevant containers per view
   - First view: C1, C3 active (C2, C4 greyed out)
   - Second view: C2, C4 active (C1, C3 greyed out)

3. **[imgDetection.py](computer:///mnt/user-data/outputs/imgDetection.py)** - Automated CV detection
   - Processes specific containers per view
   - Line detection and angle measurement
   - Curve detection for tilted canisters

### Documentation

4. **[README_TwoStage.md](computer:///mnt/user-data/outputs/README_TwoStage.md)** - Comprehensive guide
   - Complete explanation of all changes
   - Configuration examples
   - Calibration instructions
   - Troubleshooting

5. **[FLOW_DIAGRAM.md](computer:///mnt/user-data/outputs/FLOW_DIAGRAM.md)** - Visual workflow
   - Complete timeline diagram
   - Illustrates two-stage flow
   - Shows atomic commit process

## 🚀 Getting Started (Choose Your Mode)

### Option 1: Automated CV with Pi Camera (Production)

**Configuration in almostMain.py:**
```python
GUI_ENABLED = False
USE_PI_CAMERA = True
CROP_REGIONS_FRONT = {1: [y1, y2, x1, x2], 2: [...]}  # Calibrate these!
CROP_REGIONS_BACK = {3: [y1, y2, x1, x2], 4: [...]}
```

**Setup:**
```bash
# On Raspberry Pi
pip install opencv-python numpy pymodbus picamera2

# Run
sudo python almostMain.py
```

**What Happens:**
1. Robot triggers inspection
2. First view: Pi captures front → CV detects C1, C3 → Stores results
3. Robot moves to back position
4. Second view: Pi captures back → CV detects C2, C4 → Commits all results
5. Robot reads correction flags

---

### Option 2: Manual GUI Inspection (Quality Control)

**Configuration in almostMain.py:**
```python
GUI_ENABLED = True
USE_PI_CAMERA = True  # or False for testing
```

**Setup:**
```bash
pip install opencv-python numpy pymodbus PySide6 picamera2

# Run (with display)
sudo python almostMain.py
```

**What Happens:**
1. Robot triggers inspection
2. First view: Pi captures front → GUI shows C1, C3 → Operator marks defects → Submit
3. Robot moves to back position
4. Second view: Pi captures back → GUI shows C2, C4 → Operator marks defects → Submit
5. All results committed atomically
6. Robot reads correction flags

---

### Option 3: Testing with Static Images (Development)

**Configuration in almostMain.py:**
```python
GUI_ENABLED = False  # or True to test GUI
USE_PI_CAMERA = False
IMAGE_FRONT_PATH = r'/path/to/front_test.jpg'
IMAGE_BACK_PATH = r'/path/to/back_test.jpg'
```

**Setup:**
```bash
pip install opencv-python numpy pymodbus PySide6

# Run (no sudo needed if using port 1502)
python almostMain.py
```

**What Happens:**
- Same workflow, but uses pre-captured images instead of live camera

## ⚙️ Critical Configuration Steps

### Step 1: Calibrate Crop Regions (MUST DO!)

The default crop regions are placeholders. You MUST calibrate for your setup:

```python
# 1. Capture test images
from picamera2 import Picamera2
camera = Picamera2()
camera.start()
camera.capture_file('test_front.jpg')
# (reposition robot)
camera.capture_file('test_back.jpg')
camera.stop()

# 2. Find coordinates using this script
import cv2

img = cv2.imread('test_front.jpg')
clone = img.copy()

def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Clicked: x={x}, y={y}")
        cv2.circle(clone, (x, y), 5, (0, 255, 0), -1)
        cv2.imshow('Calibration', clone)

cv2.imshow('Calibration', img)
cv2.setMouseCallback('Calibration', mouse_callback)
print("Click top-left, then bottom-right of each canister")
cv2.waitKey(0)

# 3. Update CROP_REGIONS in almostMain.py
CROP_REGIONS_FRONT = {
    1: [y1_c1, y2_c1, x1_c1, x2_c1],
    2: [y1_c2, y2_c2, x1_c2, x2_c2],
}
CROP_REGIONS_BACK = {
    3: [y1_c3, y2_c3, x1_c3, x2_c3],
    4: [y1_c4, y2_c4, x1_c4, x2_c4],
}
```

### Step 2: Test Each Component

**Test CV Detection:**
```python
# In imgDetection.py, run the __main__ block
python imgDetection.py
```

**Test GUI:**
```python
# In inspection_gui.py, run the __main__ block
python inspection_gui.py
```

**Test Full System:**
```python
# Run almostMain.py and trigger via Modbus
# Or temporarily add this to trigger automatically:
# In inspection_loop(), after "Inspection loop started":
#     time.sleep(2)
#     _ir_set(MM_RECEIVED_INSTRUCTION_ADDR, [1])  # Auto-trigger
```

### Step 3: Deploy to Production

1. Copy all files to Raspberry Pi
2. Set `USE_PI_CAMERA = True`
3. Set `GUI_ENABLED = False` (for automated) or `True` (for manual QC)
4. Calibrate crop regions
5. Run: `sudo python almostMain.py`
6. Connect robot via Modbus

## 📊 How It Works (Summary)

### The Two-Stage Process

```
FIRST VIEW (photo_ready_step=1):
  ├─ Capture photo from front camera
  ├─ Process C1 and C3
  ├─ Store results: temp_c1, temp_c3
  └─ Set photo_step_done=1
      └─ Results NOT published yet!

SECOND VIEW (photo_ready_step=2):
  ├─ Capture photo from back camera
  ├─ Process C2 and C4
  ├─ ATOMIC COMMIT:
  │   ├─ c1_recorrect = temp_c1 (from first view)
  │   ├─ c2_recorrect = new_c2  (from second view)
  │   ├─ c3_recorrect = temp_c3 (from first view)
  │   ├─ c4_recorrect = new_c4  (from second view)
  │   └─ results_version++
  └─ Set photo_step_done=2
      └─ ALL results published together!
```

### Why Two Stages?

This matches your physical setup:
- **Front camera position**: Can see containers 1 and 3
- **Back camera position**: Can see containers 2 and 4
- Robot must move between positions
- Results from both views combined before publishing

## 🎯 Key Differences from Previous Version

| Aspect | Previous | New (Two-Stage) |
|--------|----------|-----------------|
| Processing | All 4 after 2nd view | C1+C3 after 1st, C2+C4 after 2nd |
| Commit | After 2nd view | After 2nd view (combined) |
| GUI Views | All 4 containers | Split: C1+C3, then C2+C4 |
| CV Processing | All at once | Separate per view |
| Results Storage | None needed | Temp storage for 1st view |

## 🔧 Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| GUI doesn't show | Install PySide6: `pip install PySide6` |
| CV doesn't work | Install OpenCV: `pip install opencv-python` |
| Wrong containers detected | Calibrate CROP_REGIONS |
| Pi camera not found | Enable camera: `sudo raspi-config` |
| Modbus connection fails | Use sudo or change port to 1502 |
| Results not updating | Check results_version incrementing |

## 📋 Checklist Before Deployment

- [ ] All dependencies installed
- [ ] Pi camera tested and working
- [ ] Crop regions calibrated with test images
- [ ] CV angle tolerance tuned (default: 2.0°)
- [ ] Tested both first and second views
- [ ] Verified atomic commit (all 4 results update together)
- [ ] Robot can connect via Modbus
- [ ] Error handling tested (missing images, etc.)

## 🎓 Understanding the Code

**Main State Machine (almostMain.py:inspection_loop):**
```python
while True:
    publish_all_registers()  # 10 Hz continuous
    
    if new_inspection_triggered:
        reset_state()
    
    if photo_ready_step == 1 and not_done_yet:
        take_photo()
        process_c1_c3()
        store_temp_results()  # NOT PUBLISHED
        mark_first_view_done()
    
    if photo_ready_step == 2 and first_view_done:
        take_photo()
        process_c2_c4()
        combine_all_results()  # c1 from temp, c2/c4 new, c3 from temp
        increment_version()    # COMMIT POINT
        publish_all()          # NOW VISIBLE TO ROBOT
        mark_second_view_done()
    
    sleep(100ms)
```

**GUI Interface (inspection_gui.py):**
```python
# First view
results = process_containers_gui(
    active_containers=[1, 3],
    view_name="First View (C1, C3)"
)
# Returns: {'c1_recorrect': bool, 'c2_recorrect': None, 
#           'c3_recorrect': bool, 'c4_recorrect': None}

# Second view
results = process_containers_gui(
    active_containers=[2, 4],
    view_name="Second View (C2, C4)"
)
# Returns: {'c1_recorrect': None, 'c2_recorrect': bool, 
#           'c3_recorrect': None, 'c4_recorrect': bool}
```

**CV Interface (imgDetection.py):**
```python
# First view
results = process_containers_automated(
    image_path='front.jpg',
    active_canisters=[1, 3],
    camera_side='front'
)

# Second view
results = process_containers_automated(
    image_path='back.jpg',
    active_canisters=[2, 4],
    camera_side='back'
)
```

## 🌟 You're Ready!

Your system now:
- ✅ Follows your pseudocode exactly
- ✅ Processes containers in two stages
- ✅ Commits results atomically
- ✅ Supports both automated and manual modes
- ✅ Integrates with Pi camera
- ✅ Handles errors gracefully
- ✅ Ready for production deployment

**Next Step:** Choose your mode from the options above and start testing!

For detailed information, refer to:
- **README_TwoStage.md** - Complete documentation
- **FLOW_DIAGRAM.md** - Visual workflow

Good luck with your AI-enhanced quality control system! 🤖🔍
