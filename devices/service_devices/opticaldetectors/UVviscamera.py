'''
Created on 18 Mar 2017

@author: Sergey Denisov
'''

import ctypes
from typing import Dict, NewType
from xmlrpc.client import boolean

Error = NewType('MsgError', Dict)

default = Error({'status': False, 'code': 2, 'desription': ''})

def errorcodehandler(code: int):
    error = Error({'status': False, 'code': 2, 'desription': ''})
    return error
    

def Init(LR: ctypes, dir: str) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """
    dirc = ctypes.c_char_p(dir.encode('utf-8'))
    executed = LR.Initialize(dirc)
    return errorcodehandler(executed),  None


def SetAcquisitionMode(LR: ctypes, mode: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    0 - Reserved
    1 - Single scan
    2 - Accumulate
    3 - Kinetics
    4 - Fast Kinetics
    5 - Run Till Abort for non-Frame Transfer
    6 - Frame Transfer
    7 - Run Till Abort for Frame Transfer
    8 - Reserved
    9 - Time Delayed Integration
    """
    if not error['status']:
        modec = ctypes.c_int32(mode)
        executed = LR.SetAcquisitionMode(modec)
        return errorcodehandler(executed), None
    else:
        return error


def SetExposureTime(LR: ctypes, time: float, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """
    if not error['status']:
        timec = ctypes.c_float(time)
        executed = LR.SetExposureTime(timec)
        return errorcodehandler(executed), None
    else:
        return error
    
    
def GetNumberHSSpeeds(LR: ctypes, type: int, channel: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, number)
    EMP-amp = 0
    Conventional Amp = 1
    """ 
    if not error['status']:
        typec = ctypes.c_int32(type)
        channelc = ctypes.c_int32(channel)
        n = ctypes.c_int(0)
        number = ctypes.pointer(n)
        executed = LR.GetNumberHSSpeeds(channelc, typec, number)
        return errorcodehandler(executed), number.contents.value
    else:
        return error
    

def SetHSSpeed(LR: ctypes, type: int, index: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    EMP-amp = 0
    Conventional Amp = 1
    """ 
    if not error['status']:
        typec = ctypes.c_int32(type)
        indexc = ctypes.c_int32(index)
        executed = LR.SetHSSpeed(typec, indexc)
        return errorcodehandler(executed), None
    else:
        return error


def GetHSSpeed(LR: ctypes, type: int, index: int, channel: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, speed)
    EMP-amp = 0
    Conventional Amp = 1
    """ 
    if not error['status']:
        typec = ctypes.c_int32(type)
        indexc = ctypes.c_int32(index)
        channelc = ctypes.c_int32(channel)
        v = ctypes.c_float(0)
        speed= ctypes.pointer(v)
        executed = LR.GetHSSpeed(channelc, typec, indexc, speed)
        return errorcodehandler(executed), speed.contents.value
    else:
        return error


def GetNumberVSSpeeds(LR: ctypes, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, number)
    """ 
    if not error['status']:
        n = ctypes.c_int(0)
        number = ctypes.pointer(n)
        executed = LR.GetNumberVSSpeeds(number)
        return errorcodehandler(executed), number.contents.value
    else:
        return error


def SetVSSpeed(LR: ctypes, index: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """ 
    if not error['status']:
        indexc = ctypes.c_int32(index)
        executed = LR.SetVSSpeed(indexc)
        return errorcodehandler(executed), None
    else:
        return error


def GetVSSpeed(LR: ctypes, index: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, speed)
    """ 
    if not error['status']:
        indexc = ctypes.c_int32(index)
        v = ctypes.c_float(0)
        speed= ctypes.pointer(v)
        executed = LR.GetVSSpeed(indexc, speed)
        return errorcodehandler(executed), speed.contents.value
    else:
        return error
    

def GetDetector(LR: ctypes,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, tuple(xpixels, ypixels)
    """ 
    if not error['status']:
        xpix = ctypes.c_int32(0)
        ypix = ctypes.c_int32(0)
        xpixels= ctypes.pointer(xpix)
        ypixels= ctypes.pointer(xpix)
        executed = LR.GetDetector(xpixels, ypixels)
        return errorcodehandler(executed), (xpixels.contents.value, ypixels.contents.value)
    else:
        return error


def GetNumberPreAmpGains(LR: ctypes,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, number)
    """
    if not error['status']:
        n = ctypes.c_int32(0)
        number= ctypes.pointer(n)
        executed = LR.GetNumberPreAmpGains(number)
        return errorcodehandler(executed), number.contents.value
    else:
        return error
    
def SetADChannel(LR: ctypes, channel: int,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """
    if not error['status']:
        channelc = ctypes.c_int32(channel)
        executed = LR.SetADChannel(channelc)
        return errorcodehandler(executed), None
    else:
        return error
    
    
def SetPreAmpGain(LR: ctypes, index: int,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """
    if not error['status']:
        indexc = ctypes.c_int32(index)
        executed = LR.SetPreAmpGain(indexc)
        return errorcodehandler(executed), None
    else:
        return error  

   
def GetPreAmpGain(LR: ctypes, index: int,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, gain)
    """
    if not error['status']:
        indexc = ctypes.c_int32(index)
        v = ctypes.c_float(0)
        gain = ctypes.pointer(v)
        executed = LR.GetPreAmpGain(indexc, gain)
        return errorcodehandler(executed), gain.contents.value
    else:
        return error  
        

def GetNumberADChannels(LR: ctypes, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, number)
    """
    if not error['status']:
        v = ctypes.c_int32(0)
        number = ctypes.pointer(v)
        executed = LR.GetNumberADChannels(number)
        return errorcodehandler(executed), number.contents.value
    else:
        return error    
    
    
def SetTriggerMode(LR: ctypes, mode: int,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    Mode:
    0 - Internal
    1- External
    2-5 - N/A
    6 - External Start
    7 - External Exposure(Bulb)
    8 - N/A
    9 - External FVB EM
    10 - Software
    11 - N/A
    12 - External Charge Shifting
    """
    if not error['status']:
        modec = ctypes.c_int32(mode)
        executed = LR.SetTriggerMode(modec)
        return errorcodehandler(executed), None
    else:
        return error  


def SetFastExtTrigger(LR: ctypes, mode: boolean,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """
    if not error['status']:
        modec = ctypes.c_int32(int(mode))
        executed = LR.SetFastExtTrigger(modec)
        return errorcodehandler(executed), None
    else:
        return error 


def SetReadMode(LR: ctypes, mode: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    Mode:
    0 - Full Vertical Binning
    1 - Multi-Track
    2 - Random-Track
    3 - Single-Track
    4 - Image
    """
    if not error['status']:
        modec = ctypes.c_int32(mode)
        executed = LR.SetReadMode(modec)
        return errorcodehandler(executed), None
    else:
        return error
    

def SetMultiTrack(LR: ctypes, number: int, height: int, offset: int, error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, (bottom, gap))
    """  
    if not error['status']:
        bot = ctypes.c_int32(0)
        g = ctypes.c_int32(0)
        bottom = ctypes.pointer(bot)
        gap = ctypes.pointer(g)
        numberc = ctypes.c_int32(number)
        heightc= ctypes.c_int32(height)
        offsetc = ctypes.c_int32(offset)
        executed = LR.SetMultiTrack(numberc, heightc, offsetc, bottom, gap)
        return errorcodehandler(executed), (bottom.contents.value, gap.contents.value)
    else:
        return error


def SetBaselineClamp(LR: ctypes, state: boolean,  error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """
    if not error['status']:
        statec = ctypes.c_int32(int(state))
        executed = LR.SetBaselineClamp(statec)
        return errorcodehandler(executed), None
    else:
        return error  


def GetAcquisitionTimings(LR: ctypes, exposure_in: float, accumulate_in: float, kinetics_in: float,
                          error: Error=default) -> tuple:
    """
    Returns tuple(MsgError type, (exposure, accumulate, kinetics))
    """     
    if not error['status']:
        exp = ctypes.c_float(exposure_in)
        acc = ctypes.c_float(accumulate_in)
        kin = ctypes.c_float(kinetics_in)
        exposure = ctypes.pointer(exp)
        accumulate = ctypes.pointer(acc)
        kinetics = ctypes.pointer(kin)

        executed = LR.GetAcquisitionTimings(exposure, accumulate, kinetics)
        return errorcodehandler(executed), None
    else:
        return error    

def ShutDown(LR: ctypes) -> tuple:
    """
    Returns tuple(MsgError type, None)
    """     

    executed = LR.ShutDown()
    return errorcodehandler(executed), None









       
LRdll = 'G:/SD/TRANCON-2015/DLL/atmcd32d.dll'

#C:/Users/Sergey Denisov/Dropbox/LCP/Soft/Python/transient-Python/DLLs/'

LR = ctypes.WinDLL(LRdll)
type = 0 #EM Amp
mode = 1 #External
readout_mode = 1 # Multi-Track
timing = 0.0001

init = Init(LR, '')

sacqmode = SetAcquisitionMode(LR, 3, init[0])

gexptime = SetExposureTime(LR, timing, sacqmode[0])

gnumHSspeeds = GetNumberHSSpeeds(LR, type, 1, gexptime[0])
print('GetNumberHSSpeeds: %d' % gnumHSspeeds[1])

sHSspeed = SetHSSpeed(LR, type, 0, gnumHSspeeds[0])

gHSspeed = GetHSSpeed(LR, type, 0, 1, sHSspeed[0])
print('GetHSSpeed: %d' % gHSspeed[1])

gnumVSspeeds = GetNumberVSSpeeds(LR, gHSspeed[0])
print('GetNumberVSSpeeds: %d' % gnumVSspeeds[1])

sVSspeed = SetVSSpeed(LR, 1, gnumVSspeeds[0])

gVSspeed = GetVSSpeed(LR, 1, sVSspeed[0])
print('GetVSSpeed: %d' % gVSspeed[1])

gdet = GetDetector(LR, gVSspeed[0])

gnumpreamp = GetNumberPreAmpGains(LR, gdet[0])
print('GetNumberPreAmpGains: %d' % gnumpreamp[1])

sADchan = SetADChannel(LR, 1, gnumpreamp[0])

spreampgain = SetPreAmpGain(LR, 0, sADchan[0])

gpreampgain = GetPreAmpGain(LR, 0, spreampgain[0])
print('GetPreAmpGain: %d' % gpreampgain[1])

gnumADchan = GetNumberADChannels(LR, gpreampgain[0])
print('GetNumberADChannels: %d' % gnumADchan[1])

striggermode = SetTriggerMode(LR, mode, gnumADchan[0])

sfastextrig = SetFastExtTrigger(LR, False, striggermode[0])

sreadmode = SetReadMode(LR, mode, sfastextrig[0])

smulttrack = SetMultiTrack(LR, 2, 128, 0, sreadmode[0])

sbaselineclamp = SetBaselineClamp(LR, True, smulttrack[0])

print(sacqmode[0])
gaqtiming = GetAcquisitionTimings(LR, timing, 1, 2, sbaselineclamp[0])

ShutDown(LR)