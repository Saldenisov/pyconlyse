using System;
using System.Diagnostics;
using System.IO;

namespace DS_DAQmx_Wrapper
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.Title = "DS_DAQmx - Tango Device Server";

            try
            {
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No instance name provided!");
                    Console.WriteLine("Usage: DS_DAQmx.exe [instance_name]");
                    Console.WriteLine("Example: DS_DAQmx.exe 1_DAQMX_1");
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
                Console.WriteLine("DS_DAQmx - Tango Device Server Wrapper");
                Console.WriteLine("=====================================================");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Environment: " + pyconlyseEnv);
                Console.WriteLine("ANACONDA: " + anaconda);
                Console.WriteLine("PYCONLYSE: " + pyconlyse);
                Console.WriteLine("=====================================================");

                string deviceDir = Path.Combine(pyconlyse, @"DeviceServers\control\daqmx");
                string title = "DS_DAQmx [" + instanceName + "]";
                string activatePath = Path.Combine(anaconda, @"Scripts\activate.bat");
                string innerCmd = "cmd /k \"call \"" + activatePath + "\" " + pyconlyseEnv +
                                  " && set DISABLE_ARCHIVE=1" +
                                  " && set PYTHONPATH=" + pyconlyse +
                                  " && echo Starting DS_DAQmx device server... && python DS_DAQmx.py " + instanceName + "\"";

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
                    ProcessStartInfo psiCmd = new ProcessStartInfo();
                    psiCmd.FileName = "cmd.exe";
                    psiCmd.Arguments = "/k \"title " + title + " && cd /d \"" + deviceDir + "\" && \"" + activatePath + "\" " + pyconlyseEnv +
                                       " && set DISABLE_ARCHIVE=1" +
                                       " && set PYTHONPATH=" + pyconlyse +
                                       " && echo Starting DS_DAQmx device server... && python DS_DAQmx.py " + instanceName + "\"";
                    psiCmd.UseShellExecute = true;
                    psiCmd.CreateNoWindow = false;
                    psiCmd.WindowStyle = ProcessWindowStyle.Normal;

                    Console.WriteLine("Starting in a separate terminal window as fallback...");
                    var process = Process.Start(psiCmd);
                    if (process == null)
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
