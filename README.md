# Siemens SIF408 Camera Detection System

An automated vision-based quality inspection system for container pallets, integrating computer vision with industrial robotics via Modbus TCP communication. Developed for the Siemens SIF400 station for the 48560 Automation Studio course at UTS.

## Overview

This system provides automated inspection of container pallets using dual-camera machine vision and robotic manipulation. The solution combines real-time image processing using a Rasperry Pi with a UR3 collaborative robot to detect misaligned containers and coordinate corrective actions to fix these containers, and a user-friendly ui for operators.

**Key Capabilities:**
- Automated detection of container tilt and misalignment using edge detection and Hough line transforms
- Dual-camera setup for comprehensive 360° pallet inspection
- Real-time Modbus TCP integration with UR3 robotic arm
- Operator-friendly GUI for manual verification and quality control
- Asynchronous communication architecture for responsive operation

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    UR3 Robot Controller                 │
│                   (Modbus TCP Server)                   │
└──────────────────────┬──────────────────────────────────┘
                       │ Modbus TCP (Port 502)
                       │ Register-based communication
┌──────────────────────▼──────────────────────────────────┐
│              Camera Inspection System Rasperry Pi       │
│            (Python Application - This Repo)             │
│                                                         │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Image         │  │   Modbus     │  │  Inspection  │ │
│  │  Detection     │──│   Client     │──│     GUI      │ │
│  │  (OpenCV)      │  │  (pymodbus)  │  │  (PySide6)   │ │
│  └────────────────┘  └──────────────┘  └──────────────┘ │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Camera System  │
              │  (Front + Back) │
              └─────────────────┘
```

### Communication Protocol

The system uses Modbus TCP to coordinate with the UR3 controller:

**Holding Registers (Integer Values):**
- `inspection_id` (reg 127): Incremental counter for each inspection cycle
- `photo_step_done` (reg 128): Workflow state (0=none, 1=first view, 2=complete)
- `results_version` (reg 129): Version counter for atomic result updates
- `photo_ready_step` (reg 135): Signal from UR3 when ready for inspection

**Coils (Boolean Outputs):**
- `c1_recorrect` through `c4_recorrect` (coils 130-133): Correction flags for each container
- `mm_received_instruction` (coil 134): Inspection trigger from UR3

## Features

### Computer Vision Pipeline

The `imgDetection.py` module implements container levelness detection:

1. **Edge Detection**: Canny edge detection with adaptive thresholding to identify container boundaries
2. **Line Detection**: Probabilistic Hough transform to identify horizontal top edges
3. **Angle Analysis**: Statistical analysis of detected lines to compute container tilt
4. **Curvature Detection**: Variance-based detection of curved surfaces indicating depth tilt

**Configurable Parameters:**
- Angle tolerance: ±2.0° for levelness threshold
- Minimum line length: 40 pixels
- Canny thresholds: 300/400 for robust edge detection in industrial lighting
- Median blur: 11px kernel for noise reduction

### Operator Interface

The PySide6-based GUI (`inspection_gui.py`) provides:

- **Visual Feedback**: Colour-coded status indicators (green=OK, red=needs correction)
- **Interactive Selection**: Click-to-toggle interface for marking defects
- **Clear Layout**: 2×2 grid matching physical container positions (C1-C4)
- **Immediate Response**: Asynchronous signal-based communication with main system

### Modbus Integration

The main controller (`camera_inspection_main.py`) orchestrates:

- **Asynchronous Architecture**: Non-blocking I/O using `asyncio` for real-time responsiveness
- **Thread-Safe GUI Bridge**: Qt signal/slot integration with asyncio event loop
- **Robust Connection Handling**: Automatic retry logic with configurable timeouts
- **10Hz State Publishing**: Continuous state updates to maintain synchronisation with robot
- **Atomic Result Commits**: Version-based updates prevent race conditions

## Installation

### Prerequisites

- Python 3.8 or higher
- Camera hardware (2× cameras for front/back views)
- Network connectivity to UR3 controller
- Linux/Windows/macOS supported

### Dependencies

```bash
pip install opencv-python numpy pymodbus PySide6
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

**Core Libraries:**
- `opencv-python>=4.8.0`: Computer vision and image processing
- `numpy>=1.24.0`: Numerical operations and array handling
- `pymodbus>=3.0.0`: Modbus TCP client implementation
- `PySide6>=6.5.0`: Qt-based GUI framework

## Configuration

### Environment Variables

Configure the system using environment variables:

```bash
# UR3 Robot Configuration
export UR3_IP="192.168.1.10"           # Default: 130.130.130.86
export UR3_MODBUS_PORT="502"           # Standard Modbus TCP port
```

### Camera Calibration

Adjust crop regions in `imgDetection.py` to match your camera setup:

```python
crop_regions = [
    ('front', 1, [y1, y2, x1, x2]),   # Canister 1 coordinates
    ('front', 2, [y1, y2, x1, x2]),   # Canister 2 coordinates
    ('back', 3, [y1, y2, x1, x2]),    # Canister 3 coordinates
    ('back', 4, [y1, y2, x1, x2])     # Canister 4 coordinates
]
```

