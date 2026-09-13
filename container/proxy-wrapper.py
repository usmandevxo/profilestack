#!/usr/bin/env python3
"""
proxy-wrapper.py - Local SOCKS5 server forwarder that authenticates to upstream proxy.
Chromium does not support user:pass credentials in CLI arguments for SOCKS5 proxies.
This daemon runs on 127.0.0.1:1081 with no-auth and forwards credentials upstream.
"""
import base64
import os
import socket
import struct
import threading

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(os.environ.get("CHROME_PROXY_LOCAL_PORT", "1081"))

SCHEME = os.environ.get("CHROME_PROXY_SCHEME", "socks5")
UPSTREAM_HOST = os.environ.get("CHROME_PROXY_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.environ.get("CHROME_PROXY_PORT", "1080"))
USER = os.environ.get("CHROME_PROXY_USER", "")
PASS = os.environ.get("CHROME_PROXY_PASS", "")


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def socks5_connect(upstream, host, port):
    upstream.sendall(b"\x05\x01\x02")
    resp = recv_exact(upstream, 2)
    if resp[1] != 0x02:
        raise ConnectionError(f"upstream SOCKS5 rejected auth method: {resp.hex()}")
    u, p = USER.encode(), PASS.encode()
    upstream.sendall(bytes([0x01, len(u)]) + u + bytes([len(p)]) + p)
    resp = recv_exact(upstream, 2)
    if resp[1] != 0x00:
        raise ConnectionError(f"upstream SOCKS5 auth failed: {resp.hex()}")
    h = host.encode()
    upstream.sendall(b"\x05\x01\x00\x03" + bytes([len(h)]) + h + struct.pack(">H", port))
    resp = recv_exact(upstream, 4)
    if resp[1] != 0x00:
        raise ConnectionError(f"upstream SOCKS5 connect failed: {resp.hex()}")
    if resp[3] == 0x01:
        recv_exact(upstream, 4 + 2)
    elif resp[3] == 0x03:
        ln = recv_exact(upstream, 1)[0]
        recv_exact(upstream, ln + 2)
    elif resp[3] == 0x04:
        recv_exact(upstream, 16 + 2)


def http_connect(upstream, host, port):
    creds = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    req = (
        f"CONNECT {host}:{port} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Proxy-Authorization: Basic {creds}\r\n"
        f"Proxy-Connection: keep-alive\r\n\r\n"
    )
    upstream.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = upstream.recv(4096)
        if not chunk:
            raise ConnectionError("upstream closed during CONNECT")
        buf += chunk
    status = buf.split(b"\r\n", 1)[0]
    if b" 200 " not in status:
        raise ConnectionError(f"upstream CONNECT failed: {status.decode(errors='replace')}")


def tunnel(client, upstream):
    def pipe(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    t1 = threading.Thread(target=pipe, args=(client, upstream), daemon=True)
    t2 = threading.Thread(target=pipe, args=(upstream, client), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def handle(client):
    try:
        data = recv_exact(client, 2)
        if data[0] != 0x05:
            raise ConnectionError(f"not a SOCKS5 greeting: {data.hex()}")
        methods = recv_exact(client, data[1])
        if 0x00 not in methods:
            client.sendall(b"\x05\xff")
            raise ConnectionError("client offered no acceptable auth method")
        client.sendall(b"\x05\x00")

        data = recv_exact(client, 4)
        if data[1] != 0x01:
            client.sendall(b"\x05\x07")
            raise ConnectionError("only CONNECT is supported")
        atyp = data[3]
        if atyp == 0x01:
            host = socket.inet_ntoa(recv_exact(client, 4))
        elif atyp == 0x03:
            ln = recv_exact(client, 1)[0]
            host = recv_exact(client, ln).decode()
        elif atyp == 0x04:
            host = socket.inet_ntop(socket.AF_INET6, recv_exact(client, 16))
        else:
            raise ConnectionError(f"bad address type: {atyp}")
        port = struct.unpack(">H", recv_exact(client, 2))[0]

        upstream = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=15)
        if SCHEME.startswith("socks"):
            socks5_connect(upstream, host, port)
        else:
            http_connect(upstream, host, port)

        client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        tunnel(client, upstream)
    except Exception as e:
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(16)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()

# [ProfileStack v1.10.10] revision checkpoint
