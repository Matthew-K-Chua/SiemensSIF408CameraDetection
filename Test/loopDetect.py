import os
import csv
import datetime
import cv2
import numpy as np
import shutil

# ========================= GLOBAL TUNING PARAMS =========================

# Angle tolerance in degrees – tweak this while tuning.
ANGLE_TOLERANCE = 2.5

# Canny edge thresholds (also tweakable if needed)
CANNY_LOW = 20
CANNY_HIGH = 60


# ========================= Adaptive Detection Function =========================

def detect_canister_level(canister_img, canister_id,
                          angle_tolerance=2.0,
                          canny_low=30,
                          canny_high=150,
                          show_debug=False):
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
    print(f"  [C{canister_id}] Crop size: {crop_width}x{crop_height}")
    
    # Scale detection parameters based on image size
    # Reference: tuned for ~700x300 crops from 4608x2592 images
    scale_factor = min(crop_width / 700.0, crop_height / 300.0)
    
    # Scaled parameters
    # min_line_length = max(10, int(40 * scale_factor))
    # hough_threshold = max(10, int(30 * scale_factor))
    min_line_length = max(10, int(25 * scale_factor))  # <-- Try 25
    hough_threshold = max(10, int(20 * scale_factor))  # <-- Try 20
    
    print(f"  [C{canister_id}] Scale factor: {scale_factor:.2f}")
    print(f"  [C{canister_id}] Using minLineLength={min_line_length}, "
          f"threshold={hough_threshold}")

    grey_image = cv2.cvtColor(canister_img, cv2.COLOR_BGR2GRAY)
    # blur_image = cv2.medianBlur(grey_image, 1)
    blur_image = cv2.GaussianBlur(grey_image, (5, 5), 0)
    _, binary_image = cv2.threshold(blur_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # --- NEW FIX 2: Clean up noise ---
    # Use a 3x3 kernel
    kernel = np.ones((3, 3), np.uint8)
    # MORPH_OPEN removes small white "noise" pixels
    binary_image_cleaned = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, kernel)
    # --- END FIX ---

    # Use the *cleaned* image for Canny
    canny_image = cv2.Canny(binary_image_cleaned, canny_low, canny_high)

    # Show intermediate steps if debugging
    if show_debug:
        cv2.imshow(f"C{canister_id} - 1.Grayscale",
                   cv2.resize(grey_image, (400, 300)))
        cv2.imshow(f"C{canister_id} - 3.Canny Edges",
                   cv2.resize(canny_image, (400, 300)))
        cv2.waitKey(1)

    lines = cv2.HoughLinesP(
        canny_image,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=5
    )

    if lines is None:
        print(f"  [C{canister_id}] ⚠ No lines detected!")
        return status, canister_img.copy(), canny_image

    print(f"  [C{canister_id}] ✓ Detected {len(lines)} lines")
    status['has_top_line'] = True

    horizontal_angles = [] # <-- Keep this line
    debug_img = canister_img.copy()

    best_line = None
    max_length = 0
    horizontal_lines_found = 0

    for line in lines:
        x1, y1, x2, y2 = line[0]

        if y1 < crop_height * 0.2 or y1 > crop_height * 0.6:
            continue  # Skip lines too high or too low
        if y2 < crop_height * 0.2 or y2 > crop_height * 0.6:
            continue

        dx = x2 - x1
        dy = y2 - y1
        if dx == 0: continue # avoid division by zero

        # 2. Angle Filter (Horizontal-ish)
        angle = np.degrees(np.arctan2(dy, dx))
        if abs(angle) > 30:  # Only < 30 degrees
            continue
            
        horizontal_lines_found += 1
        horizontal_angles.append(angle) # Still collect all angles for std dev

        # 3. Find longest line that passes filters
        length = np.sqrt(dx**2 + dy**2)
        
        if length > max_length:
            max_length = length
            best_line = (x1, y1, x2, y2, angle) # Store the line and its angle

        # Draw all *considered* lines in blue
        cv2.line(debug_img, (x1, y1), (x2, y2), (255, 0, 0), 1)

    print(f"  [C{canister_id}] Horizontal lines: {horizontal_lines_found}")

    # --- NEW ANGLE LOGIC ---
    if best_line is None:
        print(f"  [C{canister_id}] ⚠ No suitable horizontal lines found!")
        status['has_top_line'] = False
        return status, debug_img, canny_image # Use debug_img

    # We have a winner!
    status['has_top_line'] = True
    x1, y1, x2, y2, final_angle = best_line
    status['angle'] = float(final_angle)
    status['is_level'] = abs(final_angle) < angle_tolerance
    
    # Draw the *best* line in red
    cv2.line(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
    
    # We can still check for curves as a secondary check
    if horizontal_lines_found > 0:
        angle_std = np.std(horizontal_angles)
        print(f"  [C{canister_id}] Angle std dev: {angle_std:.2f}°")
        if angle_std > 5.0:
            status['is_curved'] = True
            # If it's curved, it's not level
            status['is_level'] = False 

    return status, debug_img, canny_image


# ========================= Helper: crop both canisters =========================

def crop_canisters(image):
    """Return (left_crop, right_crop) using updated crop ratios."""
    height, width = image.shape[:2]

    # Define crop regions - vertical band from 0.30 to 0.55
    y1 = int(height * 0.30)
    y2 = int(height * 0.55)
    
    # Horizontal positions
    left_x1, left_x2 = int(width * 0.24), int(width * 0.50)
    right_x1, right_x2 = int(width * 0.60), int(width * 0.85)

    left_cropped_img = image[y1:y2, left_x1:left_x2]
    right_cropped_img = image[y1:y2, right_x1:right_x2]

    return left_cropped_img, right_cropped_img


# ========================= Main Tuning Evaluation =========================

def evaluate_tuning_folder():
    tuning_dir = r"C:\Users\mattk\000INDEX\SiemensSIF408CameraDetection\Test\tuning"
    print(f"Using tuning folder: {tuning_dir}")

    if not os.path.isdir(tuning_dir):
        print("❌ tuning folder not found.")
        return

    # Create imgOutputs folder at the same level as tuning folder
    parent_dir = os.path.dirname(tuning_dir)
    output_dir = os.path.join(parent_dir, "imgOutputs")
    
    # Remove and recreate the output folder to ensure clean slate
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    print(f"Output folder created/cleared: {output_dir}\n")

    image_files = [
        f for f in sorted(os.listdir(tuning_dir))
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_files:
        print("No image files found in tuning folder.")
        return

    print(f"Found {len(image_files)} images to evaluate.\n")

    # Metrics
    total_cases = 0       # total canisters (2 per image)
    correct_cases = 0

    left_tp = left_fp = left_fn = left_tn = 0
    right_tp = right_fp = right_fn = right_tn = 0

    for filename in image_files:
        base_name, _ = os.path.splitext(filename)
        if len(base_name) < 2:
            print(f"Skipping {filename}: name too short for labels.")
            continue

        # Ground truth from first two chars: e.g. 'TFx.jpg'
        left_char = base_name[0].upper()
        right_char = base_name[1].upper()

        if left_char not in ("T", "F") or right_char not in ("T", "F"):
            print(f"Skipping {filename}: invalid label pattern.")
            continue

        # True means needs recorrection (off-kilter)
        gt_left_recorrect = (left_char == "T")
        gt_right_recorrect = (right_char == "T")

        img_path = os.path.join(tuning_dir, filename)
        image = cv2.imread(img_path)

        if image is None:
            print(f"Failed to load {img_path}, skipping.")
            continue

        print("=" * 70)
        print(f"Processing {filename}")
        print("=" * 70)

        left_img, right_img = crop_canisters(image)

        # Process left (C3)
        left_status, left_debug, left_canny = detect_canister_level(
            left_img, canister_id=3, angle_tolerance=ANGLE_TOLERANCE,
            canny_low=CANNY_LOW, canny_high=CANNY_HIGH,
            show_debug=False
        )
        pred_left_recorrect = not left_status['is_level']

        # Process right (C4)
        right_status, right_debug, right_canny = detect_canister_level(
            right_img, canister_id=4, angle_tolerance=ANGLE_TOLERANCE,
            canny_low=CANNY_LOW, canny_high=CANNY_HIGH,
            show_debug=False
        )
        pred_right_recorrect = not right_status['is_level']

        # ========================= SAVE DEBUG IMAGES =========================
        # Save left canister images
        cv2.imwrite(os.path.join(output_dir, f"{base_name}_C3_crop.jpg"), left_img)
        cv2.imwrite(os.path.join(output_dir, f"{base_name}_C3_lines.jpg"), left_debug)
        cv2.imwrite(os.path.join(output_dir, f"{base_name}_C3_canny.jpg"), left_canny)
        
        # Save right canister images
        cv2.imwrite(os.path.join(output_dir, f"{base_name}_C4_crop.jpg"), right_img)
        cv2.imwrite(os.path.join(output_dir, f"{base_name}_C4_lines.jpg"), right_debug)
        cv2.imwrite(os.path.join(output_dir, f"{base_name}_C4_canny.jpg"), right_canny)
        # ====================================================================

        # ---- Metrics update ----
        # Left
        if gt_left_recorrect and pred_left_recorrect:
            left_tp += 1
        elif gt_left_recorrect and not pred_left_recorrect:
            left_fn += 1
        elif not gt_left_recorrect and pred_left_recorrect:
            left_fp += 1
        else:
            left_tn += 1

        # Right
        if gt_right_recorrect and pred_right_recorrect:
            right_tp += 1
        elif gt_right_recorrect and not pred_right_recorrect:
            right_fn += 1
        elif not gt_right_recorrect and pred_right_recorrect:
            right_fp += 1
        else:
            right_tn += 1

        total_cases += 2
        if gt_left_recorrect == pred_left_recorrect:
            correct_cases += 1
        if gt_right_recorrect == pred_right_recorrect:
            correct_cases += 1

        print(f"  GT Left:  {'T' if gt_left_recorrect else 'F'} | "
              f"Pred: {'T' if pred_left_recorrect else 'F'} | "
              f"Angle: {left_status['angle']:.2f}°")
        print(f"  GT Right: {'T' if gt_right_recorrect else 'F'} | "
              f"Pred: {'T' if pred_right_recorrect else 'F'} | "
              f"Angle: {right_status['angle']:.2f}°")

    # ========================= Final Metrics =========================
    print("\n" + "#" * 70)
    print("FINAL TUNING RESULTS")
    print("#" * 70)

    overall_acc = correct_cases / total_cases if total_cases else 0.0

    left_total = left_tp + left_fp + left_fn + left_tn
    right_total = right_tp + right_fp + right_fn + right_tn

    left_acc = (left_tp + left_tn) / left_total if left_total else 0.0
    right_acc = (right_tp + right_tn) / right_total if right_total else 0.0

    print(f"Total canisters evaluated: {total_cases}")
    print(f"Overall accuracy: {overall_acc * 100:.2f}%")
    print(f"Left accuracy:    {left_acc * 100:.2f}% "
          f"(TP={left_tp}, FP={left_fp}, FN={left_fn}, TN={left_tn})")
    print(f"Right accuracy:   {right_acc * 100:.2f}% "
          f"(TP={right_tp}, FP={right_fp}, FN={right_fn}, TN={right_tn})")

    print(f"\n✓ Debug images saved to: {output_dir}")

    # ========================= Append summary to CSV =========================
    summary_path = os.path.join(tuning_dir, "tuning_results.csv")
    file_exists = os.path.exists(summary_path)

    with open(summary_path, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp",
                "angle_tolerance_deg",
                "canny_low",
                "canny_high",
                "num_images",
                "total_canisters",
                "overall_accuracy",
                "left_accuracy",
                "right_accuracy",
                "left_tp", "left_fp", "left_fn", "left_tn",
                "right_tp", "right_fp", "right_fn", "right_tn"
            ])

        writer.writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            ANGLE_TOLERANCE,
            CANNY_LOW,
            CANNY_HIGH,
            len(image_files),
            total_cases,
            f"{overall_acc:.4f}",
            f"{left_acc:.4f}",
            f"{right_acc:.4f}",
            left_tp, left_fp, left_fn, left_tn,
            right_tp, right_fp, right_fn, right_tn
        ])

    print(f"Summary appended to: {summary_path}")


if __name__ == "__main__":
    evaluate_tuning_folder()