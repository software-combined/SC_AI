using System;
using System.Collections.Generic;
using System.Drawing;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
#if NET10_0_OR_GREATER
using System.Text.Json;
#else
using System.Web.Script.Serialization;
#endif
using System.Windows.Forms;
using Microsoft.Win32;

// The tray and dialog routes only present what their callers send.
internal sealed class RouterMenu : ApplicationContext {
    readonly NotifyIcon icon = new NotifyIcon();
    readonly Control dispatcher = new Control();
    readonly MenuJson json = new MenuJson();
    readonly string iconPath;
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr value);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();

    RouterMenu(string path) {
        iconPath = path;
        dispatcher.CreateControl();
        var handle = dispatcher.Handle;
        RefreshIcon();
        icon.Text = "SCG Router";
        icon.Visible = true;
        icon.MouseClick += (s, e) => {
            if (e.Button != MouseButtons.Left || icon.ContextMenuStrip == null) return;
            // Take the right-click path: NotifyIcon makes its window the foreground
            // first, so clicking elsewhere or pressing Escape dismisses the menu.
            var show = typeof(NotifyIcon).GetMethod("ShowContextMenu",
                BindingFlags.Instance | BindingFlags.NonPublic);
            if (show != null) show.Invoke(icon, null);
            else icon.ContextMenuStrip.Show(Cursor.Position);
        };
        SystemEvents.UserPreferenceChanged += PreferencesChanged;
        var reader = new Thread(ReadInput) { IsBackground = true };
        reader.Start();
    }

    void PreferencesChanged(object sender, UserPreferenceChangedEventArgs args) {
        if (!dispatcher.IsDisposed) dispatcher.BeginInvoke((Action)RefreshIcon);
    }

    void RefreshIcon() {
        bool light = false;
        using (var key = Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")) {
            light = key != null && Convert.ToInt32(key.GetValue("SystemUsesLightTheme", 0)) != 0;
        }
        Color foreground = SystemInformation.HighContrast ? SystemColors.WindowText :
                           (light ? Color.Black : Color.White);
        using (var image = new Bitmap(iconPath))
        using (var pixels = new Bitmap(image, new Size(32, 32))) {
            for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++) {
                var value = pixels.GetPixel(x, y);
                int white = Math.Min(value.R, Math.Min(value.G, value.B));
                pixels.SetPixel(x, y, Color.FromArgb((255 - white) * value.A / 255, foreground));
            }
            IntPtr native = pixels.GetHicon();
            var replacement = (Icon)Icon.FromHandle(native).Clone();
            DestroyIcon(native);
            var previous = icon.Icon;
            icon.Icon = replacement;
            if (previous != null) previous.Dispose();
        }
    }

    void Emit(string action) {
        Console.WriteLine(json.Serialize(new Dictionary<string, object> { { "action", action } }));
        Console.Out.Flush();
    }

    ToolStripItem[] Build(object[] rows) {
        var result = new List<ToolStripItem>();
        foreach (Dictionary<string, object> row in rows) {
            string label = Convert.ToString(row["label"]);
            if (label.Length == 0) { result.Add(new ToolStripSeparator()); continue; }
            var entry = new ToolStripMenuItem(label) {
                Enabled = Convert.ToBoolean(row["enabled"]),
                Checked = Convert.ToBoolean(row["checked"])
            };
            var children = row["children"] as object[];
            if (children != null && children.Length > 0) entry.DropDownItems.AddRange(Build(children));
            else if (row["action"] != null) {
                string action = Convert.ToString(row["action"]);
                entry.Click += (s, e) => Emit(action);
            }
            result.Add(entry);
        }
        return result.ToArray();
    }

    void ReadInput() {
        try {
            string line;
            while ((line = Console.ReadLine()) != null) {
                if (line.Length > 65536) break;
                var doc = json.DeserializeObject(line) as Dictionary<string, object>;
                if (doc == null || Convert.ToInt32(doc["schema"]) != 1) continue;
                dispatcher.BeginInvoke((Action)(() => Update(doc)));
            }
        } catch (Exception) { }
        if (!dispatcher.IsDisposed) dispatcher.BeginInvoke((Action)ExitThread);
    }

    void Update(Dictionary<string, object> doc) {
        var menu = icon.ContextMenuStrip;
        if (menu == null) {
            menu = new ContextMenuStrip();
            menu.Opening += (s, e) => Emit("refresh");
            icon.ContextMenuStrip = menu;
        }
        // One strip for the helper's lifetime, refreshed in place: an open menu shows
        // the new state at once, and no popup is disposed while it is showing.
        var previous = new ToolStripItem[menu.Items.Count];
        menu.Items.CopyTo(previous, 0);
        menu.SuspendLayout();
        menu.Items.Clear();
        menu.Items.AddRange(Build((object[])doc["menu"]));
        menu.ResumeLayout();
        foreach (var item in previous) item.Dispose();
        string text = "SCG Router: " + Convert.ToString(doc["status"]);
        icon.Text = text.Substring(0, Math.Min(text.Length, 63));
    }

    protected override void ExitThreadCore() {
        SystemEvents.UserPreferenceChanged -= PreferencesChanged;
        if (icon.ContextMenuStrip != null) icon.ContextMenuStrip.Close();
        icon.Visible = false;
        icon.Dispose();
        dispatcher.Dispose();
        base.ExitThreadCore();
    }

    static int Dialog(string path, bool progress) {
        Console.SetIn(new System.IO.StreamReader(Console.OpenStandardInput(),
            new System.Text.UTF8Encoding(false)));
        Console.SetOut(new System.IO.StreamWriter(Console.OpenStandardOutput(),
            new System.Text.UTF8Encoding(false)) { AutoFlush = true });
        var parser = new MenuJson();
        string line = Console.ReadLine();
        if (line == null || line.Length > 65536) return 2;
        var doc = parser.DeserializeObject(line) as Dictionary<string, object>;
        if (doc == null) return 2;
        var labels = doc["labels"] as object[];
        string text = Convert.ToString(doc["text"]);
        if (labels == null || labels.Length < 1 || labels.Length > 2 || text.Length > 4000) return 2;
        bool accepted = ShowDialog(path, text, labels, progress);
        Console.WriteLine("SCG_ROUTER_DIALOG_RESULT=" + (accepted ? "accept" : "cancel"));
        Console.Out.Flush();
        return accepted ? 0 : 1;
    }

    static bool ShowDialog(string path, string text, object[] labels, bool progress) {
        using (var form = new Form())
        using (var image = new Bitmap(path)) {
            IntPtr handle = image.GetHicon();
            using (var productIcon = (Icon)Icon.FromHandle(handle).Clone()) {
                DestroyIcon(handle);
                form.Text = "SCG Router";
                form.Icon = productIcon;
                form.StartPosition = FormStartPosition.CenterScreen;
                form.AutoSize = true;
                form.AutoSizeMode = AutoSizeMode.GrowAndShrink;
                form.MinimizeBox = false;
                form.MaximizeBox = false;
                var panel = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown,
                    WrapContents = false, AutoSize = true, Padding = new Padding(12) };
                panel.Controls.Add(new Label { Text = text, AutoSize = true,
                    MaximumSize = new Size(440, 0) });
                var buttons = new FlowLayoutPanel { AutoSize = true, WrapContents = false };
                for (int index = 0; index < labels.Length; index++) {
                    string label = Convert.ToString(labels[index]);
                    bool accept = labels.Length == 2 && index == 0 || label == "OK";
                    var button = new Button { Text = label, AutoSize = true,
                        DialogResult = accept ? DialogResult.OK : DialogResult.Cancel };
                    buttons.Controls.Add(button);
                    if (accept) form.AcceptButton = button;
                    else form.CancelButton = button;
                }
                panel.Controls.Add(buttons);
                form.Controls.Add(panel);
                if (progress) {
                    var watcher = new Thread(() => {
                        try { while (Console.ReadLine() != null) { } } catch (Exception) { }
                        try { form.BeginInvoke((Action)(() => form.Close())); } catch (InvalidOperationException) { }
                    }) { IsBackground = true };
                    form.Shown += (s, e) => watcher.Start();
                }
                return form.ShowDialog() == DialogResult.OK;
            }
        }
    }

    [STAThread] static int Main(string[] args) {
        try {
            SetProcessDPIAware();
            Application.EnableVisualStyles();
            if (args.Length == 2 && (args[0] == "--dialog" || args[0] == "--progress"))
                return Dialog(args[1], args[0] == "--progress");
            if (args.Length == 3 && args[0] == "--repeat") {
                var profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                if (!WindowsRepeat.Ready(args[1], profile)) return 2;
                ShowDialog(args[2], "SCG Router is up to date.", new object[] { "OK" }, false);
                return 0;
            }
            if (args.Length != 1) return 2;
            Application.Run(new RouterMenu(args[0]));
            return 0;
        } catch (Exception) { return 2; }
    }
}

