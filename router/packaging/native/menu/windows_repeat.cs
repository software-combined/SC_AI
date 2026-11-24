using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

// The installer extracts this helper and the inventory from its own EXE.
internal static class WindowsRepeat {
    static bool Plain(string path, bool directory) {
        var attributes = File.GetAttributes(path);
        return (attributes & FileAttributes.ReparsePoint) == 0 &&
               ((attributes & FileAttributes.Directory) != 0) == directory;
    }

    static string Pointer(string home, string file) {
        var path = Path.Combine(home, file);
        if (!Plain(path, false) || new FileInfo(path).Length > 128) return null;
        return File.ReadAllText(path).Trim();
    }

    static bool Matches(string resources, IEnumerator<string> inventory) {
        var expected = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        while (inventory.MoveNext()) {
            var columns = inventory.Current.Split('\t');
            if (columns.Length != 2 || !Regex.IsMatch(columns[0], @"\A[0-9a-f]{64}\z")) return false;
            expected.Add(columns[1].Replace('/', Path.DirectorySeparatorChar), columns[0]);
        }
        var folders = new Stack<string>();
        folders.Push(resources);
        using (var sha = SHA256.Create()) {
            while (folders.Count > 0) {
                foreach (var path in Directory.EnumerateFileSystemEntries(folders.Pop())) {
                    var attributes = File.GetAttributes(path);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) return false;
                    if ((attributes & FileAttributes.Directory) != 0) {
                        // The isolated probe cannot load these generated caches.
                        if (Path.GetFileName(path) != "__pycache__") folders.Push(path);
                        continue;
                    }
                    string relative = path.Substring(resources.Length + 1);
                    string digest;
                    if (!expected.TryGetValue(relative, out digest)) return false;
                    using (var stream = File.OpenRead(path)) {
                        var actual = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "");
                        if (!String.Equals(actual, digest, StringComparison.OrdinalIgnoreCase)) return false;
                    }
                    expected.Remove(relative);
                }
            }
        }
        return expected.Count == 0;
    }

    internal static bool Ready(string inventory, string profile) {
        if (!Path.IsPathRooted(profile) || !Plain(profile, true)) return false;
        var parent = Path.Combine(profile, ".codex");
        var home = Path.Combine(parent, "mixed-model-router");
        if (!Plain(parent, true) || !Plain(home, true)) return false;
        var lockPath = Path.Combine(home, "install.lock");
        if (!Plain(lockPath, false)) return false;
        using (var guard = new FileStream(lockPath, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite))
        using (var lines = File.ReadLines(inventory).GetEnumerator()) {
            guard.Lock(0, 1); // The existing Python installer locks this byte too.
            if (!lines.MoveNext()) return false;
            string version = lines.Current;
            if (!Regex.IsMatch(version, @"\A[0-9]+(?:\.[0-9]+){2,3}\z") || Pointer(home, "current") != version)
                return false;
            if (!lines.MoveNext() || !Regex.IsMatch(lines.Current, @"\A[0-9a-f]{64}\z")) return false;
            string prefix = version + "-" + lines.Current.Substring(0, 16);
            string name = Pointer(home, "setup-current");
            if (name == null || !Regex.IsMatch(name, @"\A" + Regex.Escape(prefix) + @"(?:-repair-[0-9a-f]{12})?\z"))
                return false;
            var setup = Path.Combine(home, "setup");
            var resources = Path.Combine(setup, name);
            if (!Plain(setup, true) || !Plain(resources, true)) return false;
            if (!Matches(resources, lines)) return false;
            return Probe(resources, home, version, Path.GetDirectoryName(inventory));
        }
    }

    static bool Probe(string resources, string home, string version, string privateDirectory) {
        var python = Path.Combine(resources, @"runtime\python\python.exe");
        var probe = Path.Combine(resources, @"router\packaging\windows_repeat.py");
        // Suppress site hooks and use an empty cache namespace. No installed
        // bytecode or unverified import directories participate in this launch.
        var start = new ProcessStartInfo(python,
            "-I -S -B -X \"pycache_prefix=" + Path.Combine(privateDirectory, "cache") + "\" \"" +
            probe + "\" \"" + home + "\" " + version) {
            WorkingDirectory = privateDirectory, UseShellExecute = false, CreateNoWindow = true
        };
        start.EnvironmentVariables["PATH"] = Environment.SystemDirectory;
        start.EnvironmentVariables["SystemRoot"] = Path.GetDirectoryName(Environment.SystemDirectory);
        start.EnvironmentVariables["NO_PROXY"] = "*";
        using (var child = Process.Start(start)) {
            if (child.WaitForExit(20000)) return child.ExitCode == 0;
            child.Kill();
            return false;
        }
    }
}
