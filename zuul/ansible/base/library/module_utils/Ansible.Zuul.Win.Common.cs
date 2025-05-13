// Copyright (c) 2016 IBM Corp.
// Copyright (C) 2025 Acme Gating, LLC
//
// This module is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This software is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this software.  If not, see <http://www.gnu.org/licenses/>.

using Microsoft.Win32.SafeHandles;
using System.Runtime.InteropServices;
using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Text.RegularExpressions;
using System.Xml;

//AssemblyReference -Name netstandard.dll
//AssemblyReference -Name System.Xml.dll
//AssemblyReference -Name System.Xml.ReaderWriter.dll

namespace Ansible.Zuul.Win.Common
{
    internal class NativeMethods
    {
        // The collections Process file includes this, but not the
        // core Process file, so we go aheand and import it ourselves.
        // From
        // https://github.com/ansible-collections/ansible.windows/blob/2.5.0/plugins/module_utils/Process.cs
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern bool TerminateProcess(
            SafeHandle hProcess,
            UInt32 lpExitCode);
    }

    // From
    // https://github.com/ansible-collections/ansible.windows/blob/2.5.0/plugins/module_utils/Process.cs
    public class Win32Exception : System.ComponentModel.Win32Exception
    {
        private string _msg;

        public Win32Exception(string message) : this(Marshal.GetLastWin32Error(), message) { }
        public Win32Exception(int errorCode, string message) : base(errorCode)
        {
            _msg = String.Format("{0} ({1}, Win32ErrorCode {2} - 0x{2:X8})", message, base.Message, errorCode);
        }

        public override string Message { get { return _msg; } }
        public static explicit operator Win32Exception(string message) { return new Win32Exception(message); }
    }

    public class ZuulStreamReader : StreamReader
    {
        private StringBuilder sb = new StringBuilder();

        public ZuulStreamReader(Stream stream, Encoding enc, bool order, Int32 size) : base(stream, enc, order, size) {}

        // This overrides the base class to include the newline sequence.
        public override string ReadLine()
        {
            while (true)
            {
                int c = Read();
                if (c == -1)
                {
                    if (sb.Length == 0)
                    {
                        return null;
                    }
                    string ret = sb.ToString();
                    sb = new StringBuilder();
                    return ret;
                }
                char ch = (char)c;
                sb.Append(ch);
                if (ch == '\r' && Peek() == '\n')
                {
                    sb.Append((char)Read());
                }
                if (ch == '\r' || ch == '\n')
                {
                    string ret = sb.ToString();
                    sb = new StringBuilder();
                    return ret;
                }
            }
        }
    }

    internal class ZuulConsole : IDisposable
    {
        private StreamWriter logFile;

        public ZuulConsole(string zuulLogId, string zuulLogPath)
        {
            if (zuulLogId == "in-loop-ignore")
            {
                logFile = null;
            }
            else if (zuulLogId == "skip")
            {
                logFile = null;
            }
            else
            {
                Directory.CreateDirectory(Path.GetDirectoryName(zuulLogPath));
                logFile = new StreamWriter(zuulLogPath);
            }
        }

        public void Dispose() {
            if (logFile != null)
            {
                logFile.Dispose();
            }
        }

        public void AddLine(string ln)
        {
            // Note this format with deliminator is "inspired" by the old
            // Jenkins format but with microsecond resolution instead of
            // millisecond.  It is kept so log parsing/formatting remains
            // consistent.
            if (logFile != null) {
                lock(logFile) {
                    string ts = DateTime.Now.ToString("yyy-MM-dd HH:mm:ss.ffffff");
                    string outln = string.Format("{0} | {1}", ts, ln);
                    logFile.Write(outln);
                    logFile.Flush();
                }
            }
        }
        public void LogExitCode(UInt32 rc)
        {
            AddLine(string.Format("[Zuul] Task exit code: {0}\n", rc));
        }
    }
    internal class StreamFollower : IDisposable
    {
        // Unlike the python equivalent, we never supported combining
        // output and error streams, so this class always uses both.
        private SafeHandle process;
        private string zuulLogId;
        private string zuulLogPath;
        private StreamReader outStream;
        private StreamReader errStream;
        private UInt32 outputMaxBytes;
        // Lists to save stdout/stderr log lines in as we collect them
        public StringBuilder outLogBytes;
        public StringBuilder errLogBytes;
        private Thread stdoutThread;
        private Thread stderrThread;
        // Total size in bytes of all log and stderr_log lines
        private UInt32 logSize;
        private ZuulConsole console;
        private static Regex cliXmlRegex = new Regex("(?<clixml><Objs.+</Objs>)(?<post>.*)");

