#!/usr/bin/env python3
import socket
import threading
import time

def forward(src, dst):
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
            dst.close()
        except Exception:
            pass

def handle_client(client):
    upstream = None
    for _ in range(50):
        try:
            upstream = socket.create_connection(('127.0.0.1', 9223), timeout=2.0)
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)

    if not upstream:
        try:
            client.close()
        except Exception:
            pass
        return

    try:
        t1 = threading.Thread(target=forward, args=(client, upstream), daemon=True)
        t2 = threading.Thread(target=forward, args=(upstream, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception:
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', 9222))
    srv.listen(64)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()

if __name__ == '__main__':
    main()
