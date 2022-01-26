from collections import deque

import cv2
import  numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from pypylon import pylon, genicam

countOfImagesToGrab = 1
maxCamerasToUse = 1

DEVICE = None
SERIAL_NUMBER = '24058647'
# Init all camera
try:
    # Get the transport layer factory.
    tlFactory = pylon.TlFactory.GetInstance()

    # Get all attached devices and exit application if no device is found.
    devices = tlFactory.EnumerateDevices()
    if len(devices) == 0:
        raise pylon.RUNTIME_EXCEPTION("No camera present.")
    else:
        for dev in devices:
            ser_number = dev.GetSerialNumber()
            if dev.GetSerialNumber() == SERIAL_NUMBER:
                DEVICE = dev
                break


except genicam.GenericException as e:
    # Error handling
    print("An exception occurred. {}".format(e))
    exitCode = 1

OffSet = {'X': 300, 'Y': 380}

test = {}

def init(device):
    instance = pylon.TlFactory.GetInstance()
    camera = pylon.InstantCamera(instance.CreateDevice(device))
    camera.Open()
    camera.StopGrabbing()
    b = camera.IsOpen()
    a = camera.GetDeviceInfo().GetModelName()
    b = camera.GetDeviceInfo().GetSerialNumber()
    c = camera.GetDeviceInfo().GetIpAddress()
    camera.Width = 370
    camera.Height = 370
    camera.OffsetX.SetValue(OffSet['X'])
    camera.OffsetY = OffSet['Y']
    camera.GainAuto = 'Off'
    camera.GainRaw = 0
    camera.BlackLevelRaw.SetValue(-30)
    camera.TriggerSource = "Line1"
    camera.TriggerMode.SetValue("On")
    camera.TriggerDelayAbs.SetValue(150000)
    camera.ExposureTimeAbs.SetValue(50000.0)
    camera.BalanceRatioRaw.SetValue(64)
    camera.AcquisitionFrameRateEnable.SetValue(False)
    camera.AcquisitionFrameRateAbs.SetValue(5)

    # Transport layer
    # Packet Size
    camera.GevSCPSPacketSize.SetValue(1500)
    # Inter-Packet Delay
    camera.GevSCPD.SetValue(1000)


    camera.PixelFormat.SetValue("BayerRG8")
    converter = pylon.ImageFormatConverter()

    # converting to opencv bgr format
    # converter.OutputPixelFormat = pylon.PixelType_Mono8
    converter.OutputPixelFormat = pylon.PixelType_RGB16planar
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    return converter, camera



def read(camera, converter):
    grabResult = camera.RetrieveResult(1500, pylon.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        # Access the image data
        image = converter.Convert(grabResult)
        arr = np.ndarray(buffer=image.GetBuffer(), shape=(image.GetHeight(), image.GetWidth(), 3), dtype=np.uint8)
        img = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        # grayImage = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        grabResult.Release()
    return img


def image_treat(image):
    img = cv2.GaussianBlur(image, (3, 3), 0)
    return img


def calc(img, threshold=50):
    # apply thresholding
    cX, cY = 0, 0
    ret, thresh = cv2.threshold(img, threshold, 255, 0)
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    longest_contour = 0
    longest_contour_index = 0
    i = 0
    if contours:
        for contour in contours:
            if longest_contour < contour.shape[0]:
                longest_contour_index = i
                longest_contour = contour.shape[0]
            i += 1

        M = cv2.moments(contours[longest_contour_index])
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
    # plt.figure()
    # plt.imshow(img)
    # # edge detection
    # apply Canny edge detection
    #tight = cv2.Canny(thresh, threshold, 255)

    # calculate the centre of moment
    # cv2.drawContours(img, contours[longest_contour_index], -1, (0, 255, 0), 3)


    return thresh, contours, cX, cY, longest_contour_index


print(f'Camera {SERIAL_NUMBER} is initializing...')
converter, camera = init(DEVICE)
camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)


# Figure
fig = plt.figure(figsize=(8.5, 5.5))
# create two subplots

ax_im1 = fig.add_subplot(3, 2, 1)

ax1_x = fig.add_subplot(3, 2, 3)
ax1_x.set_ylim(250, 275)
ax1_x.set_ylabel('X1 position')

ax1_y = fig.add_subplot(3, 2, 5)
ax1_y.set_ylim(100, 125)
ax1_y.set_ylabel('Y1 position')

img = read(camera, converter)

positionsX1 = deque([], maxlen=120)
positionsY1 = deque([], maxlen=120)

im1 = ax_im1.imshow(img, cmap='jet')
Xpos1, = ax1_x.plot([1], [1], marker='o', markersize=2, color='b', linestyle= '')
Ypos1, = ax1_y.plot([1], [1], marker='o', markersize=2, color='b', linestyle= '')

fig.show()

plt.ion()

while camera.IsGrabbing():
    [p.remove() for p in reversed(ax_im1.patches)]
    img1 = read(camera, converter)
    # img1 = image_treat(img1)
    # thresh1, contours, cX1, cY1, index = calc(img1)
    # positionsX1.append(cX1)
    # positionsY1.append(cY1)
    # im1.set_data(thresh1)
    im1.set_data(img1)


    # circle1 = Circle((cX1, cY1), radius=10, color='black', zorder=10)
    # ax_im1.add_patch(circle1)
    # x1 = list([i for i in range(len(positionsX1))])
    # Xpos1.set_data(x1, positionsX1)
    # Ypos1.set_data(x1, positionsY1)
    #
    # ax1_x.relim()
    # ax1_y.relim()
    # ax1_x.autoscale_view(True, True, True)
    # ax1_y.autoscale_view(True, True, True)
    plt.pause(0.2)

plt.ioff()
fig.show()

# Releasing the resource
camera.StopGrabbing()
