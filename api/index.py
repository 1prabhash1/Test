import os
import platform
import socket
import shutil
import time
import psutil


def bytes_to_gb(value):
    return round(value / (1024 ** 3), 2)


def cpu_model():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass

    return platform.processor() or "Unknown"


def handler(request):
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage("/")

    data = {
        "hostname": socket.gethostname(),

        "os": platform.system(),
        "os_version": platform.version(),
        "kernel": platform.release(),
        "architecture": platform.machine(),

        "cpu_model": cpu_model(),
        "cpu_cores": psutil.cpu_count(logical=False) or 0,
        "cpu_threads": psutil.cpu_count(logical=True) or 0,
        "cpu_usage": psutil.cpu_percent(interval=0.1),

        "ram_total": bytes_to_gb(memory.total),
        "ram_used": bytes_to_gb(memory.used),
        "ram_free": bytes_to_gb(memory.available),
        "ram_usage": memory.percent,

        "disk_total": bytes_to_gb(disk.total),
        "disk_used": bytes_to_gb(disk.used),
        "disk_free": bytes_to_gb(disk.free),
        "disk_usage": round(
            disk.used / disk.total * 100, 1
        ),

        "python": platform.python_version(),

        "server_time": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store"
        },
        "body": data
    }
