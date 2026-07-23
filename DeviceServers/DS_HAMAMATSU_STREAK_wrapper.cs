using System;
using System.Diagnostics;
using System.IO;

class Program
{
    static int Main(string[] args)
    {
        string instanceName = args.Length > 0 ? args[0] : "1_hamamatsu_streak_main";
        string pyconlyse = Environment.GetEnvironmentVariable("PYCONLYSE") ?? @"C:\dev\pyconlyse";
        string launcher = Path.Combine(pyconlyse, @"DeviceServers\DS_HAMAMATSU_STREAK.bat");

        if (!File.Exists(launcher))
        {
            Console.Error.WriteLine("Hamamatsu launcher is missing: " + launcher);
            return 1;
        }

        var process = Process.Start(new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = "/c call \"" + launcher + "\" " + instanceName,
            UseShellExecute = false,
        });
        process.WaitForExit();
        return process.ExitCode;
    }
}
