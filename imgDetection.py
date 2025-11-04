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
    
    # Optional: Show debug view
    # cv2.imshow(f'Canister {canister_id} - Edges', canny_image)
    # cv2.imshow(f'Canister {canister_id} - Lines', debug_img)
    
    return status


def process_pallet(image_front, image_back):
    """
    Process all canisters on a pallet and return their status.
    
    Args:
        image_front: Front camera image
        image_back: Back camera image
    
    Returns:
        list: Status dictionaries for all canisters
    """
    # Define crop regions for each canister [y1:y2, x1:x2]
    # You'll need to recalibrate these for your actual Pi photos
    crop_regions = [
        ('front', 1, [100, 120, 60, 190]),   # Canister 1
        ('front', 2, [100, 120, 0, 60]),     # Canister 2
        ('back', 3, [100, 120, 60, 190]),    # Canister 3
        ('back', 4, [100, 120, 0, 60])       # Canister 4
    ]
    
    canister_status = []
    
    for camera, canister_id, coords in crop_regions:
        # Select the appropriate image
        img = image_front if camera == 'front' else image_back
        
        # Crop the canister region
        y1, y2, x1, x2 = coords
        canister_crop = img[y1:y2, x1:x2]
        
        # Analyse this canister
        status = detect_canister_level(canister_crop, canister_id)
        canister_status.append(status)
        
        # Print summary for this canister
        level_str = "LEVEL" if status['is_level'] else "OFF KILTER"
        if status['has_top_line']:
            if status['is_curved']:
                print(f"Canister {canister_id}: {level_str} - CURVED (tilted towards/away from camera)")
            else:
                print(f"Canister {canister_id}: {level_str} - Angle: {status['angle']:.2f}°")
        else:
            print(f"Canister {canister_id}: No top line detected - skipping")
    
    return canister_status


# Main execution
if __name__ == "__main__":
    # Load images
    # LATER: Get images from the Pi
    image_front = cv2.imread(r'C:\Users\mattk\Downloads\rightTilt.jpg')
    image_back = cv2.imread(r'C:\Users\mattk\Downloads\rightTilt.jpg')
    
    # Process all canisters
    canister_status = process_pallet(image_front, image_back)
    
    # Display summary
    print("\n=== PALLET SUMMARY ===")
    for status in canister_status:
        print(f"Canister {status['id']}: Level={status['is_level']}, "
              f"Angle={status['angle']:.2f}°, Curved={status['is_curved']}")
    
    # Optional: Keep windows open for debugging
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    
    # You can now use canister_status for further processing
    # e.g., send alerts, log to database, etc.