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

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "cmd.exe";
                psi.Arguments = "/k \"title DS_Standa_Motor [" + instanceName + "] && " +
                                  "cd /d \"" + pyconlyse + "\\DeviceServers\\motion\\standa\" && " +
                                  "\"" + anaconda + "\\Scripts\\activate.bat\" " + pyconlyseEnv + " && " +
                                  "echo Starting DS_Standa_Motor device server... && " +
                                  "python DS_Standa_Motor.py " + instanceName + "\"";
                psi.UseShellExecute = true;
                psi.CreateNoWindow = false;
                psi.WindowStyle = ProcessWindowStyle.Normal;

                Console.WriteLine("Starting Python device server in new terminal...");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Terminal will remain open for monitoring and manual control.");
                Console.WriteLine("=====================================================");

                Process process = Process.Start(psi);
                if (process != null)
                {
                    Console.WriteLine("Device server launch command executed.");
                    Console.WriteLine("Process ID: " + process.Id);
                    Console.WriteLine("Terminal window title: DS_Standa_Motor [" + instanceName + "]");
                    return 0;
                }
                else
                {
                    Console.WriteLine("ERROR: Failed to start the Python device server process!");
                    return 1;
                }
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
