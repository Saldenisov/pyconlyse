using System;
using System.Diagnostics;
using System.IO;

internal static class Program
{
    private static int Main(string[] args)
    {
        var batch = Path.Combine(AppContext.BaseDirectory, "DS_DG645.bat");
        if (!File.Exists(batch))
        {
            return 2;
        }

        var instance = args.Length > 0 ? args[0] : "1_DG645";
        var command = "/c call \"" + batch + "\" " + instance;
        Process.Start(new ProcessStartInfo(Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe", command)
        {
            CreateNoWindow = true,
            UseShellExecute = false,
            WorkingDirectory = AppContext.BaseDirectory,
        });
        return 0;
    }
}
