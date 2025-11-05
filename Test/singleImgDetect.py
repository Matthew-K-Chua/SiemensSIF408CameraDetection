import cv2

# Load image
image = cv2.imread(r'C:/Users/mattk/000INDEX/SiemensSIF408CameraDetection/imageOne.jpeg')

if image is None:
    print("Failed to load image!")
    exit()

# Image resolution reference (approx 4608x2592)
height, width = image.shape[:2]

# Define left crop region (red box area in your example)
# y: vertical, x: horizontal
left_y1, left_y2 = int(height * 0.42), int(height * 0.55)   # middle vertical band
left_x1, left_x2 = int(width * 0.35), int(width * 0.51)     # center horizontally

left_cropped_img = image[left_y1:left_y2, left_x1:left_x2]

# Optional: downscale display
scale = 0.3
left_cropped_small = cv2.resize(left_cropped_img, (int(left_cropped_img.shape[1]*scale), int(left_cropped_img.shape[0]*scale)))

# Define right crop region (red box area in your example)
# y: vertical, x: horizontal
right_y1, right_y2 = int(height * 0.42), int(height * 0.55)   # middle vertical band
right_x1, right_x2 = int(width * 0.55), int(width * 0.71)     # center horizontally

right_cropped_img = image[right_y1:right_y2, right_x1:right_x2]

# Optional: downscale display
scale = 0.3
right_cropped_small = cv2.resize(right_cropped_img, (int(right_cropped_img.shape[1]*scale), int(right_cropped_img.shape[0]*scale)))


cv2.imshow("Left Cropped", left_cropped_small)
cv2.imshow("Right Cropped", right_cropped_small)

cv2.waitKey(0)
cv2.destroyAllWindows()





# import cv2
# import numpy as np

# # 1. Load and preprocess
# image = cv2.imread(r'C:/Users/mattk/000INDEX/SiemensSIF408CameraDetection/images/test1.jpg')
# cv2.imshow("img", image)

# cropped_img = image[100:120, 60:190]  # crop to just the lid

# gray_image = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
# blur_image = cv2.medianBlur(gray_image, 11)
# canny_image = cv2.Canny(blur_image, 300, 400)

# # 2. Detect lines
# lines = cv2.HoughLinesP(
#     canny_image,
#     rho=1,
#     theta=np.pi / 180,
#     threshold=30,
#     minLineLength=40,
#     maxLineGap=5
# )

# angles = []

# if lines is not None:
#     # Make a copy for drawing
#     debug_img = cropped_img.copy()

#     for line in lines:
#         x1, y1, x2, y2 = line[0]

#         # draw line for debugging
#         cv2.line(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 1)

#         dx = x2 - x1
#         dy = y2 - y1

#         if dx == 0:
#             # vertical line: ignore for "lid level" test
#             continue

#         angle = np.degrees(np.arctan2(dy, dx))

#         # Keep only roughly horizontal lines (e.g. within ±45°)
#         if abs(angle) < 45:
#             angles.append(angle)

#     if angles:
#         avg_angle = float(np.mean(angles))
#         tolerance_deg = 2.0  # tune this
#         is_level_flag = abs(avg_angle) < tolerance_deg
#     else:
#         # No good horizontal line found
#         avg_angle = None
#         is_level_flag = False
# else:
#     avg_angle = None
#     is_level_flag = False

# print("Average angle (deg):", avg_angle)
# print("Is level?:", is_level_flag)

# # 3. Show debug views
# cv2.imshow('Canny edges', canny_image)
# if lines is not None:
#     cv2.imshow('Detected lines on lid', debug_img)

# cv2.waitKey(0)
# cv2.destroyAllWindows()
