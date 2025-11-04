import cv2
import numpy as np

def detect_canister_level(canister_img, canister_id, angle_tolerance=2.0):
    """
    Detect if a canister is level by analysing the top horizontal line.
    
    Args:
        canister_img: Cropped image of canister top region
        canister_id: Identifier for the canister (1-4)
        angle_tolerance: Maximum angle deviation (degrees) to consider level
    
    Returns:
        dict: Status information for the canister
    """
    status = {
        'id': canister_id,
        'is_level': True,  # Default assumption
        'angle': 0.0,
        'has_top_line': False,
        'is_curved': False
    }
    
    # Preprocess
    gray_image = cv2.cvtColor(canister_img, cv2.COLOR_BGR2GRAY)
    blur_image = cv2.medianBlur(gray_image, 11)
    canny_image = cv2.Canny(blur_image, 300, 400)
    
    # Detect lines
    lines = cv2.HoughLinesP(
        canny_image,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=40,
        maxLineGap=5
    )
    
    if lines is None:
        # No top line detected - skip this canister
        return status
    
    status['has_top_line'] = True
    
    # Analyse detected lines
    horizontal_angles = []
    debug_img = canister_img.copy()
    
    for line in lines:
        x1, y1, x2, y2 = line[0]
        cv2.line(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 1)
        
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0:
            continue  # Skip vertical lines
        
        angle = np.degrees(np.arctan2(dy, dx))
        
        # Keep roughly horizontal lines (within ±45°)
        if abs(angle) < 45:
            horizontal_angles.append(angle)
    
    if not horizontal_angles:
        # No horizontal lines found
        status['has_top_line'] = False
        return status
    
    # Check if the top is curved by looking at angle variance
    angle_std = np.std(horizontal_angles)
    if angle_std > 5.0:  # High variance suggests curved or multiple angled lines
        status['is_curved'] = True
        status['is_level'] = False
        status['angle'] = float(np.mean(horizontal_angles))
    else:
        # Straight line - check the angle
        avg_angle = float(np.mean(horizontal_angles))
        status['angle'] = avg_angle
        status['is_level'] = abs(avg_angle) < angle_tolerance
    
    return status


def process_pallet(image, active_canisters, crop_regions=None, camera_side='front'):
    """
    Process specific canisters from a single camera view.
    
    Args:
        image: Camera image (front or back)
        active_canisters: List of canister IDs to process (e.g., [1, 3])
        crop_regions: Optional dict mapping canister_id to crop coords [y1, y2, x1, x2]
        camera_side: 'front' or 'back' - used for default crop regions
    
    Returns:
        dict: Status for each processed canister {canister_id: status_dict}
    """
    # Default crop regions if not provided
    if crop_regions is None:
        # You'll need to calibrate these for your setup
        if camera_side == 'front':
            crop_regions = {
                1: [100, 120, 60, 190],   # Canister 1
                2: [100, 120, 0, 60],     # Canister 2
            }
        else:  # back
            crop_regions = {
                3: [100, 120, 60, 190],   # Canister 3
                4: [100, 120, 0, 60]      # Canister 4
            }
    
    canister_status = {}
    
    for canister_id in active_canisters:
        if canister_id not in crop_regions:
            print(f"[AUTO DETECT] Warning: No crop region defined for canister {canister_id}")
            continue
        
        # Crop the canister region
        y1, y2, x1, x2 = crop_regions[canister_id]
        canister_crop = image[y1:y2, x1:x2]
        
        # Analyse this canister
        status = detect_canister_level(canister_crop, canister_id)
        canister_status[canister_id] = status
        
        # Print summary for this canister
        level_str = "LEVEL" if status['is_level'] else "OFF KILTER"
        if status['has_top_line']:
            if status['is_curved']:
                print(f"[AUTO DETECT] Canister {canister_id}: {level_str} - CURVED (tilted towards/away from camera)")
            else:
                print(f"[AUTO DETECT] Canister {canister_id}: {level_str} - Angle: {status['angle']:.2f}°")
        else:
            print(f"[AUTO DETECT] Canister {canister_id}: No top line detected - assuming LEVEL")
    
    return canister_status


def get_recorrection_flags_from_dict(canister_status):
    """
    Convert canister status dict to recorrection flags.
    
    Args:
        canister_status: Dict mapping canister_id to status dict
    
    Returns:
        dict: {'c1_recorrect': bool/None, 'c2_recorrect': bool/None, ...}
              None indicates canister was not processed
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


def process_containers_automated(image_path, active_canisters, crop_regions=None, camera_side='front'):
    """
    Automated container inspection for specific canisters.
    
    Args:
        image_path: Path to camera image
        active_canisters: List of canister IDs to process (e.g., [1, 3])
        crop_regions: Optional custom crop regions
        camera_side: 'front' or 'back' for default regions
    
    Returns:
        dict: {'c1_recorrect': bool/None, ...}
              None values indicate containers not processed
    """
    canister_str = ", ".join([f"C{i}" for i in sorted(active_canisters)])
    print(f"\n[AUTO DETECT] Processing canisters: {canister_str}")
    print(f"[AUTO DETECT] Loading image: {image_path}")
    
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"[AUTO DETECT] ERROR: Failed to load image. Defaulting all to OK.")
        # Return None for all to indicate error
        return {
            'c1_recorrect': None,
            'c2_recorrect': None,
            'c3_recorrect': None,
            'c4_recorrect': None,
        }
    
    # Process specified canisters
    canister_status = process_pallet(image, active_canisters, crop_regions, camera_side)
    
    # Convert to recorrection flags
    result = get_recorrection_flags_from_dict(canister_status)
    
    print(f"[AUTO DETECT] Results: ", end="")
    for i in sorted(active_canisters):
        key = f'c{i}_recorrect'
        print(f"{key}={result[key]} ", end="")
    print("\n")
    
    return result


# Main execution for standalone testing
if __name__ == "__main__":
    # Test with sample images
    image_front = cv2.imread(r'C:\Users\mattk\Downloads\rightTilt.jpg')
    
    if image_front is not None:
        print("\n=== Testing First View (C1, C3) ===")
        results_view1 = process_containers_automated(
            r'C:\Users\mattk\Downloads\rightTilt.jpg',
            active_canisters=[1, 3],
            camera_side='front'
        )
        print(f"View 1 results: {results_view1}")
        
        print("\n=== Testing Second View (C2, C4) ===")
        results_view2 = process_containers_automated(
            r'C:\Users\mattk\Downloads\rightTilt.jpg',
            active_canisters=[2, 4],
            camera_side='back'
        )
        print(f"View 2 results: {results_view2}")
        
        # Merge results
        print("\n=== Combined Results ===")
        combined = {**results_view1, **results_view2}
        for k, v in combined.items():
            if v is not None:
                print(f"{k}: {v}")
