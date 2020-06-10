from pypylon import pylon, genicam
countOfImagesToGrab = 1
maxCamerasToUse = 2

# The exit code of the sample application.
exitCode = 0

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
    a = cameras[0]
    a.Width = 550
    a = 0
except genicam.GenericException as e:
    # Error handling
    print("An exception occurred. {}".format(e))
    exitCode = 1