// lan-computer-use agent for Windows. Runs in the logged-on desktop session, listens on 127.0.0.1 only and
// answers newline-delimited JSON requests that carry a random token (written to state.json next to the exe).
// Compiled on the target by setup.ps1 with the in-box .NET Framework csc (C# 5: no interpolation, no ?.).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Windows.Automation;

class AgentError : Exception { public AgentError(string m) : base(m) { } }

static class Agent
{
    const string Version = "1";
    static string token, build = "", dir, stateFile;
    static int idleMinutes = 30;
    static DateTime lastRequest = DateTime.UtcNow;
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue, RecursionLimit = 256 };
    static readonly Dictionary<string, AutomationElement> refs = new Dictionary<string, AutomationElement>();
    static int refCounter;
    static double shotScale = 1; static int shotX0, shotY0; static bool haveShot;

    [MTAThread]
    static int Main(string[] args)
    {
        for (int i = 0; i + 1 < args.Length; i++)
        {
            if (args[i] == "--idle") idleMinutes = int.Parse(args[++i]);
            else if (args[i] == "--build") build = args[++i];
        }
        try { if (!Native.SetProcessDpiAwarenessContext(new IntPtr(-4))) Native.SetProcessDPIAware(); }
        catch { try { Native.SetProcessDPIAware(); } catch { } }
        bool created;
        var mutex = new Mutex(true, "Local\\lan-computer-use-agent", out created);
        if (!created) return 2;
        dir = Path.GetDirectoryName(Process.GetCurrentProcess().MainModule.FileName);
        stateFile = Path.Combine(dir, "state.json");
        var bytes = new byte[32];
        using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(bytes);
        token = BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        var state = new Dictionary<string, object> {
            { "port", port }, { "token", token }, { "pid", Process.GetCurrentProcess().Id },
            { "build", build }, { "version", Version } };
        string tmp = stateFile + ".tmp";
        File.WriteAllText(tmp, Json.Serialize(state));
        if (File.Exists(stateFile)) File.Delete(stateFile);
        File.Move(tmp, stateFile);
        bool quit = false;
        try
        {
            while (!quit)
            {
                if (!listener.Server.Poll(1000000, SelectMode.SelectRead))
                {
                    if ((DateTime.UtcNow - lastRequest).TotalMinutes > idleMinutes) break;
                    continue;
                }
                using (var client = listener.AcceptTcpClient())
                {
                    client.NoDelay = true;
                    client.ReceiveTimeout = 60000;
                    quit = Serve(client);
                }
            }
        }
        finally
        {
            listener.Stop();
            try { File.Delete(stateFile); } catch { }
            mutex.ReleaseMutex();
        }
        return 0;
    }

    // One connection, any number of request lines. Returns true when the agent should exit.
    static bool Serve(TcpClient client)
    {
        var stream = client.GetStream();
        var reader = new StreamReader(stream, new UTF8Encoding(false));
        var writer = new StreamWriter(stream, new UTF8Encoding(false));
        writer.NewLine = "\n";
        while (true)
        {
            string line;
            try { line = reader.ReadLine(); } catch (IOException) { return false; }
            if (line == null) return false;
            if (line.Trim().Length == 0) continue;
            lastRequest = DateTime.UtcNow;
            Dictionary<string, object> resp; bool quit = false;
            try
            {
                var req = Json.Deserialize<Dictionary<string, object>>(line);
                if (!TokenOk(Str(req, "token", ""))) { resp = Fail("bad token"); writer.WriteLine(Json.Serialize(resp)); writer.Flush(); return false; }
                string cmd = Str(req, "cmd", "");
                if (cmd == "quit") { quit = true; resp = Ok(); }
                else resp = Dispatch(cmd, req);
            }
            catch (AgentError e) { resp = Fail(e.Message); }
            catch (ElementNotAvailableException) { resp = Fail("element no longer exists (stale ref) - take a new snapshot"); }
            catch (Exception e) { resp = Fail(e.GetType().Name + ": " + e.Message); }
            writer.WriteLine(Json.Serialize(resp));
            writer.Flush();
            if (quit) return true;
        }
    }

    static bool TokenOk(string t)
    {
        if (t.Length != token.Length) return false;
        int diff = 0;
        for (int i = 0; i < t.Length; i++) diff |= t[i] ^ token[i];
        return diff == 0;
    }

    static Dictionary<string, object> Ok() { var d = new Dictionary<string, object>(); d["ok"] = true; return d; }
    static Dictionary<string, object> Fail(string m) { var d = new Dictionary<string, object>(); d["ok"] = false; d["error"] = m; return d; }

    static Dictionary<string, object> Dispatch(string cmd, Dictionary<string, object> a)
    {
        if (cmd == "task") return Overlay.Task(a);
        string label = Overlay.Label(cmd, a);
        if (label != null) Overlay.Action(label);
        switch (cmd)
        {
            case "hello": return Hello();
            case "windows": return Windows();
            case "snapshot": return Snapshot(a);
            case "find": return Find(a);
            case "wait": return Wait(a);
            case "shot": return Shot(a);
            case "click": return Click(a);
            case "move": return MoveTo(a);
            case "drag": return Drag(a);
            case "scroll": return Scroll(a);
            case "press": return Press(a);
            case "set-value": return SetValue(a);
            case "focus": return FocusRef(a);
            case "type": return TypeText(a);
            case "key": return Key(a);
            case "activate": return Activate(a);
            case "launch": return Launch(a);
        }
        throw new AgentError("unknown command '" + cmd + "'");
    }

    // ---------- overlay ----------
    // A small click-through status panel in the top-right corner of the primary screen so the person at the machine
    // sees that it is being controlled, what happens right now and how long it will last. Runs its own STA thread;
    // WDA_EXCLUDEFROMCAPTURE keeps it out of screen captures (the agent's shots included). Texts follow the UI language.
    static class Overlay
    {
        static readonly object gate = new object();
        static readonly bool de = System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "de";
        static bool on; static DateTime start, actionAt; static DateTime? end; static string task = "", action = "";
        static Panel form; static Thread thread;
        internal static volatile bool excluded;

        static string T(string german, string english) { return de ? german : english; }
        static string Mmss(double sec) { int s = Math.Max(0, (int)Math.Round(sec)); return (s / 60) + ":" + (s % 60).ToString("00"); }

        internal static string Label(string cmd, Dictionary<string, object> a)
        {
            string tgt = Has(a, "ref") ? " " + Str(a, "ref", "") : Has(a, "x") ? " @" + Int(a, "x", 0) + "," + Int(a, "y", 0) : "";
            switch (cmd)
            {
                case "hello": return T("verbunden", "connected");
                case "windows": case "snapshot": case "find": return T("liest die Oberfläche", "reading the UI");
                case "wait": return T("wartet", "waiting");
                case "shot": return T("macht einen Screenshot", "taking a screenshot");
                case "click": return T("klickt", "clicking") + tgt;
                case "move": return T("bewegt die Maus", "moving the mouse") + tgt;
                case "drag": return T("zieht", "dragging");
                case "scroll": return T("scrollt", "scrolling") + tgt;
                case "press": return T("betätigt", "pressing") + tgt;
                case "set-value": return T("setzt einen Wert", "setting a value") + tgt;
                case "focus": return T("fokussiert", "focusing") + tgt;
                case "type": int n = Str(a, "text", "").Length; return T("tippt " + n + " Zeichen", "typing " + n + " characters");
                case "key":
                    object k; var keys = a.TryGetValue("keys", out k) && k is ArrayList ? string.Join(" ", ((ArrayList)k).ToArray()) : "";
                    return T("drückt ", "pressing ") + Clip(keys, 30);
                case "activate": return T("holt ein Fenster nach vorn", "bringing a window to front");
                case "launch": return T("startet ", "launching ") + Clip(Path.GetFileName(Str(a, "target", "")), 30);
            }
            return null;
        }

        internal static void Action(string label)
        {
            lock (gate) { action = label; actionAt = DateTime.UtcNow; if (!on) { on = true; start = DateTime.UtcNow; } }
            Refresh();
        }

        internal static Dictionary<string, object> Task(Dictionary<string, object> a)
        {
            var r = Ok();
            lock (gate)
            {
                if (Bool(a, "done")) { on = false; task = ""; action = ""; end = null; r["overlay"] = "hidden"; }
                else
                {
                    if (Has(a, "text")) task = Str(a, "text", "");
                    if (Has(a, "eta")) { double e = Dbl(a, "eta", 0); end = e > 0 ? DateTime.UtcNow.AddSeconds(e) : (DateTime?)null; }
                    if (!on) { on = true; start = DateTime.UtcNow; }
                    r["overlay"] = "shown";
                }
            }
            Refresh();
            return r;
        }

        // lines: bold header, optional task, current action, small meta line
        internal static string[] Lines(out bool visible)
        {
            lock (gate)
            {
                visible = on;
                var now = DateTime.UtcNow;
                var l = new List<string> { T("Claude steuert diesen Rechner", "Claude is controlling this computer") };
                l.Add(task.Length > 0 ? Clip(task, 60) : null);
                l.Add(action.Length > 0 ? "▸ " + Clip(action, 40) + " · " + T("vor ", "") + Mmss((now - actionAt).TotalSeconds) + T("", " ago") : null);
                string meta = T("läuft ", "running ") + Mmss((now - start).TotalSeconds);
                if (end.HasValue)
                {
                    double left = (end.Value - now).TotalSeconds;
                    meta += " · " + (left >= 0 ? T("noch ca. ", "about ") + Mmss(left) + T("", " left") : T("überzogen +", "overdue +") + Mmss(-left));
                }
                meta += " · " + T("Auto-Ende ", "auto-stop ") + Mmss(idleMinutes * 60 - (now - lastRequest).TotalSeconds);
                l.Add(meta);
                return l.ToArray();
            }
        }

        static void Refresh()
        {
            if (thread == null)
            {
                var ready = new ManualResetEvent(false);
                thread = new Thread(() =>
                {
                    form = new Panel();
                    form.HandleCreated += (s, e) => ready.Set();
                    var unused = form.Handle;
                    Application.Run();
                });
                thread.IsBackground = true;
                thread.SetApartmentState(ApartmentState.STA);
                thread.Start();
                ready.WaitOne(3000);
            }
            var f = form;
            if (f != null && f.IsHandleCreated) try { f.BeginInvoke((MethodInvoker)f.Tick); } catch { }
        }

        // keep the overlay out of the agent's own screenshots where display affinity is unavailable (before Windows 10 2004)
        internal static void HideForCapture(bool hide)
        {
            var f = form;
            if (excluded || f == null || !f.IsHandleCreated) return;
            try { f.Invoke((MethodInvoker)(() => { if (hide) Native.ShowWindow(f.Handle, 0); else f.Tick(); })); } catch { }
            if (hide) Thread.Sleep(60);
        }

        class Panel : Form
        {
            readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 1000 };
            string[] lines = new string[0];
            Font head, body, small;
            float dpi = 1;

            public Panel()
            {
                FormBorderStyle = FormBorderStyle.None;
                ShowInTaskbar = false;
                StartPosition = FormStartPosition.Manual;
                BackColor = Color.FromArgb(28, 28, 28);
                Opacity = 0.95;
                DoubleBuffered = true;
                timer.Tick += (s, e) => Tick();
                timer.Start();
            }
            protected override bool ShowWithoutActivation { get { return true; } }
            protected override CreateParams CreateParams
            {
                // LAYERED | TRANSPARENT (click-through) | TOOLWINDOW (no taskbar, not in window lists) | TOPMOST | NOACTIVATE
                get { var cp = base.CreateParams; cp.ExStyle |= 0x80000 | 0x20 | 0x80 | 0x8 | 0x08000000; return cp; }
            }
            protected override void OnHandleCreated(EventArgs e)
            {
                base.OnHandleCreated(e);
                try { excluded = Native.SetWindowDisplayAffinity(Handle, 0x11); } catch { excluded = false; }
                using (var g = CreateGraphics()) dpi = g.DpiX / 96f;
                head = new Font("Segoe UI Semibold", 10f, FontStyle.Regular, GraphicsUnit.Point);
                body = new Font("Segoe UI", 9.5f, FontStyle.Regular, GraphicsUnit.Point);
                small = new Font("Segoe UI", 8.5f, FontStyle.Regular, GraphicsUnit.Point);
            }

            internal void Tick()
            {
                bool visible;
                lines = Lines(out visible);
                if (!visible) { if (Native.IsWindowVisible(Handle)) Native.ShowWindow(Handle, 0); return; }
                int pad = (int)(9 * dpi), icon = (int)(24 * dpi), gap = (int)(8 * dpi), width = (int)(300 * dpi);
                int textW = width - 2 * pad - icon - gap, h = 0;
                for (int i = 0; i < lines.Length; i++)
                    if (lines[i] != null) h += TextRenderer.MeasureText(lines[i], FontFor(i), new Size(textW, 0), TextFormatFlags.SingleLine).Height;
                int height = Math.Max(h, icon) + 2 * pad;
                var wa = Screen.PrimaryScreen.WorkingArea;
                Bounds = new Rectangle(wa.Right - width - (int)(10 * dpi), wa.Top + (int)(10 * dpi), width, height);
                using (var path = Rounded(new Rectangle(0, 0, width, height), (int)(9 * dpi))) Region = new Region(path);
                if (!Native.IsWindowVisible(Handle)) Native.ShowWindow(Handle, 4); // SW_SHOWNOACTIVATE
                Native.SetWindowPos(Handle, new IntPtr(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040); // stay topmost
                Invalidate();
            }

            Font FontFor(int i) { return i == 0 ? head : i == lines.Length - 1 ? small : body; }

            static GraphicsPath Rounded(Rectangle r, int rad)
            {
                var p = new GraphicsPath(); int d = rad * 2;
                p.AddArc(r.X, r.Y, d, d, 180, 90); p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
                p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90); p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
                p.CloseFigure(); return p;
            }

            protected override void OnPaint(PaintEventArgs e)
            {
                var g = e.Graphics;
                g.SmoothingMode = SmoothingMode.AntiAlias;
                int pad = (int)(9 * dpi), icon = (int)(24 * dpi), gap = (int)(8 * dpi);
                var yellow = Color.FromArgb(255, 204, 0);
                using (var pen = new Pen(yellow, 2f * dpi))
                using (var path = Rounded(new Rectangle(1, 1, Width - 3, Height - 3), (int)(8 * dpi))) g.DrawPath(pen, path);
                // warning triangle with an exclamation mark
                var tri = new[] { new PointF(pad + icon / 2f, pad + 1), new PointF(pad + icon, pad + icon - 2), new PointF(pad, pad + icon - 2) };
                using (var b = new SolidBrush(yellow)) g.FillPolygon(b, tri);
                using (var f = new Font("Segoe UI", icon * 0.42f, FontStyle.Bold, GraphicsUnit.Pixel))
                    TextRenderer.DrawText(g, "!", f, new Rectangle(pad, pad + icon / 5, icon, icon * 4 / 5), Color.Black,
                        TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
                int x = pad + icon + gap, y = pad, textW = Width - x - pad;
                for (int i = 0; i < lines.Length; i++)
                {
                    if (lines[i] == null) continue;
                    var font = FontFor(i);
                    var color = i == lines.Length - 1 ? Color.FromArgb(184, 184, 184) : Color.FromArgb(245, 245, 245);
                    int lh = TextRenderer.MeasureText(lines[i], font, new Size(textW, 0), TextFormatFlags.SingleLine).Height;
                    TextRenderer.DrawText(g, lines[i], font, new Rectangle(x, y, textW, lh), color,
                        TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
                    y += lh;
                }
            }
        }
    }

    // ---------- helpers for arguments ----------
    static string Str(Dictionary<string, object> a, string k, string def)
    { object v; return a.TryGetValue(k, out v) && v != null ? Convert.ToString(v) : def; }
    static int Int(Dictionary<string, object> a, string k, int def)
    { object v; return a.TryGetValue(k, out v) && v != null ? Convert.ToInt32(v) : def; }
    static double Dbl(Dictionary<string, object> a, string k, double def)
    { object v; return a.TryGetValue(k, out v) && v != null ? Convert.ToDouble(v) : def; }
    static bool Bool(Dictionary<string, object> a, string k)
    { object v; return a.TryGetValue(k, out v) && v is bool && (bool)v; }
    static bool Has(Dictionary<string, object> a, string k) { object v; return a.TryGetValue(k, out v) && v != null; }

    // ---------- desktop state ----------
    static string InputDesktop()
    {
        IntPtr h = Native.OpenInputDesktop(0, false, 0x0001);
        if (h == IntPtr.Zero) return "(secure desktop)";
        try
        {
            var buf = new byte[256]; uint need;
            if (!Native.GetUserObjectInformation(h, 2, buf, (uint)buf.Length, out need)) return "(unknown)";
            return Encoding.Unicode.GetString(buf, 0, (int)Math.Max(0, need - 2)).TrimEnd('\0');
        }
        finally { Native.CloseDesktop(h); }
    }

    static void RequireInput()
    {
        string d = InputDesktop();
        if (!string.Equals(d, "Default", StringComparison.OrdinalIgnoreCase))
            throw new AgentError("input desktop is '" + d + "' (lock screen, UAC or credential prompt): stop and ask the user");
    }

    // keystrokes into a minimized foreground window (Windows keeps one when nothing else is open) hit an
    // invisible window, e.g. a console where ctrl+a starts a selection that freezes its output
    static void RequireVisibleForeground()
    {
        IntPtr fg = Native.GetForegroundWindow();
        if (fg != IntPtr.Zero && Native.IsIconic(fg))
            throw new AgentError("foreground window '" + WindowTitle(fg) + "' is minimized - activate or launch the target window first");
    }

    static string OsVersion()
    {
        const string k = @"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion";
        string name = Convert.ToString(Microsoft.Win32.Registry.GetValue(k, "ProductName", ""));
        string disp = Convert.ToString(Microsoft.Win32.Registry.GetValue(k, "DisplayVersion", ""));
        string build = Convert.ToString(Microsoft.Win32.Registry.GetValue(k, "CurrentBuild", ""));
        int b;
        // ProductName still says "Windows 10" on Windows 11
        if (name.StartsWith("Windows 10") && int.TryParse(build, out b) && b >= 22000) name = "Windows 11" + name.Substring(10);
        return (name + " " + disp + " (build " + build + ")").Trim();
    }

    static Dictionary<string, object> Hello()
    {
        var r = Ok();
        r["os"] = "windows";
        r["os_version"] = OsVersion();
        r["user"] = Environment.UserDomainName + "\\" + Environment.UserName;
        r["host"] = Environment.MachineName;
        r["session"] = Process.GetCurrentProcess().SessionId;
        r["desktop"] = InputDesktop();
        r["screen"] = new int[] { Native.GetSystemMetrics(76), Native.GetSystemMetrics(77), Native.GetSystemMetrics(78), Native.GetSystemMetrics(79) };
        r["version"] = Version; r["build"] = build; r["pid"] = Process.GetCurrentProcess().Id;
        r["units"] = "px";
        r["permissions"] = new Dictionary<string, object> { { "accessibility", true }, { "screen", true } };
        return r;
    }

    static Dictionary<string, object> Post()
    {
        var r = Ok();
        r["post"] = PostState();
        return r;
    }

    // what the agent sees right after an action: foreground window and focused element
    static Dictionary<string, object> PostState()
    {
        var p = new Dictionary<string, object>();
        IntPtr fg = Native.GetForegroundWindow();
        if (fg != IntPtr.Zero) { p["window"] = WindowTitle(fg); p["app"] = ProcName(fg); }
        try
        {
            var f = AutomationElement.FocusedElement;
            if (f != null)
            {
                p["focus_role"] = Role(f.Current.ControlType);
                p["focus_name"] = Clip(f.Current.Name, 60);
            }
        }
        catch { }
        p["desktop"] = InputDesktop();
        return p;
    }

    // ---------- windows ----------
    static string WindowTitle(IntPtr h)
    {
        int n = Native.GetWindowTextLength(h);
        var sb = new StringBuilder(n + 1);
        Native.GetWindowText(h, sb, sb.Capacity);
        return sb.ToString();
    }

    static readonly Dictionary<uint, string> procNames = new Dictionary<uint, string>();
    static string ProcName(IntPtr h)
    {
        uint pid; Native.GetWindowThreadProcessId(h, out pid);
        string n;
        if (procNames.TryGetValue(pid, out n)) return n;
        try { n = Process.GetProcessById((int)pid).ProcessName; } catch { n = "?"; }
        procNames[pid] = n;
        return n;
    }

    static bool IsCloaked(IntPtr h)
    {
        int c = 0;
        try { Native.DwmGetWindowAttribute(h, 14, out c, 4); } catch { }
        return c != 0;
    }

    static List<IntPtr> TopWindows()
    {
        var list = new List<IntPtr>();
        Native.EnumWindows(delegate (IntPtr h, IntPtr l)
        {
            if (!Native.IsWindowVisible(h) || IsCloaked(h)) return true;
            if (Native.GetWindowTextLength(h) == 0) return true;
            long ex = Native.GetWindowLongPtr(h, -20).ToInt64();
            if ((ex & 0x80) != 0) return true; // WS_EX_TOOLWINDOW
            list.Add(h);
            return true;
        }, IntPtr.Zero);
        return list;
    }

    static int[] WindowRect(IntPtr h)
    {
        Native.RECT r;
        if (Native.DwmGetWindowAttribute(h, 9, out r, Marshal.SizeOf(typeof(Native.RECT))) != 0) Native.GetWindowRect(h, out r);
        return new int[] { r.Left, r.Top, r.Right - r.Left, r.Bottom - r.Top };
    }

    static Dictionary<string, object> WinInfo(IntPtr h)
    {
        uint pid; Native.GetWindowThreadProcessId(h, out pid);
        return new Dictionary<string, object> {
            { "title", WindowTitle(h) }, { "app", ProcName(h) }, { "pid", (int)pid },
            { "handle", h.ToInt64() }, { "rect", WindowRect(h) },
            { "minimized", Native.IsIconic(h) }, { "foreground", h == Native.GetForegroundWindow() } };
    }

    static Dictionary<string, object> Windows()
    {
        var r = Ok();
        var l = new List<object>();
        foreach (var h in TopWindows()) l.Add(WinInfo(h));
        r["windows"] = l;
        return r;
    }

    // window selection: handle, title substring and/or app (process name) - default foreground window
    static IntPtr PickWindow(Dictionary<string, object> a)
    {
        if (Has(a, "handle")) return new IntPtr(Convert.ToInt64(a["handle"]));
        string title = Str(a, "window", ""), app = Str(a, "app", "");
        if (title.Length == 0 && app.Length == 0)
        {
            IntPtr fg = Native.GetForegroundWindow();
            if (fg == IntPtr.Zero) throw new AgentError("no foreground window");
            return fg;
        }
        IntPtr best = IntPtr.Zero;
        IntPtr fgw = Native.GetForegroundWindow();
        foreach (var h in TopWindows())
        {
            if (title.Length > 0 && WindowTitle(h).IndexOf(title, StringComparison.OrdinalIgnoreCase) < 0) continue;
            if (app.Length > 0 && !string.Equals(ProcName(h), app.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? app.Substring(0, app.Length - 4) : app, StringComparison.OrdinalIgnoreCase)) continue;
            if (h == fgw) return h;
            if (best == IntPtr.Zero) best = h; // EnumWindows is in z-order: first match is the topmost
        }
        if (best == IntPtr.Zero) throw new AgentError("no window matches" + (title.Length > 0 ? " title '" + title + "'" : "") + (app.Length > 0 ? " app '" + app + "'" : ""));
        return best;
    }

    static Dictionary<string, object> Activate(Dictionary<string, object> a)
    {
        RequireInput();
        IntPtr h = PickWindow(a);
        BringToFront(h);
        if (Native.GetForegroundWindow() != h) throw new AgentError("Windows refused to bring '" + WindowTitle(h) + "' to the foreground");
        return Post();
    }

    static void BringToFront(IntPtr h)
    {
        if (Native.IsIconic(h)) Native.ShowWindow(h, 9);
        if (Native.SetForegroundWindow(h) && Native.GetForegroundWindow() == h) return;
        uint fgThread = Native.GetWindowThreadProcessId(Native.GetForegroundWindow(), IntPtr.Zero);
        uint me = Native.GetCurrentThreadId();
        if (fgThread != 0 && fgThread != me)
        {
            Native.AttachThreadInput(me, fgThread, true);
            Native.BringWindowToTop(h);
            Native.SetForegroundWindow(h);
            Native.AttachThreadInput(me, fgThread, false);
        }
        if (Native.GetForegroundWindow() == h) return;
        // the foreground lock yields to the process that sent the last input event
        SendKeys(new ushort[] { 0x12 }, true); SendKeys(new ushort[] { 0x12 }, false);
        Native.SetForegroundWindow(h);
        Thread.Sleep(50);
    }

    // ---------- UIA tree ----------
    static readonly AutomationProperty[] Props = new AutomationProperty[] {
        AutomationElement.NameProperty, AutomationElement.ControlTypeProperty, AutomationElement.AutomationIdProperty,
        AutomationElement.BoundingRectangleProperty, AutomationElement.IsEnabledProperty, AutomationElement.IsOffscreenProperty,
        AutomationElement.HasKeyboardFocusProperty, AutomationElement.IsPasswordProperty, AutomationElement.IsKeyboardFocusableProperty,
        ValuePattern.ValueProperty, ValuePattern.IsReadOnlyProperty, TogglePattern.ToggleStateProperty,
        ExpandCollapsePattern.ExpandCollapseStateProperty, SelectionItemPattern.IsSelectedProperty,
        AutomationElement.IsInvokePatternAvailableProperty, AutomationElement.IsValuePatternAvailableProperty };

    static CacheRequest TreeRequest(TreeScope scope)
    {
        var cr = new CacheRequest();
        cr.TreeScope = scope;
        cr.TreeFilter = Automation.ControlViewCondition;
        cr.AutomationElementMode = AutomationElementMode.Full;
        foreach (var p in Props) cr.Add(p);
        return cr;
    }

    static object Cached(AutomationElement e, AutomationProperty p)
    {
        try
        {
            object v = e.GetCachedPropertyValue(p, true);
            return v == AutomationElement.NotSupported ? null : v;
        }
        catch { return null; }
    }

    static string Role(ControlType t)
    {
        if (t == null) return "unknown";
        string n = t.ProgrammaticName; // "ControlType.Button"
        int dot = n.LastIndexOf('.');
        n = (dot >= 0 ? n.Substring(dot + 1) : n);
        switch (n)
        {
            case "Hyperlink": return "link";
            case "RadioButton": return "radio";
            case "CheckBox": return "checkbox";
            case "ComboBox": return "combobox";
            case "DataItem": return "row";
            case "DataGrid": return "table";
            case "Tab": return "tablist";
            case "TabItem": return "tab";
            case "HeaderItem": return "columnheader";
            case "MenuItem": return "menuitem";
            case "MenuBar": return "menubar";
            case "ListItem": return "listitem";
            case "TreeItem": return "treeitem";
            case "ToolBar": return "toolbar";
            case "StatusBar": return "statusbar";
            case "TitleBar": return "titlebar";
            case "ScrollBar": return "scrollbar";
            case "SplitButton": return "splitbutton";
            case "ProgressBar": return "progressbar";
            case "ToolTip": return "tooltip";
            case "Edit": return "textfield";
            case "Text": return "text";
        }
        return n.ToLowerInvariant();
    }

    static string Clip(string s, int n)
    {
        if (s == null) return "";
        s = s.Replace("\r", " ").Replace("\n", " ").Trim();
        return s.Length > n ? s.Substring(0, n - 1) + "…" : s;
    }

    static readonly HashSet<string> Structural = new HashSet<string> { "pane", "group", "custom", "unknown" };

    // a node is printed when it can be acted on or carries text; unnamed containers are folded into their parent
    static Dictionary<string, object> NodeInfo(AutomationElement e, bool includeOffscreen, out bool emit)
    {
        emit = false;
        var ct = Cached(e, AutomationElement.ControlTypeProperty) as ControlType;
        string role = Role(ct);
        string name = Convert.ToString(Cached(e, AutomationElement.NameProperty) ?? "");
        object off = Cached(e, AutomationElement.IsOffscreenProperty);
        if (!includeOffscreen && off is bool && (bool)off) return null;
        object rectObj = Cached(e, AutomationElement.BoundingRectangleProperty);
        int[] rect = null;
        if (rectObj is System.Windows.Rect)
        {
            var r = (System.Windows.Rect)rectObj;
            if (!r.IsEmpty && r.Width > 0 && r.Height > 0) rect = new int[] { (int)r.X, (int)r.Y, (int)r.Width, (int)r.Height };
        }
        string id = Convert.ToString(Cached(e, AutomationElement.AutomationIdProperty) ?? "");
        string value = null;
        object v = Cached(e, ValuePattern.ValueProperty);
        bool isPassword = Cached(e, AutomationElement.IsPasswordProperty) is bool && (bool)Cached(e, AutomationElement.IsPasswordProperty);
        if (v != null) value = isPassword ? "(hidden)" : Clip(Convert.ToString(v), 120);
        var flags = new List<string>();
        object en = Cached(e, AutomationElement.IsEnabledProperty);
        if (en is bool && !(bool)en) flags.Add("disabled");
        object foc = Cached(e, AutomationElement.HasKeyboardFocusProperty);
        if (foc is bool && (bool)foc) flags.Add("focused");
        if (isPassword) flags.Add("password");
        object ts = Cached(e, TogglePattern.ToggleStateProperty);
        if (ts is ToggleState) flags.Add((ToggleState)ts == ToggleState.On ? "checked" : (ToggleState)ts == ToggleState.Off ? "unchecked" : "mixed");
        object ec = Cached(e, ExpandCollapsePattern.ExpandCollapseStateProperty);
        if (ec is ExpandCollapseState && (ExpandCollapseState)ec != ExpandCollapseState.LeafNode)
            flags.Add((ExpandCollapseState)ec == ExpandCollapseState.Collapsed ? "collapsed" : "expanded");
        object sel = Cached(e, SelectionItemPattern.IsSelectedProperty);
        if (sel is bool && (bool)sel) flags.Add("selected");
        object ro = Cached(e, ValuePattern.IsReadOnlyProperty);
        if (ro is bool && (bool)ro && (role == "textfield" || role == "document")) flags.Add("readonly");
        if (off is bool && (bool)off) flags.Add("offscreen");
        bool actionable = (Cached(e, AutomationElement.IsInvokePatternAvailableProperty) is bool && (bool)Cached(e, AutomationElement.IsInvokePatternAvailableProperty))
            || ts != null || sel != null || ec != null || v != null;
        bool structural = Structural.Contains(role);
        emit = !(structural && name.Length == 0 && value == null && !actionable && id.Length == 0)
            && !(role == "text" && name.Length == 0);
        var n = new Dictionary<string, object> { { "role", role }, { "name", Clip(name, 100) } };
        if (value != null && value != Clip(name, 100)) n["value"] = value;
        if (id.Length > 0 && !IsGeneratedId(id)) n["id"] = Clip(id, 60);
        if (rect != null) n["rect"] = rect;
        if (flags.Count > 0) n["flags"] = flags;
        return n;
    }

    // numeric runtime ids and GUID-like ids are noise, test ids and named ids are signal
    static bool IsGeneratedId(string id)
    {
        int digits = 0;
        foreach (char c in id) if (char.IsDigit(c)) digits++;
        return digits == id.Length || (id.Length >= 32 && digits > id.Length / 3);
    }

    static string AddRef(AutomationElement e)
    {
        string r = "e" + (++refCounter);
        refs[r] = e;
        return r;
    }

    static AutomationElement GetRef(Dictionary<string, object> a)
    {
        string r = Str(a, "ref", "");
        AutomationElement e;
        if (!refs.TryGetValue(r, out e)) throw new AgentError("unknown ref '" + r + "' - refs are reset by every snapshot");
        return e;
    }

    static Dictionary<string, object> Snapshot(Dictionary<string, object> a)
    {
        IntPtr h = PickWindow(a);
        int max = Int(a, "max", 250), maxDepth = Int(a, "depth", 60);
        bool all = Bool(a, "all");
        interactiveOnly = Bool(a, "interactive");
        refs.Clear(); refCounter = 0;
        AutomationElement root;
        using (TreeRequest(TreeScope.Element | TreeScope.Descendants).Activate()) root = AutomationElement.FromHandle(h);
        var nodes = new List<object>();
        bool truncated = false;
        Walk(root, 0, 0, maxDepth, max, all, nodes, ref truncated);
        var r = Ok();
        r["window"] = WinInfo(h);
        r["nodes"] = nodes;
        r["truncated"] = truncated;
        return r;
    }

    // interactive mode (-i): only what can be clicked or typed into, as a flat list - far fewer tokens
    static bool interactiveOnly;
    static readonly HashSet<string> InteractiveRoles = new HashSet<string> {
        "button", "link", "radio", "checkbox", "combobox", "tab", "menuitem", "listitem", "row", "treeitem",
        "textfield", "slider", "spinner", "splitbutton" };

    static void Walk(AutomationElement e, int depth, int level, int maxDepth, int max, bool all, List<object> nodes, ref bool truncated)
    {
        if (nodes.Count >= max) { truncated = true; return; }
        bool emit;
        var info = NodeInfo(e, all, out emit);
        if (info == null) return; // offscreen subtree
        int childDepth = depth;
        if (emit && (!interactiveOnly || info.ContainsKey("value") || InteractiveRoles.Contains((string)info["role"])))
        {
            info["ref"] = AddRef(e);
            info["depth"] = interactiveOnly ? 0 : depth;
            nodes.Add(info);
            childDepth = depth + 1;
        }
        if (level >= maxDepth) return;
        AutomationElementCollection kids;
        try { kids = e.CachedChildren; } catch { return; }
        foreach (AutomationElement k in kids)
        {
            Walk(k, childDepth, level + 1, maxDepth, max, all, nodes, ref truncated);
            if (truncated) return;
        }
    }

    // ---------- find / wait ----------
    static List<KeyValuePair<AutomationElement, Dictionary<string, object>>> Search(Dictionary<string, object> a, int limit)
    {
        string text = Str(a, "text", ""), role = Str(a, "role", "").ToLowerInvariant(), id = Str(a, "id", "");
        var found = new List<KeyValuePair<AutomationElement, Dictionary<string, object>>>();
        var windows = new List<IntPtr>();
        if (Has(a, "window") || Has(a, "app") || Has(a, "handle")) windows.Add(PickWindow(a));
        else { IntPtr fg = Native.GetForegroundWindow(); if (fg != IntPtr.Zero) windows.Add(fg); }
        foreach (var h in windows)
        {
            AutomationElement root;
            using (TreeRequest(TreeScope.Element | TreeScope.Descendants).Activate()) root = AutomationElement.FromHandle(h);
            var stack = new Stack<AutomationElement>();
            stack.Push(root);
            while (stack.Count > 0 && found.Count < limit)
            {
                var e = stack.Pop();
                bool emit;
                var info = NodeInfo(e, true, out emit);
                if (info != null)
                {
                    string name = Convert.ToString(info["name"]);
                    string val = info.ContainsKey("value") ? Convert.ToString(info["value"]) : "";
                    string eid = Convert.ToString(Cached(e, AutomationElement.AutomationIdProperty) ?? "");
                    bool m = (text.Length == 0 || name.IndexOf(text, StringComparison.OrdinalIgnoreCase) >= 0 || val.IndexOf(text, StringComparison.OrdinalIgnoreCase) >= 0)
                        && (role.Length == 0 || Convert.ToString(info["role"]) == role)
                        && (id.Length == 0 || string.Equals(eid, id, StringComparison.Ordinal));
                    if (m && (text.Length > 0 || role.Length > 0 || id.Length > 0)) found.Add(new KeyValuePair<AutomationElement, Dictionary<string, object>>(e, info));
                }
                AutomationElementCollection kids;
                try { kids = e.CachedChildren; } catch { continue; }
                for (int i = kids.Count - 1; i >= 0; i--) stack.Push(kids[i]);
            }
        }
        return found;
    }

    static Dictionary<string, object> Find(Dictionary<string, object> a)
    {
        var hits = Search(a, Int(a, "max", 20));
        var nodes = new List<object>();
        foreach (var kv in hits) { kv.Value["ref"] = AddRef(kv.Key); kv.Value["depth"] = 0; nodes.Add(kv.Value); }
        var r = Ok();
        r["nodes"] = nodes;
        return r;
    }

    static Dictionary<string, object> Wait(Dictionary<string, object> a)
    {
        double timeout = Dbl(a, "timeout", 10);
        bool gone = Bool(a, "gone");
        var sw = Stopwatch.StartNew();
        while (true)
        {
            List<KeyValuePair<AutomationElement, Dictionary<string, object>>> hits;
            try { hits = Search(a, 1); }
            catch (AgentError) { hits = new List<KeyValuePair<AutomationElement, Dictionary<string, object>>>(); } // window not there yet
            catch (ElementNotAvailableException) { hits = new List<KeyValuePair<AutomationElement, Dictionary<string, object>>>(); }
            if (!gone && hits.Count > 0)
            {
                var r = Ok();
                hits[0].Value["ref"] = AddRef(hits[0].Key); hits[0].Value["depth"] = 0;
                r["nodes"] = new List<object> { hits[0].Value };
                r["waited"] = Math.Round(sw.Elapsed.TotalSeconds, 2);
                return r;
            }
            if (gone && hits.Count == 0) { var r = Ok(); r["waited"] = Math.Round(sw.Elapsed.TotalSeconds, 2); return r; }
            if (sw.Elapsed.TotalSeconds >= timeout) throw new AgentError("timeout after " + timeout + " s waiting for " + (gone ? "disappearance" : "element"));
            Thread.Sleep(150);
        }
    }

    // ---------- screenshot ----------
    static Dictionary<string, object> Shot(Dictionary<string, object> a)
    {
        int x, y, w, hgt;
        if (Has(a, "ref"))
        {
            var e = GetRef(a);
            var br = e.Current.BoundingRectangle;
            x = (int)br.X; y = (int)br.Y; w = (int)br.Width; hgt = (int)br.Height;
        }
        else if (Has(a, "window") || Has(a, "app") || Has(a, "handle") || Bool(a, "foreground"))
        {
            int[] r = WindowRect(PickWindow(a)); x = r[0]; y = r[1]; w = r[2]; hgt = r[3];
        }
        else { x = Native.GetSystemMetrics(76); y = Native.GetSystemMetrics(77); w = Native.GetSystemMetrics(78); hgt = Native.GetSystemMetrics(79); }
        if (w <= 0 || hgt <= 0) throw new AgentError("empty capture region");
        int maxSide = Int(a, "max", 1280);
        double scale = Math.Max(1.0, (double)Math.Max(w, hgt) / maxSide);
        int ow = (int)Math.Round(w / scale), oh = (int)Math.Round(hgt / scale);
        byte[] png;
        using (var full = new Bitmap(w, hgt, PixelFormat.Format32bppArgb))
        {
            Overlay.HideForCapture(true);
            try { using (var g = Graphics.FromImage(full)) g.CopyFromScreen(x, y, 0, 0, new Size(w, hgt), CopyPixelOperation.SourceCopy); }
            finally { Overlay.HideForCapture(false); }
            using (var outBmp = new Bitmap(ow, oh, PixelFormat.Format24bppRgb))
            {
                using (var g = Graphics.FromImage(outBmp))
                {
                    g.InterpolationMode = scale > 1.01 ? InterpolationMode.HighQualityBicubic : InterpolationMode.NearestNeighbor;
                    g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    g.DrawImage(full, 0, 0, ow, oh);
                }
                using (var ms = new MemoryStream()) { outBmp.Save(ms, ImageFormat.Png); png = ms.ToArray(); }
            }
        }
        shotScale = scale; shotX0 = x; shotY0 = y; haveShot = true;
        var res = Ok();
        res["png"] = Convert.ToBase64String(png);
        res["width"] = ow; res["height"] = oh; res["scale"] = Math.Round(scale, 4);
        res["origin"] = new int[] { x, y };
        return res;
    }

    // ---------- input ----------
    static int[] Point(Dictionary<string, object> a, string xk, string yk)
    {
        double x = Dbl(a, xk, 0), y = Dbl(a, yk, 0);
        if (Bool(a, "img"))
        {
            if (!haveShot) throw new AgentError("--img needs a screenshot first");
            return new int[] { (int)Math.Round(shotX0 + x * shotScale), (int)Math.Round(shotY0 + y * shotScale) };
        }
        if (Bool(a, "local"))
        {
            int[] wr = WindowRect(PickWindow(a)); // window-local: offset by the window's top-left corner
            return new int[] { (int)Math.Round(wr[0] + x), (int)Math.Round(wr[1] + y) };
        }
        return new int[] { (int)Math.Round(x), (int)Math.Round(y) };
    }

    static int[] Center(AutomationElement e)
    {
        System.Windows.Point p;
        if (e.TryGetClickablePoint(out p)) return new int[] { (int)p.X, (int)p.Y };
        var r = e.Current.BoundingRectangle;
        if (r.IsEmpty || r.Width <= 0) throw new AgentError("element has no on-screen position (offscreen or collapsed)");
        return new int[] { (int)(r.X + r.Width / 2), (int)(r.Y + r.Height / 2) };
    }

    static int[] Target(Dictionary<string, object> a)
    {
        if (Has(a, "ref")) return Center(GetRef(a));
        if (Has(a, "x") && Has(a, "y")) return Point(a, "x", "y");
        Native.POINT c; Native.GetCursorPos(out c);
        return new int[] { c.X, c.Y };
    }

    static void Mouse(uint flags, int data)
    {
        var inp = new Native.INPUT[1];
        inp[0].type = 0;
        inp[0].u.mi.dwFlags = flags;
        inp[0].u.mi.mouseData = (uint)data;
        Native.SendInput(1, inp, Marshal.SizeOf(typeof(Native.INPUT)));
    }

    static Dictionary<string, object> Click(Dictionary<string, object> a)
    {
        RequireInput();
        int[] p = Target(a);
        string button = Str(a, "button", "left");
        uint down = 0x0002, up = 0x0004;
        if (button == "right") { down = 0x0008; up = 0x0010; }
        else if (button == "middle") { down = 0x0020; up = 0x0040; }
        Native.SetCursorPos(p[0], p[1]);
        Thread.Sleep(15);
        int count = Bool(a, "double") ? 2 : 1;
        for (int i = 0; i < count; i++) { Mouse(down, 0); Mouse(up, 0); if (i + 1 < count) Thread.Sleep(40); }
        Thread.Sleep(Int(a, "settle", 120));
        var r = Post();
        r["at"] = p;
        return r;
    }

    static Dictionary<string, object> MoveTo(Dictionary<string, object> a)
    {
        RequireInput();
        int[] p = Target(a);
        Native.SetCursorPos(p[0], p[1]);
        Thread.Sleep(Int(a, "settle", 80));
        var r = Post(); r["at"] = p; return r;
    }

    static Dictionary<string, object> Drag(Dictionary<string, object> a)
    {
        RequireInput();
        int[] p1 = Point(a, "x", "y"), p2 = Point(a, "x2", "y2");
        Native.SetCursorPos(p1[0], p1[1]); Thread.Sleep(30);
        Mouse(0x0002, 0); Thread.Sleep(60);
        int steps = 12;
        for (int i = 1; i <= steps; i++)
        {
            Native.SetCursorPos(p1[0] + (p2[0] - p1[0]) * i / steps, p1[1] + (p2[1] - p1[1]) * i / steps);
            Mouse(0x0001, 0); // a relative zero move makes apps that ignore SetCursorPos see movement
            Thread.Sleep(15);
        }
        Thread.Sleep(60); Mouse(0x0004, 0);
        Thread.Sleep(Int(a, "settle", 150));
        return Post();
    }

    static Dictionary<string, object> Scroll(Dictionary<string, object> a)
    {
        RequireInput();
        if (Has(a, "ref") || Has(a, "x")) { int[] p = Target(a); Native.SetCursorPos(p[0], p[1]); Thread.Sleep(15); }
        int dy = Int(a, "dy", 0), dx = Int(a, "dx", 0);
        for (int i = 0; i < Math.Abs(dy); i++) { Mouse(0x0800, dy > 0 ? -120 : 120); Thread.Sleep(10); }
        for (int i = 0; i < Math.Abs(dx); i++) { Mouse(0x01000, dx > 0 ? 120 : -120); Thread.Sleep(10); }
        Thread.Sleep(Int(a, "settle", 120));
        return Post();
    }

    static void RequireNotPassword(AutomationElement e, Dictionary<string, object> a)
    {
        if (Bool(a, "password_ok")) return;
        try
        {
            if (e != null && e.Current.IsPassword)
                throw new AgentError("target is a password field: the user enters secrets (pass --password-ok only with explicit consent)");
        }
        catch (ElementNotAvailableException) { }
    }

    static Dictionary<string, object> Press(Dictionary<string, object> a)
    {
        RequireInput();
        var e = GetRef(a);
        object p;
        string how;
        if (e.TryGetCurrentPattern(InvokePattern.Pattern, out p)) { ((InvokePattern)p).Invoke(); how = "invoke"; }
        else if (e.TryGetCurrentPattern(TogglePattern.Pattern, out p)) { ((TogglePattern)p).Toggle(); how = "toggle"; }
        else if (e.TryGetCurrentPattern(SelectionItemPattern.Pattern, out p)) { ((SelectionItemPattern)p).Select(); how = "select"; }
        else if (e.TryGetCurrentPattern(ExpandCollapsePattern.Pattern, out p))
        {
            var ec = (ExpandCollapsePattern)p;
            if (ec.Current.ExpandCollapseState == ExpandCollapseState.Collapsed) ec.Expand(); else ec.Collapse();
            how = "expand/collapse";
        }
        else
        {
            int[] c = Center(e);
            Native.SetCursorPos(c[0], c[1]); Thread.Sleep(15); Mouse(0x0002, 0); Mouse(0x0004, 0);
            how = "click (no invoke pattern)";
        }
        Thread.Sleep(Int(a, "settle", 150));
        var r = Post(); r["how"] = how; return r;
    }

    static Dictionary<string, object> SetValue(Dictionary<string, object> a)
    {
        RequireInput();
        var e = GetRef(a);
        RequireNotPassword(e, a);
        string text = Str(a, "text", "");
        object p;
        string how;
        if (e.TryGetCurrentPattern(ValuePattern.Pattern, out p) && !((ValuePattern)p).Current.IsReadOnly)
        { ((ValuePattern)p).SetValue(text); how = "value pattern"; }
        else
        {
            try { e.SetFocus(); } catch { }
            SendCombo(new ushort[] { 0x11, 0x41 }); // ctrl+a
            SendText(text);
            how = "select-all + type";
        }
        Thread.Sleep(Int(a, "settle", 80));
        var r = Post(); r["how"] = how; return r;
    }

    static Dictionary<string, object> FocusRef(Dictionary<string, object> a)
    {
        RequireInput();
        var e = GetRef(a);
        e.SetFocus();
        Thread.Sleep(Int(a, "settle", 80));
        return Post();
    }

    static Dictionary<string, object> TypeText(Dictionary<string, object> a)
    {
        RequireInput();
        AutomationElement target = null;
        if (Has(a, "ref")) { target = GetRef(a); try { target.SetFocus(); } catch { } Thread.Sleep(40); }
        else { RequireVisibleForeground(); try { target = AutomationElement.FocusedElement; } catch { } }
        RequireNotPassword(target, a);
        SendText(Str(a, "text", ""));
        Thread.Sleep(Int(a, "settle", 80));
        return Post();
    }

    static void SendText(string text)
    {
        var batch = new List<Native.INPUT>();
        foreach (char ch in text)
        {
            if (ch == '\r') continue;
            if (ch == '\n' || ch == '\t')
            {
                Flush(batch);
                ushort vk = ch == '\n' ? (ushort)0x0D : (ushort)0x09;
                SendKeys(new ushort[] { vk }, true); SendKeys(new ushort[] { vk }, false);
                continue;
            }
            batch.Add(KeyInput(0, ch, 0x0004));
            batch.Add(KeyInput(0, ch, 0x0004 | 0x0002));
            if (batch.Count >= 64) Flush(batch);
        }
        Flush(batch);
    }

    static void Flush(List<Native.INPUT> batch)
    {
        if (batch.Count == 0) return;
        Native.SendInput((uint)batch.Count, batch.ToArray(), Marshal.SizeOf(typeof(Native.INPUT)));
        batch.Clear();
        Thread.Sleep(5);
    }

    static Native.INPUT KeyInput(ushort vk, ushort scan, uint flags)
    {
        var i = new Native.INPUT();
        i.type = 1;
        i.u.ki.wVk = vk; i.u.ki.wScan = scan; i.u.ki.dwFlags = flags;
        return i;
    }

    static readonly HashSet<ushort> Extended = new HashSet<ushort> { 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0x90, 0x2C };

    static void SendKeys(ushort[] vks, bool down)
    {
        var inp = new Native.INPUT[vks.Length];
        for (int i = 0; i < vks.Length; i++)
        {
            ushort vk = down ? vks[i] : vks[vks.Length - 1 - i];
            uint flags = (down ? 0u : 0x0002u) | (Extended.Contains(vk) ? 0x0001u : 0u);
            inp[i] = KeyInput(vk, (ushort)Native.MapVirtualKey(vk, 0), flags);
        }
        Native.SendInput((uint)inp.Length, inp, Marshal.SizeOf(typeof(Native.INPUT)));
    }

    static void SendCombo(ushort[] vks)
    {
        SendKeys(vks, true);
        Thread.Sleep(20);
        SendKeys(vks, false);
    }

    static readonly Dictionary<string, ushort> Named = new Dictionary<string, ushort> {
        { "ctrl", 0x11 }, { "shift", 0x10 }, { "alt", 0x12 }, { "win", 0x5B },
        { "enter", 0x0D }, { "tab", 0x09 }, { "esc", 0x1B }, { "space", 0x20 }, { "backspace", 0x08 },
        { "delete", 0x2E }, { "insert", 0x2D }, { "home", 0x24 }, { "end", 0x23 }, { "pageup", 0x21 }, { "pagedown", 0x22 },
        { "left", 0x25 }, { "up", 0x26 }, { "right", 0x27 }, { "down", 0x28 }, { "capslock", 0x14 },
        { "printscreen", 0x2C }, { "menu", 0x5D }, { "plus", 0xBB }, { "minus", 0xBD } };

    static ushort Vk(string k)
    {
        ushort vk;
        if (Named.TryGetValue(k, out vk)) return vk;
        if (k.Length >= 2 && k[0] == 'f')
        {
            int n;
            if (int.TryParse(k.Substring(1), out n) && n >= 1 && n <= 24) return (ushort)(0x70 + n - 1);
        }
        if (k.Length == 1)
        {
            char c = char.ToUpperInvariant(k[0]);
            if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) return c;
            short s = Native.VkKeyScan(k[0]);
            if (s != -1) return (ushort)(s & 0xFF);
        }
        throw new AgentError("unknown key '" + k + "'");
    }

    static Dictionary<string, object> Key(Dictionary<string, object> a)
    {
        RequireInput();
        RequireVisibleForeground();
        object ko; a.TryGetValue("keys", out ko);
        var list = ko as ArrayList;
        if (list == null || list.Count == 0) throw new AgentError("key needs keys");
        var vks = new ushort[list.Count];
        for (int i = 0; i < list.Count; i++)
        {
            string k = Convert.ToString(list[i]);
            vks[i] = (k == "cmd" || k == "mod") ? (ushort)0x11 : Vk(k); // mod and cmd map to ctrl on Windows
        }
        int times = Math.Max(1, Int(a, "times", 1));
        for (int t = 0; t < times; t++) { SendCombo(vks); Thread.Sleep(30); }
        Thread.Sleep(Int(a, "settle", 120));
        return Post();
    }

    // ---------- launch ----------
    static Dictionary<string, object> Launch(Dictionary<string, object> a)
    {
        RequireInput();
        string target = Str(a, "target", "");
        if (target.Length == 0) throw new AgentError("launch needs a target");
        var before = new HashSet<IntPtr>(TopWindows());
        var psi = new ProcessStartInfo(target, Str(a, "args", ""));
        psi.UseShellExecute = true;
        psi.WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        Process proc = Process.Start(psi);
        double timeout = Dbl(a, "timeout", 15);
        string waitTitle = Str(a, "wait", "");
        var sw = Stopwatch.StartNew();
        IntPtr win = IntPtr.Zero;
        while (sw.Elapsed.TotalSeconds < timeout)
        {
            foreach (var h in TopWindows())
            {
                if (waitTitle.Length > 0) { if (WindowTitle(h).IndexOf(waitTitle, StringComparison.OrdinalIgnoreCase) >= 0) { win = h; break; } }
                else if (!before.Contains(h)) { win = h; break; }
            }
            if (win != IntPtr.Zero) break;
            Thread.Sleep(150);
        }
        var r = Ok();
        if (proc != null) { try { r["pid"] = proc.Id; } catch { } }
        if (win == IntPtr.Zero)
        {
            r["note"] = "no new window within " + timeout + " s (single-instance apps may reuse an existing window)";
        }
        else
        {
            BringToFront(win);
            Thread.Sleep(Int(a, "settle", 200));
            r["window"] = WinInfo(win);
        }
        r["post"] = PostState();
        return r;
    }
}

static class Native
{
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Explicit)] public struct InputUnion { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
    [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public InputUnion u; }
    public delegate bool EnumProc(IntPtr h, IntPtr l);

    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern uint SendInput(uint n, INPUT[] inputs, int size);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int i);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern bool SetWindowDisplayAffinity(IntPtr h, uint affinity);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr h, int i);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr zero);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern short VkKeyScan(char c);
    [DllImport("user32.dll")] public static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll")] public static extern bool CloseDesktop(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern bool GetUserObjectInformation(IntPtr h, int index, byte[] info, uint len, out uint need);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int attr, out int v, int size);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int attr, out RECT v, int size);
}
