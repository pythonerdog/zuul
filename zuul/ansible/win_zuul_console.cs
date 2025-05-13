// Copyright (c) 2016 IBM Corp.
// Copyright (C) 2025 Acme Gating, LLC

// This module is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This software is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this software.  If not, see <http://www.gnu.org/licenses/>.

using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;

// This file follows the structure of win_console.py closely (meaning
// some of this code is more pythonic than C#-like).

internal class ZuulConsole : IDisposable
{
    public string path;
    public FileStream file;
    public long size;

    public ZuulConsole(string path)
    {
        this.path = path;
        this.file = new FileStream(
            path, FileMode.Open, FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete);
        this.size = new FileInfo(path).Length;
    }

    public void Dispose()
    {
        file.Dispose();
    }
}

public class Server
{
    private const int MAX_REQUEST_LEN = 1024;
    private const int REQUEST_TIMEOUT = 10;
    // This is the version we report to the zuul_stream callback.  It is
    // expected that this (zuul_console) process can be long-lived, so if
    // there are updates this ensures a later streaming callback can still
    // talk to us.
    private const int ZUUL_CONSOLE_PROTO_VERSION = 1;

    private string path;
    private Socket socket;

    public Server(string path, int port)
    {
        this.path = path;
        socket = new Socket(
            AddressFamily.InterNetworkV6,
            SocketType.Stream,
            ProtocolType.Tcp);
        socket.SetSocketOption(
            SocketOptionLevel.Socket,
            SocketOptionName.ReuseAddress, true);
        socket.SetSocketOption(
            SocketOptionLevel.IPv6,
            SocketOptionName.IPv6Only, false);
        socket.Bind(new IPEndPoint(IPAddress.Any, port));
        socket.Listen(1);
    }

    private Socket Accept()
    {
        return socket.Accept();
    }

    public void Run()
    {
        while (true)
        {
            Socket conn = Accept();
            Thread t = new Thread(StartHandleOneConnection);
            t.IsBackground = true;
            t.Start((object) conn);
        }
    }

    private void StartHandleOneConnection(object conn)
    {
        try
        {
            HandleOneConnection((Socket) conn);
        }
        catch (Exception e)
        {
            Console.WriteLine("Error in connection handler: {0}",
                              e.ToString());
        }
    }

    private ZuulConsole ChunkConsole(Socket conn, string logUuid)
    {
        ZuulConsole console;
        try
        {
            console = new ZuulConsole(string.Format(path, logUuid));
        }
        catch
        {
            return null;
        }
        while (true)
        {
            Byte[] chunk = new Byte[4096];
            int len = console.file.Read(chunk, 0, 4096);
            if (len == 0)
            {
                break;
            }
            conn.Send(chunk, len, SocketFlags.None);
        }
        return console;
    }

