from collections import deque

import cv2
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from pypylon import pylon, genicam

countOfImagesToGrab = 1
maxCamerasToUse = 2

# Init all camera
try:
    # Get the transport layer factory.
    tlFactory = pylon.TlFactory.GetInstance()

    # Get all attached devices and exit application if no device is found.
    devices = tlFactory.EnumerateDevices()
    if len(devices) == 0:
        raise pylon.RUNTIME_EXCEPTION("No camera present.")

    # Create an array of instant cameras for the found devices and avoid exceeding a maximum number of devices.
    cameras = pylon.InstantCameraArray(min(len(devices), maxCamerasToUse))

except genicam.GenericException as e:
    # Error handling
    print("An exception occurred. {}".format(e))
    exitCode = 1

OffSet = {1: {'X': 310, 'Y': 290}, 0: {'X': 270, 'Y': 120}}

test = {}

def init(camera_id, camera, devices):
    # conecting to the first available camera
    #camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    test[camera_id] = camera
    camera.Attach(tlFactory.CreateDevice(devices[camera_id]))
    camera.Open()
    camera.StopGrabbing()
    b = camera.IsOpen()
    a = camera.GetDeviceInfo().GetModelName()
    b = camera.GetDeviceInfo().GetSerialNumber()
    c = camera.GetDeviceInfo().GetIpAddress()
    camera.GetDeviceInfo().SetFriendlyName('Camera1'.format('utf-8'))
    d = camera.GetDeviceInfo().GetFriendlyName()
    camera.Width = 550
    e = getattr(camera, 'Width').GetValue()
    camera.Height = 550
    camera.OffsetX.SetValue(OffSet[camera_id]['X'])
    camera.OffsetY = OffSet[camera_id]['Y']
    camera.GainAuto = 'Off'
    camera.GainRaw = 0
    camera.BlackLevelRaw.SetValue(-30)
    camera.TriggerSource = "Line1"
    camera.trigger_mode.SetValue("On")
    camera.TriggerDelayAbs.SetValue(185000)
    camera.ExposureTimeAbs.SetValue(15000.0)
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

    return converter


def read(camera, converter):
    grabResult = camera.RetrieveResult(1500, pylon.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        # Access the image data
        image = converter.Convert(grabResult)
        #img = imutils.resize(image.GetArray(), width=480, height=480)
        # if cv2.waitKey(1) & 0xFF == ord('q'):
        # break
    grabResult.Release()
    arr = image.GetArray()
    return arr


def image_treat(image):
    img = cv2.GaussianBlur(image, (3, 3), 0)
    return img


def calc(img, threshold=50):
    # apply thresholding

    ret, thresh = cv2.threshold(img, threshold, 255, 0)
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    longest_contour = 0
    longest_contour_index = 0
    i = 0
    for contour in contours:
        if longest_contour < contour.shape[0]:
            longest_contour_index = i
            longest_contour = contour.shape[0]
        i += 1
    #plt.figure()
    #plt.imshow(img)
    # edge detection
    # apply Canny edge detection
    #tight = cv2.Canny(thresh, threshold, 255)

    # calculate the centre of moment
    #cv2.drawContours(img, contours[longest_contour_index], -1, (0, 255, 0), 3)
    M = cv2.moments(contours[longest_contour_index])
    if M["m00"] != 0:
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])
    else:
        cX, cY = 0, 0
    return thresh, contours, cX, cY


converters = []

for i, camera in enumerate(cameras):
    print(f'Camera {i} is initializing')
    converters.append(init(i, camera, devices))
    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
#cameras.StartGrabbing(pylon.GrabStrategy_LatestImageOnly, pylon.GrabLoop_ProvidedByInstantCamera)
one, two = 1, 0
camera1 = cameras[one]
converter1 = converters[one]
camera2 = cameras[two]
converter2 = converters[two]


# Figure
fig = plt.figure(figsize=(8.5, 5.5))
# create two subplots

ax_im1 = fig.add_subplot(3, 2, 1)
ax_im2 = fig.add_subplot(3, 2, 2)

ax1_x = fig.add_subplot(3, 2, 3)
ax1_x.set_ylim(275, 300)
ax1_x.set_ylabel('X1 position')

ax2_x = fig.add_subplot(3, 2, 4)
ax2_x.set_ylim(250, 275)
ax2_x.set_ylabel('X2 position')

ax1_y = fig.add_subplot(3, 2, 5)
ax1_y.set_ylim(260, 285)
ax1_y.set_ylabel('Y1 position')

ax2_y = fig.add_subplot(3, 2, 6)
ax2_y.set_ylim(260, 285)
ax2_y.set_ylabel('Y2 position')

# create two image plots
img1 = read(camera1, converter1)
img2 = read(camera2, converter2)

positionsX1 = deque([], maxlen=120)
positionsX2 = deque([], maxlen=120)
positionsY1 = deque([], maxlen=120)
positionsY2 = deque([], maxlen=120)

im1_1 = ax_im1.imshow(calc(img1)[0], cmap='gray', vmin=0, vmax=255)
im1_2 = ax_im1.imshow(img1, cmap='gray', vmin=0, vmax=255, alpha=0.6)
im2_1 = ax_im2.imshow(calc(img1)[0], cmap='gray', vmin=0, vmax=255)
im2_2 = ax_im2.imshow(img2, cmap='gray', vmin=0, vmax=255, alpha=0.6)
Xpos1, = ax1_x.plot([1], [1], marker='o', markersize=2, color='b', linestyle= '')
Xpos2, = ax2_x.plot([1], [1], marker='o', markersize=2, color='b', linestyle= '')
Ypos1, = ax1_y.plot([1], [1], marker='o', markersize=2, color='b', linestyle= '')
Ypos2, = ax2_y.plot([1], [1], marker='o', markersize=2, color='b', linestyle= '')

fig.show()

plt.ion()

while camera1.IsGrabbing():
    [p.remove() for p in reversed(ax_im1.patches)]
    [p.remove() for p in reversed(ax_im2.patches)]
    img1 = read(camera1, converter1)
    img2 = read(camera2, converter2)
    img1 = image_treat(img1)
    img2 = image_treat(img2)
    thresh1, contours1, cX1, cY1 = calc(img1)
    thresh2, contours2, cX2, cY2 = calc(img2)
    positionsX1.append(cX1)
    positionsX2.append(cX2)
    positionsY1.append(cY1)
    positionsY2.append(cY2)
    im1_1.set_data(thresh1)
    im1_2.set_data(img1)
    im2_1.set_data(thresh2)
    im2_2.set_data(img2)

    circle1 = Circle((cX1, cY1), radius=10, color='black', zorder=10)
    circle2 = Circle((cX2, cY2), radius=10, color='black', zorder=10)
    ax_im1.add_patch(circle1)
    ax_im2.add_patch(circle2)
    x1 = list([i for i in range(len(positionsX1))])
    x2 = list([i for i in range(len(positionsX2))])
    Xpos1.set_data(x1, positionsX1)
    Xpos2.set_data(x2, positionsX2)
    Ypos1.set_data(x1, positionsY1)
    Ypos2.set_data(x2, positionsY2)

    ax1_x.relim()
    ax2_x.relim()
    ax1_y.relim()
    ax2_y.relim()
    ax1_x.autoscale_view(True, True, True)
    ax1_y.autoscale_view(True, True, True)
    ax2_x.autoscale_view(True, True, True)
    ax2_y.autoscale_view(True, True, True)
    plt.pause(0.2)

plt.ioff()
fig.show()

# Releasing the resource
camera.StopGrabbing()
