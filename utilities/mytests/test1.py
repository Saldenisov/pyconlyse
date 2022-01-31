from Lima import Andor
from lima import Core

cam = Andor.Camera("/usr/local/etc/andor", 0)
hwint = Andor.Interface(cam)
ct = Core.CtControl(hwint)

acq = ct.acquisition()

# configure some hw parameters
hwint.setTemperatureSP(-30)
hwint.setCooler(True)


# set some low level configuration
hwint.setPGain(2)
hwint.setCooler(True)
hwint.setFanMode(cam.FAN_ON_FULL)
hwint.setHighCapacity(cam.HIGH_SENSITIVITY)
hwint.setBaselineClamp(cam.BLCLAMP_ENABLED)
hwint.setFastExtTrigger(False)
hwint.setShutterLevel(1)


# setting new file parameters and autosaving mode
saving=ct.saving()

pars=saving.getParameters()
pars.directory='/buffer/lcb18012/opisg/test_lima'
pars.prefix='test1_'
pars.suffix='.edf'
pars.fileFormat=Core.CtSaving.EDF
pars.savingMode=Core.CtSaving.AutoFrame
saving.setParameters(pars)

# set accumulation mode

acq_pars= acq.getPars()

#0-normal,1-concatenation,2-accumu
acq_pars.acqMode = 2
acq_pars.accMaxExpoTime = 0.05
acq_pars.acqExpoTime =1
acq_pars.acqNbFrames = 1

acq.setPars(acq_pars)
# here we should have 21 accumalated images per frame
print(acq.getAccNbFrames())

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