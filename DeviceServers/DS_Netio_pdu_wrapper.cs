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

                // Set up the process to run the Python device server in a new visible terminal
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "cmd.exe";
psi.Arguments = "/k \"title DS_Netio_pdu [" + instanceName + "] && " +
                              "cd /d \"" + pyconlyse + "\\DeviceServers\\power\\netio\" && " +
                              "\\"" + anaconda + "\\\\Scripts\\\\activate.bat\\" " + pyconlyseEnv + " && " +
                              "set DISABLE_ARCHIVE=1 && " +
                              "set DEBUG_INIT_TIMING=1 && set DEBUG_TIMING_THRESHOLD_MS=1 && " +
                              "set DEBUG_FUNCTION_TIMING=1 && set DEBUG_FUNCTION_MIN_MS=1 && " +
                              "echo Starting DS_Netio_pdu device server... && " +
                              "python DS_Netio_pdu.py " + instanceName + "\\"";
                psi.UseShellExecute = true;
                psi.CreateNoWindow = false;
                psi.WindowStyle = ProcessWindowStyle.Normal;

                // Netio PDUs don't need startup delays (no concurrent device conflicts)
                Console.WriteLine("Starting Python device server in new terminal...");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Terminal will remain open for monitoring and manual control.");
                Console.WriteLine("=====================================================");

                // Start the process in a new terminal window
                Process process = Process.Start(psi);
                
                if (process != null)
                {
                    Console.WriteLine("Device server started successfully!");
                    Console.WriteLine("Process ID: " + process.Id);
                    Console.WriteLine("Terminal window title: DS_Netio_pdu [" + instanceName + "]");
                    Console.WriteLine("");
                    Console.WriteLine("The device server is now running in a separate terminal.");
                    Console.WriteLine("You can:");
                    Console.WriteLine("  - Monitor its output in the terminal window");
                    Console.WriteLine("  - Close it manually using Ctrl+C or closing the window");
                    Console.WriteLine("  - Use Astor to manage the device server");
                    
                    return 0; // Success - don't wait for the process to exit
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
