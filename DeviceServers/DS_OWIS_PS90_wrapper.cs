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

// Prepare launch parameters
string deviceDir = Path.Combine(pyconlyse, @"DeviceServers\motion\owis");
string title = "DS_OWIS_PS90 [" + instanceName + "]";
string activatePath = Path.Combine(anaconda, @"Scripts\activate.bat");
string innerCmd = "cmd /k \"call \"" + activatePath + "\" " + pyconlyseEnv +
                  " && echo Starting DS_OWIS_PS90 device server... && python DS_OWIS_PS90.py " + instanceName + "\"";

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
                       " && echo Starting DS_OWIS_PS90 device server... && python DS_OWIS_PS90.py " + instanceName + "\"";
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