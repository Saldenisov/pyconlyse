@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO Starting STANDA axes
set list=1_MM1_X 2_MM1_Y 3_MM2_X 4_MM2_Y 5_MM3_X 6_MM3_Y 7_DV01 8_DV02 9_DV03 10_DV04 11_S1 12_S2 13_S3 14_F1 15_L-2_1 16_MM4_X 17_MM4_Y 18_OPA_X 19_OPA_Y 20_TS_1 21_TS_2 22_DE1 23_DE2 24_MME_X 25_MME_Y
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\STANDA & conda activate %PYCONLYSE_ENV% & python DS_Standa_Motor.py %%x"
timeout 1)
