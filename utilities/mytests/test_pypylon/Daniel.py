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
camera.Open()
#camera.GainAuto.SetValue('Once')
camera.GainRaw.SetValue(3)
camera.BlackLevelRaw.SetValue(-128)
camera.TriggerSource.SetValue("Line1")
camera.TriggerMode.SetValue("On")
camera.ExposureTimeAbs.SetValue(100000.0)
camera.AcquisitionFrameRateEnable.SetValue(True)
camera.AcquisitionFrameRateAbs.SetValue(5)
camera.PixelFormat.SetValue("Mono8")
converter = pylon.ImageFormatConverter()

# converting to opencv bgr format
converter.OutputPixelFormat = pylon.PixelType_Mono8
converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
while camera.IsGrabbing():
    grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    # i=0

    if grabResult.GrabSucceeded():

        # Access the image data
        image = converter.Convert(grabResult)
        img = imutils.resize(image.GetArray(), width=600, height=600)
        img = cv2.GaussianBlur(img, (3, 3), 0)
        # apply thresholding
        ret, thresh = cv2.threshold(img, 100, 255, 0)

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
        cv2.putText(tight, "centroid", (cX - 25, cY - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(tight, f"X={cX}", (cX+10, cY-70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(tight, f"Y={cY}", (cX+70, cY+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        cv2.imshow('Raw image', img)
        cv2.imshow('Edge detection', tight)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    grabResult.Release()

# Releasing the resource
camera.StopGrabbing()

# destroy all windows
cv2.destroyAllWindows()