    private bool FollowConsole(ZuulConsole console, Socket conn)
    {
        while (true)
        {
            // As long as we have unread data, keep reading/sending
            while (true)
            {
                Byte[] chunk = new Byte[4096];
                int len = console.file.Read(chunk, 0, 4096);
                if (len > 0)
                {
                    conn.Send(chunk, len, SocketFlags.None);
                }
                else
                {
                    break;
                }
            }
            // At this point, we are waiting for more data to be written
            Thread.Sleep(500);

            // Check to see if the remote end has sent any data,
            // if so, discard
            if (conn.Poll(0, SelectMode.SelectError))
            {
                return false;
            }
            if (conn.Poll(0, SelectMode.SelectRead))
            {
                Byte[] chunk = new Byte[4096];
                int ret = conn.Receive(chunk);
                // Discard anything read, if input is eof, it has
                // disconnected.
                if (ret == 0)
                    return false;
            }

            // See if the file has been truncated
            try
            {
                long currentSize = new FileInfo(console.path).Length;
                if (currentSize < console.size)
                {
                    return true;
                }
                console.size = currentSize;
            } catch {
                return true;
            }
        }
    }
    private string GetCommand(Socket conn)
    {
        Byte[] buff = new Byte[MAX_REQUEST_LEN];
        DateTime start = DateTime.UtcNow;
        int pos = 0;

        while (true)
        {
            int elapsed = (DateTime.UtcNow - start).Seconds;
            int timeout = Math.Max(REQUEST_TIMEOUT - elapsed, 0);
            if (timeout == 0)
            {
                throw new Exception("Timeout while waiting for input");
            }

            if (conn.Poll(0, SelectMode.SelectRead))
            {
                int len = conn.Receive(buff, pos, MAX_REQUEST_LEN - pos,
                                       SocketFlags.None);
                if (len == 0) {
                    throw new Exception("Remote side closed connection");
                }
            }
            if (conn.Poll(0, SelectMode.SelectError))
            {
                throw new Exception("Received error event");
            }

            if (pos >= MAX_REQUEST_LEN)
            {
                throw new Exception("Request too long");
            }

            try
            {
                string ret = System.Text.Encoding.UTF8.GetString(buff);
                int x = ret.IndexOf('\n');
                if (x > 0)
                {
                    return ret.Substring(0,x).Trim();
                }
            }
            catch
            {
            }
        }
    }
    private string CleanUuid(string logUuid)
    {
        // Make use the input isn't trying to be clever and
        // construct some path like /tmp/console-/../../something
        return Path.GetFileName(logUuid);
    }

    private void HandleOneConnection(Socket conn)
    {
        // V1 protocol
        // -----------
        //  v:<ver>    get version number, <ver> is remote version
        //  s:<uuid>   send logs for <uuid>
        //  f:<uuid>   finalise/cleanup <uuid>
        string logUuid;

        while (true)
        {
            string command = GetCommand(conn);
            if (command.StartsWith("v:"))
            {
                // NOTE(ianw) : remote sends its version.  We currently
                // don't have anything to do with this value, so ignore
                // for now.
                conn.Send(
                    System.Text.Encoding.UTF8.GetBytes(
                        String.Format("{0}\n", ZUUL_CONSOLE_PROTO_VERSION)));
                continue;
            }
            else if (command.StartsWith("f:"))
            {
                logUuid = CleanUuid(command.Substring(2));
                try
                {
                    File.Delete(string.Format(path, logUuid));
                }
                catch
                {
                }
                continue;
            }
            else if (command.StartsWith("s:"))
            {
                logUuid = CleanUuid(command.Substring(2));
                break;
            }
            else
            {
                // NOTE(ianw): 2022-07-21 In releases < 6.3.0 the streaming
                // side would just send a raw uuid and nothing else; so by
                // default assume that is what is coming in here.  We can
                // remove this fallback when we decide it is no longer
                // necessary.
                logUuid = CleanUuid(command);
                break;
            }
        }

        // FIXME: this won't notice disconnects until it tries to send
        ZuulConsole console = null;
        try
        {
            while (true)
            {
                if (console != null)
                {
                    try
                    {
                        console.Dispose();
                    }
                    catch
                    {
                    }
                }
                while (true)
                {
                    console = ChunkConsole(conn, logUuid);
                    if (console != null)
                    {
                        break;
                    }
                    conn.Send(System.Text.Encoding.UTF8.GetBytes(
                                  "[Zuul] Log not found\n"));
                    Thread.Sleep(500);
                }
                while (true)
                {
                    if (FollowConsole(console, conn))
                    {
                        break;
                    }
                    else
                    {
                        return;
                    }
                }
            }
        } finally {
            conn.Close();
            if (console != null)
            {
                console.Dispose();
            }
        }
    }
}

public class WinZuulConsole
{
    public static void Main(string[] args)
    {
        if (args.Length < 2)
        {
            throw new Exception("Not enough arguments");
        }

        string path = System.Text.Encoding.UTF8.GetString(
        Convert.FromBase64String(args[0]));
        int port = Int32.Parse(args[1]);

        Server s = new Server(path, port);
        s.Run();
    }
}
