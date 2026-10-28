"""Regressions for internal-file overwrites and inventory path escapes."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import ansiblePower
import inventory
import utils


def configure(paths, target):
    utils.save_config({"playbooks_dir": paths["playbooks_dir"], "hosts_file": str(target)})


def assert_blocked_at_use(client, target):
    before = Path(target).read_bytes()
    with patch("ansiblePower.subprocess.check_output") as execute:
        assert client.get("/settings/get_hosts").status_code == 400
        assert client.post("/settings/save_hosts", data={"content": "OVERWRITTEN"}).status_code == 400
        assert client.post("/run_playbook", data={"playbook": "sample.yml"}).status_code == 400
    execute.assert_not_called()
    assert Path(target).read_bytes() == before


@pytest.mark.parametrize("kind", ["config", "history.db", "history.json", "auth", ".env", "outside.ini"])
def test_internal_files_cannot_be_selected_or_used_from_configuration(flask_client, patched_paths, kind):
    if kind == "config":
        target = Path(patched_paths["config_file"])
    elif kind == "auth":
        target = Path(ansiblePower.app.config["AUTH_DATABASE"])
    else:
        target = Path(patched_paths["base"]) / kind
        target.write_bytes(b"private application data\n")
    original_config = Path(patched_paths["config_file"]).read_bytes()
    original_target = target.read_bytes()
    response = flask_client.post("/settings/update_hosts_file", data={"hosts_file": str(target)})
    assert response.status_code == 400
    assert target.read_bytes() == original_target
    assert Path(patched_paths["config_file"]).read_bytes() == original_config
    configure(patched_paths, target)  # Bypass the settings endpoint, as old configs can.
    assert_blocked_at_use(flask_client, target)


@pytest.mark.parametrize("name", ["config.json", "history.json", "history.db", "auth.db", ".env", "secret.sqlite3"])
def test_reserved_files_are_rejected_even_inside_inventory_directory(flask_client, patched_paths, name):
    target = Path(inventory.INVENTORY_DIR) / name
    target.write_bytes(b"keep this unchanged")
    configure(patched_paths, target)
    assert_blocked_at_use(flask_client, target)


@pytest.mark.parametrize("escape", ["file", "directory", "root", "hardlink"])
def test_link_escapes_leave_internal_files_untouched(flask_client, patched_paths, escape):
    root = Path(inventory.INVENTORY_DIR)
    private_dir = Path(patched_paths["base"]) / "private"
    private_dir.mkdir()
    target = private_dir / "secret.ini"
    target.write_bytes(b"secret must survive")
    if escape == "file":
        selected = root / "escape.ini"
        selected.symlink_to(target)
    elif escape == "directory":
        (root / "escape").symlink_to(private_dir, target_is_directory=True)
        selected = root / "escape" / "secret.ini"
    elif escape == "root":
        (root / "hosts").unlink()
        root.rmdir()
        root.symlink_to(private_dir, target_is_directory=True)
        selected = root / "secret.ini"
    else:
        selected = root / "escape.ini"
        os.link(target, selected)
    original_config = Path(patched_paths["config_file"]).read_bytes()
    assert flask_client.post("/settings/update_hosts_file", data={"hosts_file": str(selected)}).status_code == 400
    assert Path(patched_paths["config_file"]).read_bytes() == original_config
    configure(patched_paths, selected)
    assert_blocked_at_use(flask_client, target)


def test_file_replaced_after_selection_is_revalidated(flask_client, patched_paths):
    selected = Path(utils.HOSTS_FILE)
    assert flask_client.post("/settings/update_hosts_file", data={"hosts_file": str(selected)}).status_code == 200
    private = Path(patched_paths["base"]) / "secret"
    private.write_bytes(b"private")
    selected.unlink()
    selected.symlink_to(private)
    assert_blocked_at_use(flask_client, private)


def test_symlink_swap_during_write_does_not_truncate_target(flask_client, patched_paths):
    selected = Path(utils.HOSTS_FILE)
    configure(patched_paths, selected)
    private = Path(patched_paths["base"]) / "secret"
    private.write_bytes(b"private")
    real_open = os.open

    def swap_on_open(path, flags, *args, **kwargs):
        if path == selected.name and flags & os.O_WRONLY:
            selected.unlink()
            selected.symlink_to(private)
        return real_open(path, flags, *args, **kwargs)

    with patch("inventory.os.open", side_effect=swap_on_open):
        response = flask_client.post("/settings/save_hosts", data={"content": "OVERWRITE"})
    assert response.status_code == 400
    assert private.read_bytes() == b"private"


@pytest.mark.parametrize("bad_value", [None, 42, [], {}, "", "data/../config.json", "\x00"])
def test_malformed_persisted_paths_fail_closed(flask_client, patched_paths, bad_value):
    configure(patched_paths, bad_value)
    # Write the actual JSON type rather than configure()'s string conversion.
    config = utils.load_config()
    config["hosts_file"] = bad_value
    utils.save_config(config)
    with patch("ansiblePower.subprocess.check_output") as execute:
        for method, route, data in [("GET", "/settings/get_hosts", {}),
                                    ("POST", "/settings/save_hosts", {"content": "x"}),
                                    ("POST", "/run_playbook", {"playbook": "sample.yml"})]:
            assert flask_client.open(route, method=method, data=data).status_code == 400
    execute.assert_not_called()


def test_missing_inventory_does_not_fall_back_to_local_execution(flask_client, patched_paths):
    configure(patched_paths, Path(inventory.INVENTORY_DIR) / "missing.ini")
    with patch("ansiblePower.subprocess.check_output") as execute:
        assert flask_client.post("/run_playbook", data={"playbook": "sample.yml"}).status_code == 404
    execute.assert_not_called()


def test_select_edit_read_and_run_a_valid_inventory(flask_client, patched_paths):
    selected = Path(inventory.INVENTORY_DIR) / "production.yaml"
    selected.write_text("all:\n  hosts:\n    localhost:\n", encoding="utf-8")
    (selected.parent / "group_vars").mkdir()
    assert flask_client.post("/settings/update_hosts_file", data={"hosts_file": str(selected)}).status_code == 200
    assert utils.load_config()["hosts_file"] == str(selected.resolve())
    content = "all:\n  hosts:\n    example.test:\n"
    assert flask_client.post("/settings/save_hosts", data={"content": content}).status_code == 200
    assert flask_client.get("/settings/get_hosts").json["content"] == content
    private = Path(patched_paths["base"]) / "secret"
    private.write_bytes(b"untouched")

    def execute(cmd, **kwargs):
        snapshot = cmd[cmd.index("-i") + 1]
        assert snapshot != str(selected) and snapshot.endswith(".yaml")
        assert len(kwargs["pass_fds"]) == 1
        assert Path(snapshot).read_text() == content
        assert (Path(snapshot).parent / "group_vars").is_dir()
        selected.unlink()
        selected.symlink_to(private)
        assert Path(snapshot).read_text() == content
        return b"ok: safe inventory snapshot"

    with patch("ansiblePower.subprocess.check_output", side_effect=execute) as run:
        assert flask_client.post("/run_playbook", data={"playbook": "sample.yml"}).status_code == 200
    run.assert_called_once()
    assert private.read_bytes() == b"untouched"
    assert not list(Path(inventory.INVENTORY_DIR).glob(".ansiblepower-run-*"))


@pytest.fixture()
def migration(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    root = data / "inventories"
    legacy = data / "hosts"
    hosts = root / "hosts"
    config = data / "config.json"
    config.write_text("{}")
    monkeypatch.setattr(inventory, "INVENTORY_DIR", str(root))
    monkeypatch.setattr(utils, "HOSTS_FILE", str(hosts))
    monkeypatch.setattr(utils, "LEGACY_HOSTS_FILE", str(legacy))
    monkeypatch.setattr(utils, "CONFIG_FILE", str(config))
    return legacy, hosts, config


def test_legacy_inventory_migrates_byte_for_byte_and_keeps_backup(migration):
    legacy, hosts, config = migration
    content = b"[production]\r\nserver.example.test\r\n"
    legacy.write_bytes(content)
    utils.init_inventory()
    assert legacy.read_bytes() == hosts.read_bytes() == content
    assert json.loads(config.read_text())["hosts_file"] == str(hosts)
    hosts.write_text("edited inventory")
    utils.init_inventory()  # Restart must never overwrite the edited inventory.
    assert hosts.read_text() == "edited inventory"
    assert legacy.read_bytes() == content


def test_fresh_install_creates_inventory_only_in_dedicated_directory(migration):
    legacy, hosts, config = migration
    utils.init_inventory()
    assert hosts.is_file() and not legacy.exists()
    assert utils.get_hosts_file() == str(hosts)


def test_migration_conflict_leaves_both_files_and_configuration_untouched(migration):
    legacy, hosts, config = migration
    hosts.parent.mkdir()
    legacy.write_bytes(b"legacy inventory")
    hosts.write_bytes(b"existing inventory")
    with pytest.raises(ValueError, match="conflict"):
        utils.init_inventory()
    assert legacy.read_bytes() == b"legacy inventory"
    assert hosts.read_bytes() == b"existing inventory"
    assert config.read_text() == "{}"


@pytest.mark.parametrize("link_location", ["source", "destination", "directory"])
def test_migration_rejects_symlinks_without_touching_targets(migration, link_location):
    legacy, hosts, config = migration
    private = config.parent / "secret"
    private.write_bytes(b"private")
    if link_location == "source":
        legacy.symlink_to(private)
    elif link_location == "destination":
        hosts.parent.mkdir()
        hosts.symlink_to(private)
    else:
        other = config.parent / "other"
        other.mkdir()
        hosts.parent.symlink_to(other, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        utils.init_inventory()
    assert private.read_bytes() == b"private"
    assert config.read_text() == "{}"


def test_migration_does_not_copy_arbitrary_configured_files(migration):
    legacy, hosts, config = migration
    config.write_text(json.dumps({"hosts_file": str(config)}))
    original = config.read_bytes()
    with pytest.raises(ValueError):
        utils.init_inventory()
    assert config.read_bytes() == original
    assert not hosts.exists() and not legacy.exists()


def test_failed_migration_config_save_preserves_original_and_can_retry(migration):
    legacy, hosts, config = migration
    legacy.write_bytes(b"[prod]\nproduction.example.test\n")
    with patch("utils.os.replace", side_effect=OSError("disk failure")):
        with pytest.raises(OSError):
            utils.init_inventory()
    assert config.read_bytes() == b"{}"
    assert legacy.read_bytes() == hosts.read_bytes()
    utils.init_inventory()
    assert json.loads(config.read_text())["hosts_file"] == str(hosts)


def test_real_ansible_parses_yaml_snapshot_and_adjacent_vars(tmp_path):
    executable = Path(ansiblePower.ANSIBLE_PLAYBOOK).with_name("ansible-inventory")
    binary = str(executable) if executable.is_file() else shutil.which("ansible-inventory")
    if not binary:
        pytest.skip("Ansible is not installed; snapshot behavior is also covered with subprocess tests")
    selected = Path(inventory.INVENTORY_DIR) / "production.yaml"
    selected.write_text("all:\n  hosts:\n    snapshot.example.test: {}\n")
    variables = selected.parent / "group_vars"
    variables.mkdir()
    (variables / "all.yml").write_text("inventory_marker: safe\n")
    ansible_config = tmp_path / "ansible.cfg"
    ansible_config.write_text("[defaults]\n")
    environment = dict(os.environ, ANSIBLE_HOME=str(tmp_path / "ansible"),
                       ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible-tmp"),
                       ANSIBLE_CONFIG=str(ansible_config), ANSIBLE_INVENTORY_ENABLED="yaml,ini",
                       ANSIBLE_INVENTORY_UNPARSED_FAILED="true")
    with inventory.for_run(str(selected)) as (snapshot, descriptor):
        output = subprocess.check_output([binary, "-i", snapshot, "--list"],
                                         pass_fds=(descriptor,), env=environment, timeout=30)
    data = json.loads(output)
    assert data["_meta"]["hostvars"]["snapshot.example.test"]["inventory_marker"] == "safe"