        public StreamFollower(SafeHandle process, StreamReader outStream,
                              StreamReader errStream, string zuulLogId,
                              string zuulLogPath, UInt32 outputMaxBytes)
        {
            this.process = process;
            this.zuulLogId = zuulLogId;
            this.zuulLogPath = zuulLogPath;
            this.outLogBytes = new StringBuilder();
            this.errLogBytes = new StringBuilder();
            this.outStream = outStream;
            this.errStream = errStream;
            this.outputMaxBytes = outputMaxBytes;
            this.logSize = 0;
        }

        public void Dispose()
        {
            if (console != null) {
                console.Dispose();
            }
        }

        public void Follow()
        {
            console = new ZuulConsole(zuulLogId, zuulLogPath);
            stdoutThread = new Thread(this.FollowOut);
            stdoutThread.Start();
            stderrThread = new Thread(this.FollowErr);
            stderrThread.Start();
        }

        private void FollowOut()
        {
            FollowInner(outStream, outLogBytes);
        }

        private void FollowErr()
        {
            FollowInner(errStream, errLogBytes);
        }


        private void FollowInner(StreamReader stream, StringBuilder logBytes)
        {
            // The unix/python version of this has a check that throws
            // a warning if we encounter a line without a trailing
            // newline.  That doesn't make as much sense here, so we
            // omit it.

            // These variables are used for the CLIXML handling
            // (win_shell only).
            bool first = true;
            bool cliXml = false;
            while (true)
            {
                string line = stream.ReadLine();
                if (line == null)
                {
                    break;
                }

                logSize += (UInt32) line.Length;
                if (logSize > outputMaxBytes)
                {
                    string msg = string.Format("[Zuul] Log output exceeded max of {0}, terminating\n", outputMaxBytes);
                    console.AddLine(msg);

                    if (!NativeMethods.TerminateProcess(process, 1))
                    {
                        throw new Win32Exception("TerminateProcess() failed");
                    }
                    throw new Win32Exception(msg);
                }
                logBytes.Append(line);

                // Begin CLIXML handling section (win_shell only)

                // This attempts to approximate the way the win_shell
                // module handles the output in win_shell.ps1.
                // Because the module handles the returned structured
                // output, we only apply this to the streaming logs.
                if (stream == errStream)
                {
                    try
                    {
                        if (first)
                        {
                            first = false;
                            if (line.Equals("#< CLIXML"))
                            {
                                // Switch on CLIXML handling for this stream.
                                cliXml = true;
                                continue;
                            }
                        }
                        else if (cliXml)
                        {
                            Match m = cliXmlRegex.Match(line);
                            if (m.Success)
                            {
                                XmlDocument xml = new XmlDocument();
                                xml.LoadXml(m.Groups["clixml"].Value);

                                XmlNode root = xml.DocumentElement;
                                XmlNodeList nodes = root.SelectNodes("*[local-name()='S' and @S='Error']");

                                foreach (XmlNode node in nodes)
                                {
                                    console.AddLine(node.InnerText.Replace("_x000D__x000A_", "") + "\n");
                                }
                                if (m.Groups["post"].Value.Length > 0)
                                {
                                    console.AddLine(m.Groups["post"].Value + "\n");
                                }
                                continue;
                            }
                        }
                    } catch (Exception e)
                    {
                        console.AddLine("[Zuul] Error handling CLIXML: " + e.ToString() + "\n");
                    }
                }
                // End CLIXML handling section
                console.AddLine(line);
            }
        }
        public void Join()
        {
            foreach (var thread in new Thread[] { stdoutThread, stderrThread })
            {
                // The original win_command will wait until the output
                // streams are closed before waiting for the process
                // to exit, so unlike the unix/python version, we
                // don't timeout the join.
                thread.Join();
            }
        }
        public void LogExitCode(UInt32 rc)
        {
            console.LogExitCode(rc);
        }
    }
}
