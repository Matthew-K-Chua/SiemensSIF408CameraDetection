import cv2
import numpy

image = cv2.imread('C:\\Users\\mattk\\Downloads\\rightTilt.jpg') # import img
cropped_img = image[100:120, 60:190] # crop to just the lid
gray_image = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY) # grayscale
blur_image = cv2.medianBlur(gray_image, 11) # blur to reduce noise
canny_image = cv2.Canny(blur_image, 300, 400) # find edges


cv2.imshow('Grayscale', canny_image)
cv2.waitKey(0)  
cv2.destroyAllWindows()

