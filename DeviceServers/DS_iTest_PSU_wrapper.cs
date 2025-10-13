using System;
using System.Diagnostics;
using System.IO;

namespace DS_iTest_PSU_Wrapper
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.Title = "DS_iTest_PSU - Tango Device Server";
            
            try
            {
                // Check if instance name is provided
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No instance name provided!");
                    Console.WriteLine("Usage: DS_iTest_PSU.exe [instance_name]");
                    Console.WriteLine("Example: DS_iTest_PSU.exe 1_iTest");
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
                Console.WriteLine("DS_iTest_PSU - Tango Device Server Wrapper");
                Console.WriteLine("=====================================================");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Environment: " + pyconlyseEnv);
                Console.WriteLine("ANACONDA: " + anaconda);
                Console.WriteLine("PYCONLYSE: " + pyconlyse);
                Console.WriteLine("=====================================================");

                // Prepare launch parameters
                string deviceDir = Path.Combine(pyconlyse, @"DeviceServers\power\iTest");
                string title = "DS_iTest_PSU [" + instanceName + "]";
                string activatePath = Path.Combine(anaconda, @"Scripts\activate.bat");
                string innerCmd = "cmd /k \"call \"" + activatePath + "\" " + pyconlyseEnv +
                                  " && set DISABLE_ARCHIVE=1" +
                                  " && set PYTHONPATH=" + pyconlyse +
                                  " && echo Starting DS_iTest_PSU device server... && python DS_itest_psu.py " + instanceName + "\"";

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
                                       " && set DISABLE_ARCHIVE=1" +
                                       " && set PYTHONPATH=" + pyconlyse +
                                       " && echo Starting DS_iTest_PSU device server... && python DS_itest_psu.py " + instanceName + "\"";
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
