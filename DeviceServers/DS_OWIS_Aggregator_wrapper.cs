using System;
using System.Diagnostics;
using System.IO;

namespace DS_OWIS_Aggregator_Wrapper
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.Title = "DS_OWIS_Aggregator - Tango Device Server";
            
            try
            {
                // Check if instance name is provided
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No instance name provided!");
                    Console.WriteLine("Usage: DS_OWIS_Aggregator.exe [instance_name]");
                    Console.WriteLine("Example: DS_OWIS_Aggregator.exe 1");
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
                Console.WriteLine("DS_OWIS_Aggregator - Tango Device Server Wrapper");
                Console.WriteLine("=====================================================");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Environment: " + pyconlyseEnv);
                Console.WriteLine("ANACONDA: " + anaconda);
                Console.WriteLine("PYCONLYSE: " + pyconlyse);
                Console.WriteLine("=====================================================");

                // Prepare launch parameters
                string deviceDir = Path.Combine(pyconlyse, @"DeviceServers\motion\owis");
                string title = "DS_OWIS_Aggregator [" + instanceName + "]";
                string activatePath = Path.Combine(anaconda, @"Scripts\activate.bat");

                Console.WriteLine("Starting Python device server in new terminal...");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Terminal will remain open for monitoring and manual control.");
                Console.WriteLine("=====================================================");

                // Launch directly in cmd.exe
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "cmd.exe";
                psi.Arguments = "/k \"title " + title + " && cd /d \"" + deviceDir + "\" && \"" + activatePath + "\" " + pyconlyseEnv +
                               " && python DS_OWIS_Aggregator.py " + instanceName + "\"";
                psi.UseShellExecute = true;
                psi.CreateNoWindow = false;
                psi.WindowStyle = ProcessWindowStyle.Normal;

                Console.WriteLine("Starting device server in terminal...");
                var process = Process.Start(psi);
                if (process != null)
                {
                    Console.WriteLine("Device server started!");
                    Console.WriteLine("Process ID: " + process.Id);
                    return 0;
                }
                else
                {
                    Console.WriteLine("ERROR: Failed to start the device server!");
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
