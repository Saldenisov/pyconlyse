using System;
using System.Diagnostics;
using System.IO;

namespace DS_Standa_Motor_Wrapper
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.Title = "DS_Standa_Motor - Tango Device Server";
            
            try
            {
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No instance name provided!");
                    Console.WriteLine("Usage: DS_Standa_Motor.exe [instance_name]");
                    Console.WriteLine("Example: DS_Standa_Motor.exe 1_MotorX_V0");
                    return 1;
                }

                string instanceName = args[0];

                string anaconda = Environment.GetEnvironmentVariable("ANACONDA");
                string pyconlyse = Environment.GetEnvironmentVariable("PYCONLYSE");
                string pyconlyseEnv = Environment.GetEnvironmentVariable("PYCONLYSE_ENV") ?? "pyconlyse39";

                if (string.IsNullOrEmpty(anaconda))
                {
                    Console.WriteLine("ERROR: ANACONDA environment variable not set!");
                    return 1;
                }
                if (string.IsNullOrEmpty(pyconlyse))
                {
                    Console.WriteLine("ERROR: PYCONLYSE environment variable not set!");
                    return 1;
                }

                Console.WriteLine("=====================================================");
                Console.WriteLine("DS_Standa_Motor - Tango Device Server Wrapper");
                Console.WriteLine("=====================================================");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Environment: " + pyconlyseEnv);
                Console.WriteLine("ANACONDA: " + anaconda);
                Console.WriteLine("PYCONLYSE: " + pyconlyse);
                Console.WriteLine("=====================================================");

// Prepare launch parameters
string deviceDir = Path.Combine(pyconlyse, @"DeviceServers\motion\standa");
string title = "DS_Standa_Motor [" + instanceName + "]";
string activatePath = Path.Combine(anaconda, @"Scripts\activate.bat");
string innerCmd = "cmd /k \"call \"" + activatePath + "\" " + pyconlyseEnv +
                  " && set DISABLE_ARCHIVE=1 && set DEBUG_INIT_TIMING=1 && set DEBUG_TIMING_THRESHOLD_MS=1 && set DEBUG_FUNCTION_TIMING=1 && set DEBUG_FUNCTION_MIN_MS=1" +
                  " && echo Starting DS_Standa_Motor device server... && python DS_Standa_Motor.py " + instanceName + "\"";

// Try Windows Terminal tab first
bool launched = false;
try
{
    ProcessStartInfo psiWT = new ProcessStartInfo();
    psiWT.FileName = "wt.exe";
    psiWT.Arguments = "-w 0 nt --title \"" + title + "\" -d \"" + deviceDir + "\" " + innerCmd;
    psiWT.UseShellExecute = true;
    psiWT.CreateNoWindow = false;
    psiWT.WindowStyle = ProcessWindowStyle.Normal;

    Console.WriteLine("Attempting to launch in Windows Terminal tab...");
    var pwt = Process.Start(psiWT);
    if (pwt != null)
    {
        Console.WriteLine("Launched in Windows Terminal tab.");
        launched = true;
    }
}
catch (Exception ex)
{
    Console.WriteLine("Windows Terminal launch failed: " + ex.Message);
}

if (!launched)
{
    // Fallback to separate Command Prompt window
    ProcessStartInfo psiCmd = new ProcessStartInfo();
    psiCmd.FileName = "cmd.exe";
    psiCmd.Arguments = "/k \"title " + title + " && cd /d \"" + deviceDir + "\" && \"" + activatePath + "\" " + pyconlyseEnv +
                       " && set DISABLE_ARCHIVE=1 && set DEBUG_INIT_TIMING=1 && set DEBUG_TIMING_THRESHOLD_MS=1 && set DEBUG_FUNCTION_TIMING=1 && set DEBUG_FUNCTION_MIN_MS=1" +
                       " && echo Starting DS_Standa_Motor device server... && python DS_Standa_Motor.py " + instanceName + "\"";
    psiCmd.UseShellExecute = true;
    psiCmd.CreateNoWindow = false;
    psiCmd.WindowStyle = ProcessWindowStyle.Normal;

    Console.WriteLine("Starting in a separate terminal window as fallback...");
    var process = Process.Start(psiCmd);
    if (process != null)
    {
        Console.WriteLine("Device server launch command executed.");
        Console.WriteLine("Process ID: " + process.Id);
        Console.WriteLine("Terminal window title: " + title);
        return 0;
    }
    else
    {
        Console.WriteLine("ERROR: Failed to start the Python device server process!");
        return 1;
    }
}

return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine("EXCEPTION: " + ex.Message);
                Console.WriteLine("Stack Trace: " + ex.StackTrace);
                return 1;
            }
        }
    }
}
