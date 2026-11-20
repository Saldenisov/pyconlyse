using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

// Starter owns this process. Closing its job handle also releases the Python child.
internal static class Program
{
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr MinWorkingSet, MaxWorkingSet;
        public uint ActiveProcesses;
        public UIntPtr Affinity;
        public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct IoCounters {
        public ulong ReadOperations, WriteOperations, OtherOperations, ReadBytes, WriteBytes, OtherBytes;
    }
    [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr security, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int kind, ref ExtendedLimits limits, uint length);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    static readonly object LogLock = new object();

    static int Main(string[] args)
    {
        IntPtr job = IntPtr.Zero;
        Process child = null;
        string log = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "DS_TOPAS.log");
        try {
            var configPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "DS_TOPAS.runtime.json");
            var config = new JavaScriptSerializer().Deserialize<Dictionary<string, string>>(File.ReadAllText(configPath));
            string python = config["python"], root = config["root"];
            if (!Path.IsPathRooted(python) || !File.Exists(python) || !Path.IsPathRooted(root) || !Directory.Exists(root))
                throw new InvalidOperationException("Configure absolute Python and release paths");
            if (args.Length == 0) throw new ArgumentException("Supply the Tango server instance");
            foreach (string argument in args)
                if (!Regex.IsMatch(argument, @"^[A-Za-z0-9_.:/=,+-]+$")) throw new ArgumentException("Invalid server argument");
            job = CreateJobObject(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw new Win32Exception();
            var limits = new ExtendedLimits();
            limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(limits))) throw new Win32Exception();
            var start = new ProcessStartInfo(python, "-u -m DeviceServers.lasers.topas.DS_TOPAS " + String.Join(" ", args)) {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            start.EnvironmentVariables["TANGO_HOST"] = config["tango_host"];
            start.EnvironmentVariables["PYTHONUTF8"] = "1";
            child = Process.Start(start);
            if (child == null) throw new InvalidOperationException("Python did not start");
            if (!AssignProcessToJobObject(job, child.Handle)) {
                child.Kill();
                throw new Win32Exception();
            }
            Action<string> append = line => {
                if (line != null) lock (LogLock) File.AppendAllText(log, DateTime.UtcNow.ToString("o") + " " + line + Environment.NewLine);
            };
            child.OutputDataReceived += (sender, item) => append(item.Data);
            child.ErrorDataReceived += (sender, item) => append(item.Data);
            append("Starting DS_TOPAS " + args[0] + "; Python PID " + child.Id + "; root " + root);
            child.BeginOutputReadLine(); child.BeginErrorReadLine();
            child.WaitForExit();
            return child.ExitCode;
        } catch (Exception error) {
            File.AppendAllText(log, DateTime.UtcNow.ToString("o") + " " + error + Environment.NewLine);
            return 1;
        } finally {
            if (job != IntPtr.Zero) CloseHandle(job);
            if (child != null) child.Dispose();
        }
    }
}
