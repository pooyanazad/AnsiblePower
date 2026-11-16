"""Separate queue consumer. Start under Supervisor or your service manager."""
import argparse
import fcntl
import os
import signal
import subprocess
import threading
import sys
import tempfile
import time
import json
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from contextlib import ExitStack

import process_control
import inventory
import jobs
import utils


class RunLaunchError(Exception):
    """The executable could not be started."""


class RunBlocked(Exception):
    """Preflight failed before a process could be started."""


# The wrapper waits for registration before exec. If the worker dies first,
# stdin closes and no playbook starts. The error pipe closes on successful exec.
LAUNCH_GATE = """
import os, sys
error_fd = int(sys.argv[1])
os.set_inheritable(error_fd, False)
if os.read(0, 1) != b'1':
    sys.exit(125)
os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
try:
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
except OSError as exc:
    os.write(error_fd, str(exc).encode())
    sys.exit(127)
"""


def run_command(command, descriptors, timeout, *, logfile=None, on_start=None,
                stop_reason=None, grace=2):
    """Keep partial output on disk and supervise the entire local process group."""
    environment = dict(os.environ, ANSIBLE_INVENTORY_ENABLED="host_list,yaml,ini",
                       ANSIBLE_INVENTORY_UNPARSED_FAILED="true",
                       ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED="true")
    with ExitStack() as stack:
        if logfile:
            fd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            output_file = stack.enter_context(os.fdopen(fd, "wb"))
            reader = stack.enter_context(open(logfile, "rb"))
        else:
            output_file = stack.enter_context(tempfile.TemporaryFile())
            reader = output_file
        # A separate error pipe distinguishes exec failure from an Ansible exit.
        error_read, error_write = os.pipe()
        stack.callback(os.close, error_read)
        os.set_blocking(error_read, False)
        gated_command = [sys.executable, "-c", LAUNCH_GATE, str(error_write), *command]
        try:
            process = subprocess.Popen(gated_command, stdin=subprocess.PIPE, stdout=output_file,
                                       stderr=subprocess.STDOUT, pass_fds=(*descriptors, error_write),
                                       start_new_session=True, env=environment)
        except OSError as exc:
            raise RunLaunchError(f"Could not launch playbook: {exc}") from exc
        finally:
            os.close(error_write)
        owner = None
        reason = None
        try:
            owner = process_control.identity(process.pid)
            if on_start:
                on_start(owner)
            reason = stop_reason() if stop_reason else None
            if not reason:
                process.stdin.write(b"1")
                process.stdin.flush()
            process.stdin.close()
            deadline = time.monotonic() + timeout
            while process.poll() is None and not reason:
                reason = stop_reason() if stop_reason else None
                if reason:
                    break
                if time.monotonic() >= deadline:
                    reason = "timed_out"
                    break
                time.sleep(0.1)
        finally:
            process.stdin.close()
            if owner:
                process_control.terminate(owner, grace)
            else:
                # No command was released through the gate.
                process.kill()
            process.wait(timeout=max(grace, 1) + 2)
        reader.seek(0)
        output = reader.read().decode("utf-8", errors="replace")
        error = os.read(error_read, 65536).decode("utf-8", errors="replace")
        if error:
            raise RunLaunchError(f"Could not launch playbook: {error}")
        if reason:
            messages = {"timed_out": f"Playbook timed out after {timeout:g} seconds.",
                        "canceled": "Run canceled by an administrator.",
                        "interrupted": "Run interrupted because the runner stopped."}
            output += "\n" + messages[reason] + " Local process group stopped; remote work may still be running."
            return reason, output, process.returncode
        return ("succeeded" if process.returncode == 0 else "failed"), output, process.returncode


def execute(job, binary, timeout):
    spec = job["spec"]
    path = spec["playbook_path"]
    with ExitStack() as stack:
        try:
            # Queued jobs never silently switch to a different input.
            if os.path.realpath(path) != path:
                raise ValueError("Playbook path changed. Review it and submit a new run.")
            with open(path, "rb") as source:
                if jobs.digest(source.read()) != spec["playbook_digest"]:
                    raise ValueError("Playbook changed while queued. Review it and submit a new run.")
            command = [binary, path]
            descriptors = ()
            if spec["execution_mode"] == "local":
                command += ["-i", "localhost,", "--connection=local", "--limit", "localhost"]
            else:
                snapshot, descriptor = stack.enter_context(inventory.for_run(spec["inventory_path"]))
                hosts = inventory.inspect_snapshot(snapshot)
                with open(snapshot, "rb") as source:
                    if jobs.digest(source.read()) != spec["inventory_digest"]:
                        raise ValueError("Inventory changed while queued. Review it in Settings and submit a new run.")
                command += ["-i", snapshot, "--limit", ",".join(hosts)]
                descriptors = (descriptor,)
        except (ValueError, OSError) as exc:
            raise RunBlocked(f"Run blocked: {exc}. Repair the configuration in Settings and submit again.") from exc
        database = job.get("database")
        if database:
            return run_command(command, descriptors, timeout,
                               logfile=jobs.log_path(database, job["id"]),
                               on_start=lambda owner: jobs.register_process(database, job["id"], owner),
                               stop_reason=job.get("stop_reason"))
        return run_command(command, descriptors, timeout)


def run_one(database, binary, timeout=300, stopping=None):
    job = jobs.claim(database)
    if not job:
        return False
    def stop_reason():
        if jobs.cancellation_requested(database, job["id"]):
            return "canceled"
        if stopping is not None and stopping.is_set():
            return "interrupted"
        return None

    job["database"] = database
    job["stop_reason"] = stop_reason
    exit_code = None
    try:
        reason = stop_reason()
        if reason:
            state, output = reason, "Run stopped before a local process was started."
        else:
            state, output, exit_code = execute(job, binary, timeout)
    except RunLaunchError as exc:
        state, output = "launch_error", str(exc)
    except RunBlocked as exc:
        state, output = "blocked", str(exc)
    except Exception:
        # A process may already have started; never claim it is safe to retry.
        utils.logger.exception("Run %s has an uncertain outcome", job["id"])
        state, output = "uncertain", jobs.read_log(database, job["id"]) + "\nRunner could not confirm the result. Check the affected hosts before acknowledging this run."
    jobs.finish(database, job["id"], state, output.strip() or "No output produced.", exit_code)
    return True


def serve(database, binary, concurrency=1, timeout=300):
    os.makedirs(os.path.dirname(os.path.abspath(database)), exist_ok=True)
    with open(database + ".worker.lock", "a") as lock:
        # One supervisor owns recovery and the global concurrency limit.
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another worker already owns this queue") from exc
        stopping = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stopping.set())
        jobs.recover(database)

        def consume():
            while not stopping.is_set():
                if not run_one(database, binary, timeout, stopping):
                    stopping.wait(0.5)

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(consume) for _ in range(concurrency)]
            try:
                wait(futures, return_when=FIRST_EXCEPTION)
                stopping.set()
                for future in futures:
                    future.result()
            finally:
                stopping.set()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=utils.get_history_db_file())
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("ANSIBLEPOWER_RUN_CONCURRENCY", "1")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("ANSIBLEPOWER_RUN_TIMEOUT", "300")))
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 8 or args.timeout <= 0:
        parser.error("concurrency must be 1–8 and timeout must be positive")
    serve(args.database, utils.find_ansible_playbook(), args.concurrency, args.timeout)


if __name__ == "__main__":
    main()