// Keep the Framework and modern .NET serializers behind the same menu protocol.
internal sealed class MenuJson {
#if NET10_0_OR_GREATER
    static object ConvertElement(JsonElement value) {
        switch (value.ValueKind) {
            case JsonValueKind.Object:
                var result = new Dictionary<string, object>();
                foreach (var item in value.EnumerateObject()) result[item.Name] = ConvertElement(item.Value);
                return result;
            case JsonValueKind.Array:
                var list = new List<object>();
                foreach (var item in value.EnumerateArray()) list.Add(ConvertElement(item));
                return list.ToArray();
            case JsonValueKind.String: return value.GetString();
            case JsonValueKind.Number: return value.GetInt32();
            case JsonValueKind.True: return true;
            case JsonValueKind.False: return false;
            case JsonValueKind.Null: return null;
            default: throw new FormatException();
        }
    }
    internal object DeserializeObject(string value) {
        using (var document = JsonDocument.Parse(value)) return ConvertElement(document.RootElement);
    }
    internal string Serialize(object value) { return JsonSerializer.Serialize(value); }
#else
    readonly JavaScriptSerializer serializer = new JavaScriptSerializer { MaxJsonLength = 65536 };
    internal object DeserializeObject(string value) { return serializer.DeserializeObject(value); }
    internal string Serialize(object value) { return serializer.Serialize(value); }
#endif
}
