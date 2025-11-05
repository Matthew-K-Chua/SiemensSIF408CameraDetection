import cv2
import numpy as np

# 1. Load and preprocess
image = cv2.imread(r'\home\admin\test.jpg')
cropped_img = image[100:120, 60:190]  # crop to just the lid

gray_image = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
blur_image = cv2.medianBlur(gray_image, 11)
canny_image = cv2.Canny(blur_image, 300, 400)

# 2. Detect lines
lines = cv2.HoughLinesP(
    canny_image,
    rho=1,
    theta=np.pi / 180,
    threshold=30,
    minLineLength=40,
    maxLineGap=5
)

angles = []

if lines is not None:
    # Make a copy for drawing
    debug_img = cropped_img.copy()

    for line in lines:
        x1, y1, x2, y2 = line[0]

        # draw line for debugging
        cv2.line(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 1)

        dx = x2 - x1
        dy = y2 - y1

        if dx == 0:
            # vertical line: ignore for "lid level" test
            continue

        angle = np.degrees(np.arctan2(dy, dx))

        # Keep only roughly horizontal lines (e.g. within ±45°)
        if abs(angle) < 45:
            angles.append(angle)

    if angles:
        avg_angle = float(np.mean(angles))
        tolerance_deg = 2.0  # tune this
        is_level_flag = abs(avg_angle) < tolerance_deg
    else:
        # No good horizontal line found
        avg_angle = None
        is_level_flag = False
else:
    avg_angle = None
    is_level_flag = False

print("Average angle (deg):", avg_angle)
print("Is level?:", is_level_flag)

# 3. Show debug views
cv2.imshow('Canny edges', canny_image)
if lines is not None:
    cv2.imshow('Detected lines on lid', debug_img)

cv2.waitKey(0)
cv2.destroyAllWindows()
