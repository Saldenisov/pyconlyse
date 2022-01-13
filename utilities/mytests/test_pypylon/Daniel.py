import cv2
import matplotlib.pyplot as plt
from pypylon import pylon
import numpy as np

figure = plt.figure()

def init():
    # conecting to the first available camera
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()
    camera.Width = 512
    camera.Height = 512
    camera.OffsetX = 0
    camera.OffsetY = 0
    camera.GainRaw.SetValue(0)
    camera.BlackLevelRaw.SetValue(-30)
    camera.TriggerSource.SetValue("Line1")
    camera.TriggerMode.SetValue("On")
    camera.TriggerDelayAbs.SetValue(185000)
    camera.ExposureTimeAbs.SetValue(15000.0)
    camera.BalanceRatioRaw.SetValue(64)
    camera.AcquisitionFrameRateEnable.SetValue(False)
    camera.AcquisitionFrameRateAbs.SetValue(5)
    camera.PixelFormat.SetValue("BayerRG8")
    converter = pylon.ImageFormatConverter()
    converter.OutputPixelFormat = pylon.PixelType_RGB16packed
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    # Transport layer
    # Packet Size
    camera.GevSCPSPacketSize.SetValue(1500)
    # Inter-Packet Delay
    camera.GevSCPD.SetValue(1000)

    # converting to opencv bgr format


    return camera, converter


camera, converter = init()


camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
while camera.IsGrabbing():
    grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        # Access the image data
        image = converter.Convert(grabResult)
        image = np.ndarray(buffer=image.GetBuffer(), shape=(image.GetHeight(), image.GetWidth(), 3), dtype=np.uint16)
        image2D = image.transpose(2, 0, 1).reshape(-1, image.shape[1])
        shp = (int(image2D.shape[0] / 3), image2D.shape[1], 3)
        image3D = image2D.reshape(np.roll(shp, 1)).transpose(1, 2, 0)



        cv2.imshow('Raw image', image3D)


        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    grabResult.Release()

# Releasing the resource
camera.StopGrabbing()

# destroy all windows
cv2.destroyAllWindows()