Use the provided test images to calibrate these regions for your specific camera positioning and pallet dimensions.

## Usage

### Running the Complete System

```bash
python camera_inspection_main.py
```

This launches:
1. Modbus TCP client connecting to the UR3 controller
2. Continuous state monitoring and publishing (10Hz)
3. Inspection GUI on-demand when triggered by the robot
4. Automated result transmission back to the robot

### Standalone GUI Testing

Test the operator interface independently:

```bash
python inspection_gui.py
```

### Image Detection Testing

Test the vision algorithm with sample images:

```python
python imgDetection.py
```

Modify the image paths in the main block to use your test images.

### Diagnostic Tools

The repository includes several diagnostic utilities:

- `modbus_basic_test.py`: Test Modbus connectivity
- `read_ur3_registers.py`: Read and display UR3 register values
- `ur3_diagnostic_reader.py`: Comprehensive UR3 diagnostics
- `test_gp_registers.py`: General purpose register testing

## Workflow

### Standard Inspection Cycle

1. **Trigger**: UR3 sets `mm_received_instruction` flag
2. **Initialisation**: System increments `inspection_id` and resets `photo_step_done`
3. **Photo Capture**: Robot positions cameras and sets `photo_ready_step = 2`
4. **GUI Launch**: Operator interface appears for manual verification
5. **Operator Input**: User reviews images and marks containers needing correction
6. **Result Commit**: System updates correction flags and increments `results_version`
7. **Robot Action**: UR3 reads results and executes corrective movements

### Test Mode

The system includes a test mode for development without UR3 hardware:

```python
test_mode = True  # In camera_inspection_main.py, inspection_loop()
```

This enables:
- Simulated photo ready signals
- Automatic GUI triggering for testing
- Manual inspection cycling

## Project Structure

```
SiemensSIF408CameraDetection/
├── camera_inspection_main.py    # Main coordinator - Modbus client & workflow
├── inspection_gui.py             # Operator GUI - defect marking interface
├── imgDetection.py               # Computer vision - container levelness detection
├── modbus_basic_test.py          # Diagnostic - basic Modbus connectivity
├── modbus_test_photo.py          # Diagnostic - photo trigger testing
├── read_ur3_registers.py         # Diagnostic - register reading utility
├── ur3_diagnostic_reader.py      # Diagnostic - comprehensive UR3 analysis
├── test_gp_registers.py          # Diagnostic - GP register testing
├── Test/                         # Test data and validation scripts
├── images/                       # Sample images for calibration
├── imageOne.jpeg                 # Reference image
├── imageTwo.jpeg                 # Reference image
├── imageThree.jpeg               # Reference image
└── README.md                     # This file
```

## Modbus Register Reference

### Holding Registers (Function Codes 3, 6, 16)

| Address | Name | Description | Range |
|---------|------|-------------|-------|
| 127 | inspection_id | Inspection cycle counter | 0-65535 |
| 128 | photo_step_done | Workflow state | 0-2 |
| 129 | results_version | Result update counter | 0-65535 |
| 135 | photo_ready_step | Robot ready signal | 0-2 |

### Coils (Function Codes 1, 5, 15)

| Address | Name | Description | Values |
|---------|------|-------------|--------|
| 130 | c1_recorrect | Container 1 correction needed | TRUE/FALSE |
| 131 | c2_recorrect | Container 2 correction needed | TRUE/FALSE |
| 132 | c3_recorrect | Container 3 correction needed | TRUE/FALSE |
| 133 | c4_recorrect | Container 4 correction needed | TRUE/FALSE |
| 134 | mm_received_instruction | Inspection trigger | TRUE/FALSE |

## Technical Details

### Asynchronous Architecture

The system uses Python's `asyncio` for non-blocking I/O:

- **GUI Thread**: Runs Qt event loop in the main thread for GUI responsiveness
- **Modbus Thread**: Runs asyncio event loop in background thread for I/O operations
- **Bridge Pattern**: `GUIBridge` class coordinates between threads using Qt signals

This architecture ensures:
- The GUI remains responsive during long-running operations
- Modbus communication doesn't block the user interface
- State updates occur at consistent 10Hz rate
- Thread-safe data exchange between async and Qt contexts

### Error Handling

The system implements comprehensive error handling:

- **Connection Resilience**: Automatic reconnection with exponential backoff
- **Register Write Validation**: Error checking on all Modbus operations
- **Graceful Degradation**: Continues operation despite transient failures
- **Detailed Logging**: Structured console output for troubleshooting

### Computer Vision Algorithm

The levelness detection algorithm:

1. Converts to greyscale and applies median blur for noise reduction
2. Uses Canny edge detection with calibrated thresholds
3. Applies Probabilistic Hough Line Transform with tuned parameters
4. Filters for horizontal lines (±45° from horizontal)
5. Computes statistical measures: mean angle and standard deviation
6. Classifies containers based on angle tolerance and variance

