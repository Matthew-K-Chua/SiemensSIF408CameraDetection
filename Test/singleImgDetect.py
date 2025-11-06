import cv2
import numpy as np

# ========================= Adaptive Detection Function =========================

def detect_canister_level(canister_img, canister_id, angle_tolerance=2.0, show_debug=False):
    """
    Detect if a canister is level by analysing the top horizontal line.
    Auto-scales parameters based on image size.
    """
    status = {
        'id': canister_id,
        'is_level': True,
        'angle': 0.0,
        'has_top_line': False,
        'is_curved': False
    }

    # Get crop dimensions to scale parameters
    crop_height, crop_width = canister_img.shape[:2]
    print(f"  Crop size: {crop_width}x{crop_height}")
    
    # Scale detection parameters based on image size
    # Reference: tuned for ~700x300 crops from 4608x2592 images
    scale_factor = min(crop_width / 700, crop_height / 300)
    
    # Scaled parameters
    min_line_length = max(10, int(40 * scale_factor))
    hough_threshold = max(10, int(30 * scale_factor))
    
    print(f"  Scale factor: {scale_factor:.2f}")
    print(f"  Using minLineLength={min_line_length}, threshold={hough_threshold}")

    grey_image = cv2.cvtColor(canister_img, cv2.COLOR_BGR2GRAY)
    # blur_image = cv2.medianBlur(grey_image, 1)
    blur_image = cv2.GaussianBlur(grey_image, (5, 5), 0)
    _, binary_image = cv2.threshold(blur_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # canny_image = cv2.Canny(blur_image, 30, 150)
    canny_image = cv2.Canny(binary_image, 30, 150) # Keep your Canny params for now

    # Show intermediate steps if debugging
    if show_debug:
        cv2.imshow(f"C{canister_id} - 1.Grayscale", cv2.resize(grey_image, (400, 300)))
        # cv2.imshow(f"C{canister_id} - 2.Blurred", cv2.resize(blur_image, (400, 300)))
        cv2.imshow(f"C{canister_id} - 3.Canny Edges", cv2.resize(canny_image, (400, 300)))

    lines = cv2.HoughLinesP(
        canny_image,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=5
    )

    if lines is None:
        print(f"  ⚠ No lines detected!")
        return status, canister_img.copy(), canny_image

    print(f"  ✓ Detected {len(lines)} lines")
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
        if abs(angle) < 50:
            horizontal_angles.append(angle)

    print(f"  Horizontal lines: {len(horizontal_angles)}")

    if not horizontal_angles:
        status['has_top_line'] = False
        return status, debug_img, canny_image

    angle_std = np.std(horizontal_angles)
    print(f"  Angle std dev: {angle_std:.2f}°")
    
    if angle_std > 5.0:
        # Lots of variation → likely curved
        status['is_curved'] = True
        status['is_level'] = False
        status['angle'] = float(np.median(horizontal_angles))
    else:
        avg_angle = float(np.median(horizontal_angles))
        status['angle'] = avg_angle
        status['is_level'] = abs(avg_angle) < angle_tolerance

    return status, debug_img, canny_image

# ========================= Main Script =========================

# Load image
image_path = r'C:\Users\mattk\000INDEX\SiemensSIF408CameraDetection\Test\imgs\inspection_1_first_view_20251106_133900.jpg'
image = cv2.imread(image_path)

if image is None:
    print("Failed to load image!")
    exit()

print(f"\n{'='*60}")
print(f"Image loaded: {image.shape[1]}x{image.shape[0]}")
print(f"{'='*60}\n")

# Image resolution reference
height, width = image.shape[:2]

# Define crop regions (matching your server code)
left_y1, left_y2 = int(height * 0.38), int(height * 0.50)
left_x1, left_x2 = int(width * 0.24), int(width * 0.50)

right_y1, right_y2 = int(height * 0.38), int(height * 0.50)
right_x1, right_x2 = int(width * 0.60), int(width * 0.85)

# Crop the canisters
left_cropped_img = image[left_y1:left_y2, left_x1:left_x2]
right_cropped_img = image[right_y1:right_y2, right_x1:right_x2]

print("="*60)
print("PROCESSING LEFT CANISTER (C3)")
print("="*60)

# Process left canister (C3) with debug enabled
left_status, left_debug, left_canny = detect_canister_level(
    left_cropped_img, 
    canister_id=3,
    show_debug=True
)

level_str = "✓ LEVEL" if left_status['is_level'] else "✗ OFF KILTER"
if left_status['has_top_line']:
    if left_status['is_curved']:
        print(f"Result: {level_str} - CURVED")
        print(f"  Average angle: {left_status['angle']:.2f}°")
    else:
        print(f"Result: {level_str}")
        print(f"  Angle: {left_status['angle']:.2f}°")
else:
    print(f"Result: No top line detected - assuming LEVEL")

print("\n" + "="*60)
print("PROCESSING RIGHT CANISTER (C4)")
print("="*60)

# Process right canister (C4) with debug enabled
right_status, right_debug, right_canny = detect_canister_level(
    right_cropped_img, 
    canister_id=4,
    show_debug=True
)

level_str = "✓ LEVEL" if right_status['is_level'] else "✗ OFF KILTER"
if right_status['has_top_line']:
    if right_status['is_curved']:
        print(f"Result: {level_str} - CURVED")
        print(f"  Average angle: {right_status['angle']:.2f}°")
    else:
        print(f"Result: {level_str}")
        print(f"  Angle: {right_status['angle']:.2f}°")
else:
    print(f"Result: No top line detected - assuming LEVEL")

print("\n" + "="*60)
print("FINAL RESULTS")
print("="*60)
print(f"C3 (Left):  {'PASS' if left_status['is_level'] else 'NEEDS RECORRECTION'}")
print(f"C4 (Right): {'PASS' if right_status['is_level'] else 'NEEDS RECORRECTION'}")
print("="*60 + "\n")

# Display windows
print("Press any key to cycle through windows, ESC to exit...")

# Show original crops
cv2.imshow("C3 - Original Crop", cv2.resize(left_cropped_img, (400, 300)))
cv2.waitKey(0)

cv2.imshow("C4 - Original Crop", cv2.resize(right_cropped_img, (400, 300)))
cv2.waitKey(0)

# Show detected lines
cv2.imshow("C3 - Detected Lines", cv2.resize(left_debug, (400, 300)))
cv2.waitKey(0)

cv2.imshow("C4 - Detected Lines", cv2.resize(right_debug, (400, 300)))
cv2.waitKey(0)

cv2.destroyAllWindows()

print("\nDone!")