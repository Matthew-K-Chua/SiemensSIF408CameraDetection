# Two-Stage Inspection Flow Diagram

## Complete Inspection Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ROBOT TRIGGERS INSPECTION                    │
│              (writes mm_received_instruction = 1)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAMERA SYSTEM RESPONDS                       │
│              inspection_id++                                     │
│              photo_step_done = 0                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ROBOT MOVES TO POSITION 1                      │
│           (writes photo_ready_step = 1)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
╔═════════════════════════════════════════════════════════════════╗
║                       FIRST VIEW PROCESSING                     ║
╠═════════════════════════════════════════════════════════════════╣
║  1. Take Photo (Front Camera)                                   ║
║     └─> Capture from Pi Camera OR use IMAGE_FRONT_PATH          ║
║                                                                  ║
║  2. Process Containers C1 and C3                                ║
║     ┌─────────────────────┬─────────────────────┐              ║
║     │   GUI MODE          │   AUTOMATED MODE     │              ║
║     ├─────────────────────┼─────────────────────┤              ║
║     │ Show GUI with:      │ Run CV Detection:    │              ║
║     │ • C1 GREEN (active) │ • Crop C1 region     │              ║
║     │ • C2 GREY (inactive)│ • Detect angle       │              ║
║     │ • C3 GREEN (active) │ • Crop C3 region     │              ║
║     │ • C4 GREY (inactive)│ • Detect angle       │              ║
║     │                     │                      │              ║
║     │ User clicks to mark │ Return results       │              ║
║     │ defective canisters │                      │              ║
║     └─────────────────────┴─────────────────────┘              ║
║                                                                  ║
║  3. Store Results (NOT published yet)                           ║
║     temp_c1 = <result>      ┐                                   ║
║     temp_c3 = <result>      │ STORED IN MEMORY                  ║
║                             │ NOT VISIBLE TO ROBOT YET          ║
║  4. Set photo_step_done = 1 ┘                                   ║
║                                                                  ║
║  Published to robot:                                            ║
║    • photo_step_done = 1    ✓                                   ║
║    • results_version = N    (unchanged)                         ║
║    • c1_recorrect = <old>   (previous value)                    ║
║    • c2_recorrect = <old>   (previous value)                    ║
║    • c3_recorrect = <old>   (previous value)                    ║
║    • c4_recorrect = <old>   (previous value)                    ║
╚═════════════════════════════════════════════════════════════════╝
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ROBOT MOVES TO POSITION 2                      │
│           (writes photo_ready_step = 2)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
╔═════════════════════════════════════════════════════════════════╗
║                      SECOND VIEW PROCESSING                     ║
╠═════════════════════════════════════════════════════════════════╣
║  1. Take Photo (Back Camera)                                    ║
║     └─> Capture from Pi Camera OR use IMAGE_BACK_PATH           ║
║                                                                  ║
║  2. Process Containers C2 and C4                                ║
║     ┌─────────────────────┬─────────────────────┐              ║
║     │   GUI MODE          │   AUTOMATED MODE     │              ║
║     ├─────────────────────┼─────────────────────┤              ║
║     │ Show GUI with:      │ Run CV Detection:    │              ║
║     │ • C1 GREY (inactive)│ • Crop C2 region     │              ║
║     │ • C2 GREEN (active) │ • Detect angle       │              ║
║     │ • C3 GREY (inactive)│ • Crop C4 region     │              ║
║     │ • C4 GREEN (active) │ • Detect angle       │              ║
║     │                     │                      │              ║
║     │ User clicks to mark │ Return results       │              ║
║     │ defective canisters │                      │              ║
║     └─────────────────────┴─────────────────────┘              ║
║                                                                  ║
║  3. Combine Results (ATOMIC COMMIT)                             ║
║     c1_recorrect = temp_c1      ┐                               ║
║     c2_recorrect = new_c2       │                               ║
║     c3_recorrect = temp_c3      │ ALL UPDATED                   ║
║     c4_recorrect = new_c4       │ TOGETHER                      ║
║     results_version++           │                               ║
║     photo_step_done = 2         ┘                               ║
║                                                                  ║
║  Published to robot:                                            ║
║    • photo_step_done = 2    ✓                                   ║
║    • results_version = N+1  ✓ ← COMMIT POINT                    ║
║    • c1_recorrect = temp_c1 ✓ (from first view)                 ║
║    • c2_recorrect = new_c2  ✓ (from second view)                ║
║    • c3_recorrect = temp_c3 ✓ (from first view)                 ║
║    • c4_recorrect = new_c4  ✓ (from second view)                ║
╚═════════════════════════════════════════════════════════════════╝
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ROBOT READS RESULTS                          │
│   Waits for: photo_step_done=2 AND results_version incremented │
│   Then reads all 4 correction flags                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ROBOT TAKES CORRECTIVE ACTION                   │
│   FOR EACH canister WHERE c<i>_recorrect = TRUE:                │
│       Execute correction procedure                              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Points

### 1. Two Separate Photo Captures
- **First photo**: Front camera position → Process C1, C3
- **Second photo**: Back camera position → Process C2, C4

