import hashlib
import os
import socket
import time
from typing import Dict, Optional, Tuple
import docker
import docker.errors
from docker.types import Ulimit
from app.config import (
    CDP_PORT_END,
    CDP_PORT_START,
    CONTAINER_PREFIX,
    DATA_DIR,
    DOCKER_IMAGE,
    VNC_PORT_END,
    VNC_PORT_START,
)
from app.validator import (
    clean_stale_locks,
    fix_profile_permissions,
    parse_proxy,
    validate_profile_name,
)
from app.proxy_manager import resolve_proxy_url

_H_FIRST = ["alex", "sam", "mike", "lisa", "chris", "pat", "lee", "tom", "jay", "kai", "max", "dan"]
_H_DEVICE = ["laptop", "desktop", "thinkpad", "studio", "workstation", "home", "book", "pc"]


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


class DockerEngine:
    def __init__(self):
        self.client = docker.from_env()
        self._ensure_image()
        self._ensure_empty_mask()

    def _ensure_empty_mask(self):
        mask_path = DATA_DIR / ".empty"
        if mask_path.is_dir():
            shutil.rmtree(mask_path, ignore_errors=True)
        if not mask_path.exists():
            mask_path.touch()
            try:
                os.chmod(mask_path, 0o664)
            except Exception:
                pass

    def _ensure_image(self):
        try:
            self.client.images.get(DOCKER_IMAGE)
        except docker.errors.ImageNotFound:
            pass

    def container_name(self, profile_name: str) -> str:
        return f"{CONTAINER_PREFIX}{validate_profile_name(profile_name)}"

    def _profile_hostname(self, profile_name: str) -> str:
        h = int(hashlib.md5(profile_name.encode()).hexdigest(), 16)
        first = _H_FIRST[h % len(_H_FIRST)]
        device = _H_DEVICE[(h >> 8) % len(_H_DEVICE)]
        return f"{first}-{device}"

    def get_container(self, profile_name: str):
        cname = self.container_name(profile_name)
        try:
            return self.client.containers.get(cname)
        except docker.errors.NotFound:
            return None

    def is_profile_running(self, profile_name: str) -> bool:
        c = self.get_container(profile_name)
        return bool(c and c.status == "running")

    def find_free_ports(self) -> Tuple[int, int]:
        """Finds free VNC and CDP ports not currently bound or used by Docker containers."""
        containers = self.client.containers.list(all=True)
        used_ports = set()
        for c in containers:
            ports = c.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
            for port_proto, bindings in ports.items():
                if bindings:
                    for b in bindings:
                        try:
                            used_ports.add(int(b.get("HostPort", 0)))
                        except (ValueError, TypeError):
                            pass

        free_vnc = None
        for p in range(VNC_PORT_START, VNC_PORT_END + 1):
            if p not in used_ports and not is_port_in_use(p):
                free_vnc = p
                break

        free_cdp = None
        for p in range(CDP_PORT_START, CDP_PORT_END + 1):
            if p not in used_ports and p != free_vnc and not is_port_in_use(p):
                free_cdp = p
                break

        if not free_vnc or not free_cdp:
            raise RuntimeError("Exhausted available port pool for VNC or CDP.")
        return free_vnc, free_cdp

    def get_profile_ports(self, profile_name: str) -> Dict[str, Optional[int]]:
        c = self.get_container(profile_name)
        if not c:
            return {"vnc_port": None, "cdp_port": None}
        ports = c.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        vnc_port = None
        cdp_port = None
        vnc_binding = ports.get("6080/tcp")
        if vnc_binding and len(vnc_binding) > 0:
            try:
                vnc_port = int(vnc_binding[0].get("HostPort", 0))
            except (ValueError, TypeError):
                pass
        cdp_binding = ports.get("9222/tcp")
        if cdp_binding and len(cdp_binding) > 0:
            try:
                cdp_port = int(cdp_binding[0].get("HostPort", 0))
            except (ValueError, TypeError):
                pass
        return {"vnc_port": vnc_port, "cdp_port": cdp_port}

    def container_telemetry(self, profile_name: str) -> dict:
        c = self.get_container(profile_name)
        if not c:
            return {"status": "not_found", "cpu_percent": 0.0, "ram_mb": 0.0}
        if c.status != "running":
            return {"status": c.status, "cpu_percent": 0.0, "ram_mb": 0.0}

        try:
            stats = c.stats(stream=False)
            memory_stats = stats.get("memory_stats", {})
            ram_bytes = memory_stats.get("usage", 0)
            ram_mb = round(ram_bytes / (1024 * 1024), 1)

            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})
            cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
            online_cpus = cpu_stats.get("online_cpus", 1) or 1

            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = round((cpu_delta / system_delta) * online_cpus * 100.0, 1)

            return {
                "status": "running",
                "cpu_percent": cpu_percent,
                "ram_mb": ram_mb,
            }
        except Exception:
            return {"status": c.status, "cpu_percent": 0.0, "ram_mb": 0.0}

    def all_container_telemetry(self) -> dict:
        """Batch fetch status and ports for all containers."""
        prefix = CONTAINER_PREFIX
        prefix_len = len(prefix)
        result = {}
        try:
            containers = self.client.containers.list(all=True)
            for c in containers:
                cname = (getattr(c, "name", "") or "").lstrip("/")
                if cname.startswith(prefix):
                    prof_name = cname[prefix_len:]
                    ports = c.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
                    vnc_port = None
                    cdp_port = None
                    vb = ports.get("6080/tcp")
                    if vb:
                        vnc_port = int(vb[0].get("HostPort", 0))
                    cb = ports.get("9222/tcp")
                    if cb:
                        cdp_port = int(cb[0].get("HostPort", 0))
                    result[prof_name] = {
                        "status": c.status,
                        "vnc_port": vnc_port,
                        "cdp_port": cdp_port,
                    }
        except Exception:
            pass
        return result

    def start_profile(
        self,
        profile_name: str,
        profile_dir: str,
        proxy_val: str = "",
        start_url: str = "",
        host_mount: str = "",
    ) -> dict:
        profile_name = validate_profile_name(profile_name)
        cname = self.container_name(profile_name)
        c = self.get_container(profile_name)

        if c:
            if c.status == "running":
                ports = self.get_profile_ports(profile_name)
                return {
                    "status": "already_running",
                    "vnc_port": ports["vnc_port"],
                    "cdp_port": ports["cdp_port"],
                }
            # Remove stopped container to recreate with clean allocated ports
            c.remove(force=True)

        vnc_port, cdp_port = self.find_free_ports()
        hostname = self._profile_hostname(profile_name)

        downloads_dir = os.path.join(profile_dir, "Downloads")
        os.makedirs(profile_dir, exist_ok=True)
        os.makedirs(downloads_dir, exist_ok=True)

        # Clear stale locks and enforce full read/write permissions for container UID 1001
        clean_stale_locks(profile_dir)
        fix_profile_permissions(profile_dir)

        empty_mask = DATA_DIR / ".empty"
        if empty_mask.is_dir():
            shutil.rmtree(empty_mask, ignore_errors=True)
        if not empty_mask.exists():
            empty_mask.touch()
            try:
                os.chmod(empty_mask, 0o664)
            except Exception:
                pass

        volumes = {
            profile_dir: {"bind": "/home/chrome/.config/chromium", "mode": "rw"},
            downloads_dir: {"bind": "/home/chrome/Downloads", "mode": "rw"},
        }
        if empty_mask.is_file():
            volumes[str(empty_mask)] = {"bind": "/.dockerenv", "mode": "ro"}
        if host_mount and os.path.isdir(host_mount):
            volumes[host_mount] = {"bind": "/home/chrome/host", "mode": "ro"}

        env = {
            "CHROME_PROFILE": profile_name,
            "CHROME_START_URL": start_url or "https://www.google.com",
        }

        command = [f"--class=chrome-{profile_name}"]
        extra_hosts = None

        raw_proxy = resolve_proxy_url(proxy_val)
        if raw_proxy:
            parsed = parse_proxy(raw_proxy)
            if parsed and parsed["user"]:
                # Authenticated proxy handled by in-container proxy-wrapper.py
                env["CHROME_PROXY_SCHEME"] = parsed["scheme"]
                env["CHROME_PROXY_USER"] = parsed["user"]
                env["CHROME_PROXY_PASS"] = parsed["pass"]
                env["CHROME_PROXY_HOST"] = parsed["host"].replace(
                    "127.0.0.1", "host.docker.internal"
                ).replace("localhost", "host.docker.internal")
                env["CHROME_PROXY_PORT"] = str(parsed["port"])
                command += ["--proxy-server=socks5://127.0.0.1:1081"]
            else:
                proxy_clean = raw_proxy.replace("127.0.0.1", "host.docker.internal").replace(
                    "localhost", "host.docker.internal"
                )
                command += [f"--proxy-server={proxy_clean}"]
            extra_hosts = {"host.docker.internal": "host-gateway"}

        run_kwargs = dict(
            image=DOCKER_IMAGE,
            name=cname,
            hostname=hostname,
            shm_size="1g",
            ulimits=[Ulimit(name="nofile", soft=65536, hard=65536)],
            detach=True,
            init=True,
            volumes=volumes,
            environment=env,
            ports={
                "6080/tcp": ("127.0.0.1", vnc_port),
                "9222/tcp": ("127.0.0.1", cdp_port),
            },
            command=command,
        )
        if extra_hosts:
            run_kwargs["extra_hosts"] = extra_hosts

        container = self.client.containers.run(**run_kwargs)
        return {
            "status": "started",
            "container_id": container.id[:12],
            "vnc_port": vnc_port,
            "cdp_port": cdp_port,
        }

    def stop_profile(self, profile_name: str, profile_dir: str = "") -> dict:
        c = self.get_container(profile_name)
        if not c:
            if profile_dir:
                clean_stale_locks(profile_dir)
                fix_profile_permissions(profile_dir)
            return {"status": "not_found"}
        try:
            # Allow Chromium up to 10 seconds to gracefully commit SQLite WAL journals & sessions
            c.stop(timeout=10)
            c.remove(force=True)
            if profile_dir:
                clean_stale_locks(profile_dir)
                fix_profile_permissions(profile_dir)
            return {"status": "stopped"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def remove_profile_container(self, profile_name: str) -> dict:
        c = self.get_container(profile_name)
        if not c:
            return {"status": "not_found"}
        try:
            c.remove(force=True)
            return {"status": "removed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
