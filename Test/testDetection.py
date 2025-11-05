import cv2
import numpy as np
from singleImgDetect import detect_canister_level, process_pallet

def test_with_visual_output(image_path, active_canisters, camera_side='front'):
    """
    Test the detection with visual output showing crops and detected lines.
    
    Args:
        image_path: Path to test image
        active_canisters: List of canister IDs to test (e.g., [1, 2])
        camera_side: 'front' or 'back'
    """
    print(f"\n{'='*60}")
    print(f"Testing: {image_path}")
    print(f"Camera side: {camera_side}")
    print(f"Active canisters: {active_canisters}")
    print(f"{'='*60}\n")
    
    # Load image
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"ERROR: Could not load image from {image_path}")
        return
    
    height, width = image.shape[:2]
    print(f"Image resolution: {width}x{height}")
    
    # Calculate crop regions (same logic as in main code)
    y1 = int(height * 0.42)
    y2 = int(height * 0.55)
    
    left_x1 = int(width * 0.35)
    left_x2 = int(width * 0.51)
    
    right_x1 = int(width * 0.55)
    right_x2 = int(width * 0.71)
    
    if camera_side == 'front':
        crop_regions = {
            1: [y1, y2, left_x1, left_x2],
            2: [y1, y2, right_x1, right_x2],
        }
    else:
        crop_regions = {
            3: [y1, y2, left_x1, left_x2],
            4: [y1, y2, right_x1, right_x2]
        }
    
    # Draw crop boxes on original image
    annotated = image.copy()
    for canister_id in active_canisters:
        if canister_id in crop_regions:
            y1, y2, x1, x2 = crop_regions[canister_id]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(annotated, f"C{canister_id}", (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # Save annotated image
    annotated_path = image_path.replace('.jpg', '_annotated.jpg').replace('.jpeg', '_annotated.jpg')
    cv2.imwrite(annotated_path, annotated)
    print(f"Saved annotated image to: {annotated_path}")
    
    # Process each canister and save crops
    for canister_id in active_canisters:
        if canister_id not in crop_regions:
            continue
        
        y1, y2, x1, x2 = crop_regions[canister_id]
        canister_crop = image[y1:y2, x1:x2]
        
        # Run detection
        status = detect_canister_level(canister_crop, canister_id)
        
        # Save the crop
        crop_path = image_path.replace('.jpg', f'_c{canister_id}_crop.jpg').replace('.jpeg', f'_c{canister_id}_crop.jpg')
        cv2.imwrite(crop_path, canister_crop)
        
        # Print results
        print(f"\nCanister {canister_id}:")
        print(f"  Crop saved to: {crop_path}")
        print(f"  Status: {'LEVEL' if status['is_level'] else 'OFF KILTER'}")
        print(f"  Has top line: {status['has_top_line']}")
        print(f"  Is curved: {status['is_curved']}")
        print(f"  Angle: {status['angle']:.2f} degrees")
    
    print(f"\n{'='*60}\n")


def quick_test(image_path):
    """
    Quick test that checks all four canisters using the same image.
    Useful for initial testing.
    """
    print("\n" + "="*60)
    print("QUICK TEST MODE")
    print("Testing all canisters using the provided image")
    print("="*60)
    
    # Test front view (C1, C2)
    test_with_visual_output(image_path, [1, 2], camera_side='front')
    
    # Test back view (C3, C4) using same image
    test_with_visual_output(image_path, [3, 4], camera_side='back')


if __name__ == "__main__":
    # Easy testing - just update this path
    TEST_IMAGE = '/home/pi/test_image.jpg'
    
    print("\n" + "#"*60)
    print("# CANISTER DETECTION TEST SCRIPT")
    print("#"*60)
    
    # Option 1: Quick test all canisters
    quick_test(TEST_IMAGE)
    
    # Option 2: Test specific setup
    # Uncomment these lines to test specific configurations
    # test_with_visual_output(TEST_IMAGE, [1, 2], camera_side='front')
    # test_with_visual_output(TEST_IMAGE, [3, 4], camera_side='back')