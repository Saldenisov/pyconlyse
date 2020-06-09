from pypylon import pylon
import cv2
import matplotlib.pyplot as plt
import time
import os
import numpy as np
import imutils
from matplotlib.animation import FuncAnimation

figure = plt.figure()

def init():
    # conecting to the first available camera
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()
    camera.Width = 550
    camera.Height = 550
    camera.OffsetX = 310
    camera.OffsetY = 290
    camera.GainRaw.SetValue(0)
    camera.BlackLevelRaw.SetValue(-30)
    camera.TriggerSource.SetValue("Line1")
    camera.TriggerMode.SetValue("On")
    camera.TriggerDelayAbs.SetValue(190000)
    camera.ExposureTimeAbs.SetValue(10000.0)
    camera.BalanceRatioRaw.SetValue(64)
    camera.AcquisitionFrameRateEnable.SetValue(False)
    camera.AcquisitionFrameRateAbs.SetValue(5)
    camera.PixelFormat.SetValue("Mono8")
    converter = pylon.ImageFormatConverter()

    # Transport layer
    # Packet Size
    camera.GevSCPSPacketSize.SetValue(1500)
    # Inter-Packet Delay
    camera.GevSCPD.SetValue(1000)

    # converting to opencv bgr format
    converter.OutputPixelFormat = pylon.PixelType_Mono8
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    return camera, converter


camera, converter = init()


camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
while camera.IsGrabbing():
    grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        # Access the image data
        image = converter.Convert(grabResult)
        #img = imutils.resize(image.GetArray(), width=300, height=300)
        img = cv2.GaussianBlur(image.GetArray(), (3, 3), 0)

        # apply thresholding

        ret, thresh = cv2.threshold(img, 80, 255, 0)
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # edge detection
        # apply Canny edge detection
        tight = cv2.Canny(thresh, 60, 255)

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
        cv2.line(img, (cX, 0), (cX, w), (150, 0, 0), 1)
        cv2.line(img, (0, cY), (h, cY), (150, 0, 0), 1)
        cv2.circle(img, (cX, cY), 5, (255, 255, 255), -1)
        cv2.putText(img, "centroid", (cX - 25, cY - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(img, f"X={cX}", (cX+10, cY-70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(img, f"Y={cY}", (cX+70, cY+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.drawContours(img, contours, -1, (0, 255, 0), 1)

        cv2.imshow('Raw image', img)


        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    grabResult.Release()

# Releasing the resource
camera.StopGrabbing()

# destroy all windows
cv2.destroyAllWindows()

