from lima import Basler
from lima import Core

#----------------------------------------+
#                        packet-size     |
#                                        |
#-------------------------------------+  |
#              inter-packet delay     |  |
#                                     |  |
#----------------------------------+  |  |
#      frame-transmission delay    |  |  |
#                                  |  |  |
#--------------------+             |  |  |
# cam ip or hostname |             |  |  |
#                    v             v  v  v
cam = Basler.Camera('192.168.1.1', 0, 0, 8000)

hwint = Basler.Interface(cam)
ct = Core.CtControl(hwint)

acq = ct.acquisition()


# set and test video
#

video=ct.video()
video.setMode(Core.RGB24)
video.startLive()
video.stopLive()
video_img = video.getLastImage()

# set and test an acquisition
#

# setting new file parameters and autosaving mode
saving=ct.saving()

pars=saving.getParameters()
pars.directory='/buffer/lcb18012/opisg/test_lima'
pars.prefix='test1_'
pars.suffix='.edf'
pars.fileFormat=Core.CtSaving.TIFF
pars.savingMode=Core.CtSaving.AutoFrame
saving.setParameters(pars)

# now ask for 2 sec. exposure and 10 frames
acq.setAcqExpoTime(2)
acq.setNbImages(10)

ct.prepareAcq()
ct.startAcq()

# wait for last image (#9) ready
lastimg = ct.getStatus().ImageCounters.LastImageReady
while lastimg !=9:
  time.sleep(1)
  lastimg = ct.getStatus().ImageCounters.LastImageReady

# read the first image
im0 = ct.ReadImage(0)