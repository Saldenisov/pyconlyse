using System;
using System.Diagnostics;
using System.IO;

namespace DS_OWIS_PS90_Wrapper
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.Title = "DS_OWIS_PS90 - Tango Device Server";
            
            try
            {
                // Check if instance name is provided
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No instance name provided!");
                    Console.WriteLine("Usage: DS_OWIS_PS90.exe [instance_name]");
                    Console.WriteLine("Example: DS_OWIS_PS90.exe 1");
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
                Console.WriteLine("DS_OWIS_PS90 - Tango Device Server Wrapper");
                Console.WriteLine("=====================================================");
                Console.WriteLine("Instance: " + instanceName);
                Console.WriteLine("Environment: " + pyconlyseEnv);
                Console.WriteLine("ANACONDA: " + anaconda);
                Console.WriteLine("PYCONLYSE: " + pyconlyse);
                Console.WriteLine("=====================================================");

                // Set up the process to run the Python device server in a new visible terminal
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "cmd.exe";
                psi.Arguments = "/k \"title DS_OWIS_PS90 [" + instanceName + "] && " +
                              "cd /d \"" + pyconlyse + "\\DeviceServers\\motion\\owis\" && " +
                              "\"" + anaconda + "\\Scripts\\activate.bat\" " + pyconlyseEnv + " && " +
                              "echo Starting DS_OWIS_PS90 device server... && " +
                              "python DS_OWIS_PS90.py " + instanceName + "\"";
                psi.UseShellExecute = true;
                psi.CreateNoWindow = false;
                psi.WindowStyle = ProcessWindowStyle.Normal;

                // Add startup delay to prevent concurrent device conflicts  
                int startupDelay = GetStartupDelay("owis");
                
                Console.WriteLine("Starting Python device server in new terminal...");
                Console.WriteLine("Instance: " + instanceName);
                if (startupDelay > 0)
                {
                    Console.WriteLine("Startup delay: " + startupDelay + " seconds (to avoid device conflicts)");
                    Console.WriteLine("Waiting for staggered startup...");
                    System.Threading.Thread.Sleep(startupDelay * 1000);
                    Console.WriteLine("Delay complete, proceeding with launch.");
                }
                Console.WriteLine("Terminal will remain open for monitoring and manual control.");
                Console.WriteLine("=====================================================");

                // Start the process in a new terminal window
                Process process = Process.Start(psi);
                
                if (process != null)
                {
                    Console.WriteLine("Device server started successfully!");
                    Console.WriteLine("Process ID: " + process.Id);
                    Console.WriteLine("Terminal window title: DS_OWIS_PS90 [" + instanceName + "]");
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
        
        static int GetStartupDelay(string deviceType)
        {
            try
            {
                // Simple counter file approach for Windows
                string tempDir = System.IO.Path.GetTempPath();
                string counterFile = System.IO.Path.Combine(tempDir, "pyconlyse_" + deviceType + "_startup_counter.txt");
                
                int counter = 0;
                
                // Try to read existing counter with retry logic
                for (int attempt = 0; attempt < 10; attempt++)
                {
                    try
                    {
                        if (System.IO.File.Exists(counterFile))
                        {
                            string content = System.IO.File.ReadAllText(counterFile);
                            int.TryParse(content, out counter);
                        }
                        
                        // Write incremented counter
                        System.IO.File.WriteAllText(counterFile, (counter + 1).ToString());
                        break;
                    }
                    catch
                    {
                        // File in use, wait and retry
                        System.Threading.Thread.Sleep(100 + attempt * 50);
                    }
                }
                
                int delaySeconds = counter * 5; // 5 seconds per instance
                Console.WriteLine("[Startup Coordinator] This is " + deviceType + " instance #" + (counter + 1));
                Console.WriteLine("[Startup Coordinator] Calculated delay: " + delaySeconds + " seconds");
                
                return delaySeconds;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[Startup Coordinator] Error calculating delay: " + ex.Message);
                return 0; // Default to no delay on error
            }
        }
    }
}