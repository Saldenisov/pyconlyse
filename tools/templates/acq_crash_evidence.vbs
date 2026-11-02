Option Explicit
On Error Resume Next
Dim service, events, item, count, message
Set service = GetObject("winmgmts:\\.\root\cimv2")
If Err.Number <> 0 Then
  WScript.Echo "WMI_ERROR|" & Err.Number & "|" & Err.Description
  WScript.Quit 2
End If
' Read-only Application errors for the incident date; no process control.
Set events = service.ExecQuery("SELECT * FROM Win32_NTLogEvent WHERE Logfile='Application' AND EventType=1 AND TimeGenerated >= '20261102000000.000000+060'", "WQL", 48)
If Err.Number <> 0 Then
  WScript.Echo "EVENT_QUERY_ERROR|" & Err.Number & "|" & Err.Description
  WScript.Quit 3
End If
count = 0
For Each item In events
  message = ""
  If Not IsNull(item.Message) Then message = Left(Replace(Replace(item.Message, vbCr, " "), vbLf, " "), 6000)
  WScript.Echo "APPLICATION_ERROR|" & item.RecordNumber & "|" & item.TimeGenerated & "|" & item.EventCode & "|" & item.SourceName & "|" & message
  count = count + 1
  If count >= 50 Then Exit For
Next
WScript.Echo "READ_ONLY_COMPLETED|records=" & count
