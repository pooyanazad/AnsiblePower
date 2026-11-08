"""Separate queue consumer. Start under Supervisor or your service manager."""
import argparse
import fcntl
import os
import signal
import subprocess
import threading
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from contextlib import ExitStack

import inventory
import jobs
import utils


class RunBlocked(Exception):
    """Preflight failed before a process could be started."""


def run_command(command, descriptors, timeout):
    """Kill the whole process group on timeout, including SSH children."""
    environment = dict(os.environ, ANSIBLE_INVENTORY_ENABLED="host_list,yaml,ini",
                       ANSIBLE_INVENTORY_UNPARSED_FAILED="true",
                       ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED="true")
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          pass_fds=descriptors, start_new_session=True, env=environment) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
            return ("succeeded" if process.returncode == 0 else "failed"), output.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
            return "timed_out", output.decode("utf-8", errors="replace") + f"\nPlaybook timed out after {timeout:g} seconds. The process group was killed."


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
        return run_command(command, descriptors, timeout)


def run_one(database, binary, timeout=300):
    job = jobs.claim(database)
    if not job:
        return False
    try:
        state, output = execute(job, binary, timeout)
    except RunBlocked as exc:
        state, output = "blocked", str(exc)
    except Exception:
        # A process may already have started; never claim it is safe to retry.
        utils.logger.exception("Run %s has an uncertain outcome", job["id"])
        state, output = "uncertain", "Runner could not confirm the result. Check the affected hosts before acknowledging this run."
    jobs.finish(database, job["id"], state, output.strip() or "No output produced.")
    return True


def serve(database, binary, concurrency=1, timeout=300):
    os.makedirs(os.path.dirname(os.path.abspath(database)), exist_ok=True)
    with open(database + ".worker.lock", "a") as lock:
        # One supervisor owns recovery and the global concurrency limit.
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another worker already owns this queue") from exc
        jobs.recover(database)
        stopping = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stopping.set())

        def consume():
            while not stopping.is_set():
                if not run_one(database, binary, timeout):
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