### 2. Results Storage Pattern
```
First View:  temp_c1, temp_c3 → STORED (not published)
                                    ↓
                            [Robot repositions]
                                    ↓
Second View: new_c2, new_c4 → COMBINE with temp values
                                    ↓
                            ATOMIC COMMIT
                                    ↓
                    ALL RESULTS PUBLISHED TOGETHER
```

### 3. Atomic Commit Guarantee
The robot sees a **consistent** set of results because:
- Results from both views are combined BEFORE publishing
- `results_version` is incremented only AFTER all 4 flags are set
- Robot monitors `results_version` to detect when new results are ready

### 4. Continuous Publishing
```
Every 100ms (10 Hz):
    PUBLISH inspection_id
    PUBLISH photo_step_done
    PUBLISH results_version
    PUBLISH c1_recorrect
    PUBLISH c2_recorrect  
    PUBLISH c3_recorrect
    PUBLISH c4_recorrect
```

The robot can read these at any time, but should:
- Wait for `photo_step_done = 2`
- Wait for `results_version` to increment
- Then read the correction flags

## Example Timeline

```
Time    Event                           Published Values
────────────────────────────────────────────────────────────────
t=0     Robot triggers inspection       inspection_id=0
                                        photo_step_done=0
                                        results_version=0
                                        c1/c2/c3/c4=FALSE

t=1     inspection_id++                 inspection_id=1
                                        photo_step_done=0
                                        results_version=0
                                        c1/c2/c3/c4=FALSE

t=2     Robot: photo_ready_step=1       inspection_id=1
                                        photo_step_done=0
                                        results_version=0
                                        c1/c2/c3/c4=FALSE

t=3     First view: Take photo          (same as above)

t=4     First view: Process C1, C3      (same as above)
        Result: C1=TRUE, C3=FALSE       
        Stored in: temp_c1, temp_c3     (NOT PUBLISHED YET)

t=5     photo_step_done=1               inspection_id=1
                                        photo_step_done=1 ← CHANGED
                                        results_version=0
                                        c1/c2/c3/c4=FALSE ← OLD VALUES

t=6     Robot: photo_ready_step=2       (same as above)

t=7     Second view: Take photo         (same as above)

t=8     Second view: Process C2, C4     (same as above)
        Result: C2=FALSE, C4=TRUE

t=9     ATOMIC COMMIT:                  inspection_id=1
        c1 = temp_c1 = TRUE             photo_step_done=2 ← CHANGED
        c2 = new_c2 = FALSE             results_version=1 ← INCREMENTED
        c3 = temp_c3 = FALSE            c1=TRUE  ← NEW ✓
        c4 = new_c4 = TRUE              c2=FALSE ← NEW ✓
        results_version++               c3=FALSE ← NEW ✓
        photo_step_done=2               c4=TRUE  ← NEW ✓

t=10    Robot reads results             (robot takes action)
```

## Configuration Matrix

```
┌──────────────┬────────────────┬────────────────┬────────────────┐
│  GUI_ENABLED │ USE_PI_CAMERA  │  Use Case      │  Best For      │
├──────────────┼────────────────┼────────────────┼────────────────┤
│  FALSE       │  TRUE          │  Production    │  Automated     │
│              │                │  Automated CV  │  operations    │
├──────────────┼────────────────┼────────────────┼────────────────┤
│  TRUE        │  TRUE          │  Production    │  Quality       │
│              │                │  Manual QC     │  control       │
├──────────────┼────────────────┼────────────────┼────────────────┤
│  FALSE       │  FALSE         │  Development   │  Testing CV    │
│              │                │  Testing       │  algorithms    │
├──────────────┼────────────────┼────────────────┼────────────────┤
│  TRUE        │  FALSE         │  Development   │  Testing GUI   │
│              │                │  Testing       │  workflow      │
└──────────────┴────────────────┴────────────────┴────────────────┘
```

## File Responsibilities

```
almostMain.py
    ├─ Modbus communication
    ├─ State machine (follows pseudocode)
    ├─ Coordinates both views
    └─ Atomic commit logic

inspection_gui.py  
    ├─ GUI display (partial containers)
    ├─ User interaction
    └─ Returns results dict

imgDetection.py
    ├─ CV processing (specific containers)
    ├─ Line detection
    ├─ Angle calculation
    └─ Returns results dict
```

## Error Handling

```
┌────────────────────────┬─────────────────────────────────────┐
│  Error Condition       │  Behavior                           │
├────────────────────────┼─────────────────────────────────────┤
│  Camera read fails     │  Return all None → Robot decides    │
├────────────────────────┼─────────────────────────────────────┤
│  No lines detected     │  Assume LEVEL (default safe)        │
├────────────────────────┼─────────────────────────────────────┤
│  User closes GUI       │  Results still returned (from state)│
├────────────────────────┼─────────────────────────────────────┤
│  Modbus disconnection  │  Continue processing, reconnects    │
└────────────────────────┴─────────────────────────────────────┘
```
