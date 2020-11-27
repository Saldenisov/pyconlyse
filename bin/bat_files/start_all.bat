call start_pdu_netio.bat
ping -n 2 127.0.0.1 >NUL
call start_server.bat
ping -n 3 127.0.0.1 >NUL
call start_basler_cameras.bat
call start_standa_stpmtrs.bat
call start_owis.bat
ping -n 4 127.0.0.1 >NUL
call start_SuperUserGUI.bat