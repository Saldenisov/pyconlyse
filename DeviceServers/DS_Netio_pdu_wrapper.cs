using System;
using System.Diagnostics;
using System.IO;

namespace DS_Netio_pdu_Wrapper
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.Title = "DS_Netio_pdu - Tango Device Server";
            
            try
            {
                // Check if instance name is provided
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No instance name provided!");
                    Console.WriteLine("Usage: DS_Netio_pdu.exe [instance_name]");
                    Console.WriteLine("Example: DS_Netio_pdu.exe 1_V0");
                    return 1;
                }

                string instanceName = args[0];
                
                // Get environment variables
                string anaconda = Environment.GetEnvironmentVariable("ANACONDA");
                string pyconlyse = Environment.GetEnvironmentVariable("PYCONLYSE");
                string pyconlyseEnv = Environment.GetEnvironmentVariable("PYCONLYSE_ENV") ?? "pyconlyse39";

                // Validate environment variables
                if (string.IsNullOrEmpty(anaconda))
                {
                    Console.WriteLine("ERROR: ANACONDA environment variable not set!");
                    Console.WriteLine("Please set ANACONDA to your Anaconda installation directory");
                    return 1;
                }

                if (string.IsNullOrEmpty(pyconlyse))
                {
                    Console.WriteLine("ERROR: PYCONLYSE environment variable not set!");
                    Console.WriteLine("Please set PYCONLYSE to your PyConlyse project directory");
                    return 1;
                }

                Console.WriteLine("=====================================================");
                Console.WriteLine("DS_Netio_pdu - Tango Device Server Wrapper");
                Console.WriteLine("=====================================================");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Environment: " + pyconlyseEnv);
                Console.WriteLine("ANACONDA: " + anaconda);
                Console.WriteLine("PYCONLYSE: " + pyconlyse);
                Console.WriteLine("=====================================================");

// The executable is the Astor entry point. Delegate to the shared launcher so
// that console output is mirrored to the convention used by Starter.DevReadLog.
string deviceDir = Path.Combine(pyconlyse, @"DeviceServers\power\netio");
string title = "DS_Netio_pdu [" + instanceName + "]";
string launcherPath = Path.Combine(pyconlyse, @"DeviceServers\run_logged_server.cmd");
string runnerArgs = "call \"" + launcherPath + "\" \"DS_Netio_pdu\" \"" +
                    instanceName + "\" \"" + deviceDir + "\" \"DS_Netio_pdu.py\" " +
                    "\"DISABLE_ARCHIVE=1\"";

// Try Windows Terminal tab first
bool launched = false;
try
{
    ProcessStartInfo psiWT = new ProcessStartInfo();
    psiWT.FileName = "wt.exe";
    psiWT.Arguments = "-w 0 nt --title \"" + title + "\" -d \"" + deviceDir + "\" cmd /k " + runnerArgs;
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
    psiCmd.Arguments = "/k " + runnerArgs;
    psiCmd.UseShellExecute = true;
    psiCmd.CreateNoWindow = false;
    psiCmd.WindowStyle = ProcessWindowStyle.Normal;

    Console.WriteLine("Starting in a separate terminal window as fallback...");
    var process = Process.Start(psiCmd);
    if (process != null)
    {
        Console.WriteLine("Device server started successfully!");
        Console.WriteLine("Process ID: " + process.Id);
        Console.WriteLine("Terminal window title: " + title);
        Console.WriteLine("");
        Console.WriteLine("The device server is now running in a terminal.");
        Console.WriteLine("You can monitor its output and close it manually.");
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
