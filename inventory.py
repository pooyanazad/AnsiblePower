"""Confine inventory I/O to regular files in the dedicated inventory directory."""
import os
import secrets
import shutil
import stat
from contextlib import contextmanager

from ansible.errors import AnsibleError
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import inventory_loader


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVENTORY_DIR = os.path.join(BASE_DIR, "data", "inventories")
_INTERNAL_NAMES = {"config.json", "history.json", "history.db", "auth.db"}


def validate_path(path, must_exist=True):
    """Validate configuration values as strictly as paths submitted through the UI."""
    if not isinstance(path, str) or not path.strip() or "\x00" in path or ".." in path.split(os.sep):
        raise ValueError("Invalid inventory path")
    candidate = os.path.abspath(os.path.join(BASE_DIR, path))
    root = os.path.abspath(INVENTORY_DIR)
    if os.path.realpath(root) != root or os.path.realpath(candidate) != candidate:
        raise ValueError("Inventory paths must not contain symlinks")
    if os.path.commonpath([candidate, root]) != root or candidate == root:
        raise ValueError("Inventories must be inside the dedicated inventory directory")
    relative = os.path.relpath(candidate, root)
    if any(part.startswith(".") for part in relative.split(os.sep)):
        raise ValueError("Hidden inventory paths are not allowed")
    if os.path.basename(candidate) in _INTERNAL_NAMES or candidate.endswith((".db", ".sqlite", ".sqlite3", ".db-journal", ".db-wal", ".db-shm")):
        raise ValueError("Application data cannot be used as an inventory")
    try:
        check_regular_file(os.stat(candidate, follow_symlinks=False))
    except FileNotFoundError:
        if must_exist:
            raise
    return candidate


def check_regular_file(metadata):
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError("Inventory must be a regular file without hard links")


@contextmanager
def directory_fd(path):
    """Walk with O_NOFOLLOW so a replaced parent cannot redirect file operations."""
    descriptor = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in os.path.abspath(path).split(os.sep):
            if not component:
                continue
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def open_file(path, writable=False):
    path = validate_path(path)
    with directory_fd(os.path.dirname(path)) as parent:
        flags = (os.O_WRONLY if writable else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(os.path.basename(path), flags, dir_fd=parent)
        try:
            metadata = os.fstat(descriptor)
            check_regular_file(metadata)
            if not writable and not metadata.st_mode & 0o444:
                raise PermissionError("Inventory has no read permission")
            stream = os.fdopen(descriptor, "w" if writable else "r", encoding="utf-8")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            # Opening in write mode above does not truncate the existing descriptor.
            if writable:
                os.ftruncate(stream.fileno(), 0)
            yield stream


class InvalidInventory(ValueError):
    """An inventory that must be repaired before a playbook can start."""


def inspect_snapshot(path):
    """Parse a pinned static inventory using Ansible's own INI/YAML plugins.

    Do not load script or dynamic inventory plugins in a web request. Keeping
    preflight to static files also prevents a provider failure from producing
    an empty inventory and falling back to Ansible's implicit localhost.
    """
    loader = DataLoader()
    data = InventoryData()
    plugin = "yaml" if path.endswith((".yaml", ".yml", ".json")) else "ini"
    try:
        inventory_loader.get(plugin).parse(data, loader, path, cache=False)
        data.reconcile_inventory()
    except (AnsibleError, OSError, UnicodeError) as exc:
        raise InvalidInventory("Inventory could not be parsed. Repair the INI or YAML file in Settings.") from exc
    finally:
        loader.cleanup_all_tmp_files()
    hosts = sorted(data.hosts)
    if not hosts:
        raise InvalidInventory("Inventory contains no hosts. Add hosts in Settings or explicitly select Local execution.")
    return hosts


@contextmanager
def for_run(path):
    """Give Ansible a private snapshot, preserving the extension and adjacent vars.

    A pinned parent descriptor keeps both the snapshot and group_vars inside the
    validated directory even if a directory is replaced while Ansible starts.
    """
    path = validate_path(path)
    with open_file(path) as source, directory_fd(os.path.dirname(path)) as parent:
        name = ".ansiblepower-run-" + secrets.token_hex(16) + os.path.splitext(path)[1]
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                shutil.copyfileobj(source, target)
            yield f"/proc/self/fd/{parent}/{name}", parent
        finally:
            os.unlink(name, dir_fd=parent)
