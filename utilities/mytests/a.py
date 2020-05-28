from pypylon import pylon
import cv2
import matplotlib.pyplot as plt
import time
import os
import numpy as np
import imutils
from matplotlib.animation import FuncAnimation

figure = plt.figure()

# conecting to the first available camera
camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

# Grabing Continusely (video) with minimal delay
camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
converter = pylon.ImageFormatConverter()

# converting to opencv bgr format
converter.OutputPixelFormat = pylon.PixelType_BGR8packed
converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

while camera.IsGrabbing():
    grabResult = camera.RetrieveResult(500, pylon.TimeoutHandling_ThrowException)
    # i=0
    print(grabResult.GrabSucceeded())
    if grabResult.GrabSucceeded():

        # Access the image data
        image = converter.Convert(grabResult)
        frame = image.GetArray()

        # convert image to grayscale

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # blur the image
        gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)

        # resize the image
        img = imutils.resize(gray_blur, width=800)

        # apply thresholding
        ret, thresh = cv2.threshold(img, 127, 255, 0)

        # edge detection

        # apply Canny edge detection
        tight = cv2.Canny(thresh, 127, 255)

        # calculate the centre of moment

        M = cv2.moments(tight)

        h, w = tight.shape[:2]

        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])


        else:
            cX, cY = 0, 0

        # put text and highlight the center
        # Draw full segment lines

        cv2.line(tight, (cX, 0), (cX, w), (150, 0, 0), 1)
        cv2.line(tight, (0, cY), (h, cY), (150, 0, 0), 1)
        cv2.circle(tight, (cX, cY), 5, (255, 255, 255), -1)
        cv2.putText(tight, "centroid", (cX - 25, cY - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # open windows to display image

        # cv2.namedWindow('window', cv2.WINDOW_NORMAL)

        cv2.rectangle(thresh, (100, 200), (200, 300), (0, 255, 0),
                      2)  # we need to define the centre of the image wherfe the laser will be positioned
        cv2.namedWindow('window', cv2.WINDOW_AUTOSIZE)
        cv2.resizeWindow('window', 200, 200)
        cv2.imshow(' Raw image', frame)
        cv2.resizeWindow('Raw image', 500, 500)
        cv2.imshow('edge detection', tight)
        cv2.resizeWindow('edge detection', 800, 800)

        ####
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    grabResult.Release()

# Releasing the resource
camera.StopGrabbing()

# destroy all windows
cv2.destroyAllWindows()

