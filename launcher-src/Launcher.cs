using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Security.Cryptography;

class Launcher {
#if BACKEND
    const string Title = "easyERP · 后端 SQL";
    const string Script = "start-backend.ps1";
    const string LogName = "launcher-backend.log";
    const string Message = "正在启动数据库与 SQL 界面…";
#else
    const string Title = "easyERP · 前端工作台";
    const string Script = "start-frontend.ps1";
    const string LogName = "launcher-frontend.log";
    const string Message = "正在启动数据库与前端工作台…";
#endif
    static string Root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
    static string LogFile;
    [STAThread]
    static int Main(string[] args) {
        string suffix;
        using(SHA256 hash = SHA256.Create()) suffix = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Root.ToLowerInvariant()))).Replace("-", "").Substring(0,16);
        using(Mutex mutex = new Mutex(false, "Local\\easyERP_" + Script + "_" + suffix)) {
            try { if(!mutex.WaitOne(0)) return 0; } catch(AbandonedMutexException) {}
            try { return Start(args); } finally { mutex.ReleaseMutex(); }
        }
    }
    static int Start(string[] args) {
        bool check = Array.IndexOf(args, "--check") >= 0;
        bool smoke = Array.IndexOf(args, "--smoke") >= 0;
        try {
            string script = Path.Combine(Root, "bin", Script);
            if (!File.Exists(script)) throw new Exception("请将启动文件保留在 easyerp-0.2 目录内；找不到 bin\\" + Script);
            string logs = Path.Combine(Root, "var", "log");
            Directory.CreateDirectory(logs);
            LogFile = Path.Combine(logs, LogName);
            if (check || smoke) return Run(script, smoke);
            Application.EnableVisualStyles();
            Form form = new Form();
            form.Text = Title;
            form.ClientSize = new Size(420, 130);
            form.StartPosition = FormStartPosition.CenterScreen;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.MaximizeBox = false; form.MinimizeBox = false;
            form.ControlBox = false;
            form.Font = new Font("Microsoft YaHei UI", 10F);
            Label label = new Label();
            label.Text = Message; label.SetBounds(24, 23, 375, 32);
            ProgressBar progress = new ProgressBar();
            progress.Style = ProgressBarStyle.Marquee; progress.SetBounds(25, 72, 370, 12);
            form.Controls.Add(label); form.Controls.Add(progress);
            int result = 1;
            form.Shown += delegate {
                ThreadPool.QueueUserWorkItem(delegate {
                    string error = null;
                    try { result = Run(script, true); if (result != 0) error = "启动失败，详情已写入：\n" + LogFile; }
                    catch(Exception ex) { error = ex.Message; WriteError(ex.ToString()); }
                    form.BeginInvoke(new Action(delegate {
                        if (error != null) MessageBox.Show(form, error, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
                        form.Close();
                    }));
                });
            };
            Application.Run(form);
            return result;
        } catch(Exception ex) {
            WriteError(ex.ToString());
            if (!check && !smoke) MessageBox.Show(ex.Message, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
    static int Run(string script, bool openBrowser) {
        string powershell = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe");
        ProcessStartInfo start = new ProcessStartInfo(powershell);
        // Use a file rather than redirected pipes: Windows background services
        // can retain inherited pipe handles after PowerShell has already exited.
        string quotedScript = "'" + script.Replace("'", "''") + "'";
        string quotedLog = "'" + LogFile.Replace("'", "''") + "'";
        string command = "$ErrorActionPreference='Stop'; try { (Get-Date).ToString('o') | Out-File -LiteralPath " + quotedLog + " -Encoding UTF8; & " + quotedScript + (openBrowser ? " -OpenBrowser" : "") + " *>&1 | Out-File -LiteralPath " + quotedLog + " -Append -Encoding UTF8; exit 0 } catch { $_ | Out-File -LiteralPath " + quotedLog + " -Append -Encoding UTF8; exit 1 }";
        start.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand " + Convert.ToBase64String(Encoding.Unicode.GetBytes(command));
        start.WorkingDirectory = Root;
        start.UseShellExecute = false; start.CreateNoWindow = true;
        start.RedirectStandardOutput = false; start.RedirectStandardError = false;
        using(Process process = new Process()) {
            process.StartInfo = start;
            process.Start();
            if (!process.WaitForExit(180000)) {
                // End only this launcher-owned PowerShell process; existing services remain intact.
                try { process.Kill(); } catch {}
                WriteError("启动超时，请检查数据库和本机界面的日志。"); return 1;
            }
            return process.ExitCode;
        }
    }
    static void WriteError(string error) {
        try { if(LogFile != null) File.AppendAllText(LogFile, error + Environment.NewLine, Encoding.UTF8); } catch {}
    }
}
