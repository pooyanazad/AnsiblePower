"""Linux process-group supervision with durable identity for restart cleanup."""
import os
import signal
import time
from pathlib import Path


def proc_stat(pid):
    try:
        # comm may contain spaces and parentheses; fields after it start at #3.
        fields = Path(f"/proc/{pid}/stat").read_text(errors="replace").rsplit(")", 1)[1].split()
        return {"state": fields[0], "group": int(fields[2]), "session": int(fields[3]),
                "start": int(fields[19])}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def identity(pid):
    info = proc_stat(pid)
    if info is None:
        raise ProcessLookupError(pid)
    return {"pid": pid, "start": info["start"],
            "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def group_alive(owner):
    """Reject stale PIDs after reboot/reuse, including when the leader has exited."""
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != owner["boot"]:
        return False
    leader = proc_stat(owner["pid"])
    if leader and leader["start"] != owner["start"]:
        return False
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            info = proc_stat(path.name)
            if (info and info["state"] != "Z" and info["group"] == owner["pid"]
                    and info["session"] == owner["pid"] and info["start"] >= owner["start"]):
                return True
    return False


def send_group(owner, signum):
    if group_alive(owner):
        try:
            os.killpg(owner["pid"], signum)
        except ProcessLookupError:
            pass  # The last member exited between inspection and signal.


def terminate(owner, grace=2):
    """Bounded TERM → KILL, even if only a descendant remains."""
    send_group(owner, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while group_alive(owner) and time.monotonic() < deadline:
        time.sleep(0.05)
    send_group(owner, signal.SIGKILL)
    deadline = time.monotonic() + 2
    while group_alive(owner) and time.monotonic() < deadline:
        time.sleep(0.05)
    if group_alive(owner):
        raise RuntimeError("Could not confirm that the local process group stopped")