**Edge Cases Handled:**
- No lines detected (incomplete view)
- Multiple angled lines (curved surface)
- High variance (complex geometry)
- Near-vertical containers (excluded from horizontal analysis)

## Development

### Testing Workflow

1. **Vision Algorithm**: Test with static images using `imgDetection.py`
2. **GUI Interface**: Verify user interaction with `inspection_gui.py`
3. **Modbus Communication**: Validate connectivity with diagnostic scripts
4. **Integration**: Run full system in test mode with simulated triggers
5. **Production**: Deploy with actual UR3 integration

### Debugging Tips

**Enable Visual Debugging in imgDetection.py:**
```python
cv2.imshow(f'Canister {canister_id} - Edges', canny_image)
cv2.imshow(f'Canister {canister_id} - Lines', debug_img)
cv2.waitKey(0)
```

**Increase Logging Verbosity:**
```python
# In camera_inspection_main.py
print(f"[DEBUG] Current state: {vars(state)}")
```

**Monitor Modbus Traffic:**
- Use Wireshark with Modbus TCP filter
- Check UR3 Modbus logs via Polyscope interface
- Verify register values using `read_ur3_registers.py`

### Code Quality

The codebase follows professional Python standards:

- **Type Hints**: Dataclasses and type annotations for clarity
- **Documentation**: Comprehensive docstrings in Google/NumPy style
- **Modularity**: Clean separation of concerns (vision, GUI, communication)
- **Error Handling**: Explicit exception handling with informative messages
- **PEP 8 Compliance**: Consistent code style and formatting

## Troubleshooting

### Common Issues

**Problem**: GUI doesn't appear when inspection is triggered
- **Solution**: Check that `photo_ready_step` is being set to 2 by the UR3
- **Debug**: Add logging in `inspection_loop()` to monitor state transitions

**Problem**: Modbus connection fails
- **Solution**: Verify UR3 IP address and ensure Modbus TCP server is enabled in Polyscope
- **Debug**: Run `modbus_basic_test.py` to isolate connectivity issues

**Problem**: Containers not detected correctly
- **Solution**: Recalibrate crop regions in `imgDetection.py` for your camera setup
- **Debug**: Enable visual debugging to see detected edges and lines

**Problem**: Results not updating on UR3
- **Solution**: Verify `results_version` is incrementing in Modbus logs
- **Debug**: Check UR3 is polling the correct coil addresses (130-133)

## Performance Considerations

- **State Publishing**: 10Hz update rate provides real-time feedback without overwhelming the network
- **Image Processing**: Edge detection optimised for industrial lighting conditions
- **GUI Responsiveness**: Asynchronous architecture prevents UI freezing
- **Memory Usage**: Minimal footprint suitable for embedded deployment
- **Network Latency**: Sub-100ms typical round-trip for Modbus operations

## Future Enhancements

Potential improvements for future iterations:

1. **Automated Image Capture**: Direct camera integration replacing manual photo triggers
2. **Machine Learning**: CNN-based defect classification to reduce manual verification
3. **Multi-Pallet Support**: Queue-based processing for high-throughput operations
4. **Cloud Logging**: Remote monitoring and analytics dashboard
5. **Auto-Calibration**: Computer vision-based automatic camera positioning
6. **3D Vision**: Depth sensing for improved tilt detection accuracy

## Hardware Requirements

### Minimum Specifications

- **Processor**: Dual-core 1.5GHz+ (recommended: Raspberry Pi 4 or equivalent)
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 1GB for application and dependencies
- **Network**: 100Mbps Ethernet for Modbus TCP
- **Display**: 1024×768 minimum resolution for GUI

### Camera Specifications

- **Resolution**: 640×480 minimum, 1920×1080 recommended
- **Frame Rate**: 15fps minimum for real-time operation
- **Interface**: USB 2.0/3.0, GigE, or CSI (Raspberry Pi)
- **Lens**: Fixed focal length matching working distance
- **Mounting**: Adjustable positioning for top-down pallet view

## Contributors

**Matthew K. Chua** 

**Marcus Frischknecht**  

## Acknowledgements

Special thanks to:
- Ricardo Aguilera for inviting us to this subject and providing extra learning material and support. 
- Pablo Poblete Durruty and Rodrigo Cuzmar Leiva, for their aid in troubleshooting, and teaching us the SIF400 system.

## Contact

For technical support or collaboration inquiries:
- **GitHub**: [@Matthew-K-Chua](https://github.com/Matthew-K-Chua)
- **Project Repository**: [SiemensSIF408CameraDetection](https://github.com/Matthew-K-Chua/SiemensSIF408CameraDetection)
- **Final Camera Repository**: [sif408_camera](https://github.com/marcus-frisch/sif408_camera)

---

**Built with:** Python • OpenCV • Qt • Modbus TCP • Universal Robots  
**Industry:** Manufacturing Automation • Quality Control • Computer Vision
