import json
import os
import pathlib
import re
import shutil
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_volume_control_sh_routes_through_eq_sink_clamps_and_serializes(tmp_path):
    shell_cfg_path = pathlib.Path("/home/execorn/.config/caelestia/shell.json")
    cfg = json.loads(shell_cfg_path.read_text()) if shell_cfg_path.exists() else {}
    max_vol = float(cfg.get("services", {}).get("maxVolume", 1.0))

    rt_dir = tmp_path / "run"
    rt_dir.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    state_file = tmp_path / "vol_state.json"
    state_file.write_text(json.dumps({"40": {"vol": round(max_vol - 0.04, 2), "muted": False}}))
    ipc_log = tmp_path / "ipc.log"

    (fake_bin / "pactl").write_text("""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args == ["get-default-sink"]:
    print("riced_equalizer_sink")
elif args == ["-f", "json", "list", "sinks"]:
    print(json.dumps([
        {"index": 10, "name": "riced_equalizer_sink"},
        {"index": 40, "name": "bluez_output.08_F0_B6_35_49_16.1"},
    ]))
elif args == ["-f", "json", "list", "sink-inputs"]:
    print(json.dumps([
        {"index": 99, "sink": 40, "properties": {"node.name": "output.filter-chain-1-8", "media.name": "Riced Equalizer Sink"}}
    ]))
""")
    (fake_bin / "pactl").chmod(0o755)

    (fake_bin / "pw-dump").write_text("""#!/usr/bin/env python3
import json
print(json.dumps([
    {"id": 10, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "riced_equalizer_sink"}}},
    {"id": 40, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "bluez_output.08_F0_B6_35_49_16.1"}}},
]))
""")
    (fake_bin / "pw-dump").chmod(0o755)

    (fake_bin / "wpctl").write_text(f"""#!/usr/bin/env python3
import fcntl, json, pathlib, sys
sf = pathlib.Path({str(state_file)!r})
lockf = pathlib.Path({str(tmp_path / 'wpctl.lck')!r})
args = sys.argv[1:]
with lockf.open("a+") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    st = json.loads(sf.read_text())
    cmd = args[0]
    limit = None
    pos = []
    i = 1
    while i < len(args):
        if args[i] == "-l" and i + 1 < len(args):
            limit = float(args[i + 1])
            i += 2
        else:
            pos.append(args[i])
            i += 1
    tid = pos[0] if pos else "40"
    entry = st.setdefault(tid, {{"vol": 0.5, "muted": False}})
    if cmd == "get-volume":
        m = " [MUTED]" if entry["muted"] else ""
        print(f"Volume: {{entry['vol']:.2f}}{{m}}")
    elif cmd == "set-volume":
        val = pos[1]
        if val.endswith("%+"):
            entry["vol"] += float(val[:-2]) / 100.0
        elif val.endswith("%-"):
            entry["vol"] -= float(val[:-2]) / 100.0
        else:
            entry["vol"] = float(val)
        if limit is not None:
            entry["vol"] = min(limit, entry["vol"])
        entry["vol"] = max(0.0, round(entry["vol"], 2))
        sf.write_text(json.dumps(st))
    elif cmd == "set-mute":
        if pos[1] == "toggle":
            entry["muted"] = not entry["muted"]
        else:
            entry["muted"] = pos[1] == "1"
        sf.write_text(json.dumps(st))
""")
    (fake_bin / "wpctl").chmod(0o755)

    (fake_bin / "quickshell").write_text(f"""#!/usr/bin/env python3
import pathlib, sys
with pathlib.Path({str(ipc_log)!r}).open("a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
""")
    (fake_bin / "quickshell").chmod(0o755)

    env = dict(os.environ, XDG_RUNTIME_DIR=str(rt_dir), PATH=f"{fake_bin}:{os.environ['PATH']}")

    # Step up from max_vol - 0.04 with explicit +10% -> clamped cleanly to max_vol via wpctl -l
    subprocess.run(["/home/execorn/scripts/volume_control.sh", "up", "10"], env=env, check=True)
    assert abs(json.loads(state_file.read_text())["40"]["vol"] - max_vol) < 1e-6

    # Concurrent decrements serialized via flock (4x -10% -> max_vol - 0.40, zero lost updates)
    procs = [subprocess.Popen(["/home/execorn/scripts/volume_control.sh", "down", "10"], env=env) for _ in range(4)]
    for p in procs:
        assert p.wait(timeout=5) == 0
    expected_after_down = round(max_vol - 0.40, 2)
    assert abs(json.loads(state_file.read_text())["40"]["vol"] - expected_after_down) < 1e-6

    # Toggle mute reports mutStr=true to IPC; showOsd is only used when VOL query returns empty
    subprocess.run(["/home/execorn/scripts/volume_control.sh", "mute"], env=env, check=True)
    assert json.loads(state_file.read_text())["40"]["muted"] is True
    log_lines = ipc_log.read_text().splitlines()
    assert any(f"ipc call audio updateVolume {max_vol:.2f} false" in l for l in log_lines)
    assert any(f"ipc call audio updateVolume {expected_after_down:.2f} true" in l for l in log_lines)


def test_guitar_rig_sh_discovers_minifuse_dynamically_and_restores_mic_on_exit(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls_log = tmp_path / "guitar_calls.log"
    qpw_pid_file = tmp_path / "qpw.pid"

    nodes_dump = [
        {"id": 101, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "alsa_input.usb-ARTURIA_MiniFuse_2-00.HiFi__Mic1__source"}}},
        {"id": 202, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "alsa_output.usb-ARTURIA_MiniFuse_2-00.HiFi__Line1__sink"}}},
        {"id": 303, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "gx_head_fx"}}},
        {"id": 404, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "alsa_output.pci-0000_05_00.6.analog-stereo"}}},
        {"id": 501, "type": "PipeWire:Interface:Port", "info": {"props": {"node.id": 303, "port.name": "out_0"}}},
        {"id": 502, "type": "PipeWire:Interface:Port", "info": {"props": {"node.id": 404, "port.name": "playback_FL"}}},
        {"id": 503, "type": "PipeWire:Interface:Port", "info": {"props": {"node.id": 202, "port.name": "playback_FL"}}},
        {"id": 601, "type": "PipeWire:Interface:Link", "info": {"output-port-id": 501, "input-port-id": 502}},
        {"id": 602, "type": "PipeWire:Interface:Link", "info": {"output-port-id": 501, "input-port-id": 503}},
    ]
    (fake_bin / "pw-dump").write_text(f"""#!/usr/bin/env python3
import json
print(json.dumps({json.dumps(nodes_dump)}))
""")
    (fake_bin / "pw-dump").chmod(0o755)

    (fake_bin / "wpctl").write_text(f"""#!/usr/bin/env python3
import pathlib, sys
with pathlib.Path({str(calls_log)!r}).open("a") as f:
    f.write("wpctl " + " ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] == "get-volume" and sys.argv[2] == "101":
    print("Volume: 0.72 [MUTED]")
""")
    (fake_bin / "wpctl").chmod(0o755)

    (fake_bin / "pw-link").write_text(f"""#!/usr/bin/env python3
import pathlib, sys
with pathlib.Path({str(calls_log)!r}).open("a") as f:
    f.write("pw-link " + " ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["-i"]:
    print("gx_head_amp:in_0")
elif sys.argv[1:] == ["-o"]:
    print("gx_head_fx:out_0")
    print("gx_head_fx:out_1")
""")
    (fake_bin / "pw-link").chmod(0o755)

    (fake_bin / "guitarix").write_text("""#!/bin/sh
sleep 0.5
exit 0
""")
    (fake_bin / "guitarix").chmod(0o755)

    (fake_bin / "qpwgraph").write_text(f"""#!/bin/sh
echo $$ > {str(qpw_pid_file)!r}
sleep 30
""")
    (fake_bin / "qpwgraph").chmod(0o755)

    env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}")
    subprocess.run(["/home/execorn/scripts/guitar-rig.sh"], env=env, check=True, timeout=5)

    calls = calls_log.read_text().splitlines()
    assert "wpctl set-mute 101 0" in calls
    assert "wpctl set-volume 101 1.0" in calls
    # Trap cleanup restores original volume (0.72) and original mute state (1)
    assert "wpctl set-volume 101 0.72" in calls
    assert "wpctl set-mute 101 1" in calls
    # Unwanted non-Line1 gx_head_fx link was dropped while Line1 link kept
    assert "pw-link -d gx_head_fx:out_0 alsa_output.pci-0000_05_00.6.analog-stereo:playback_FL" in calls
    assert not any("pw-link -d gx_head_fx:out_0 alsa_output.usb-ARTURIA_MiniFuse_2" in c for c in calls)
    # Verify spawned qpwgraph was terminated by cleanup trap
    if qpw_pid_file.exists():
        pid = int(qpw_pid_file.read_text().strip())
        assert not pathlib.Path(f"/proc/{pid}").exists()


def test_pipewire_wireplumber_and_hypr_config_invariants():
    # 1. PipeWire isolated filter-chain drop-in present; legacy monolithic drop-in absent
    riced_eq = pathlib.Path("/home/execorn/.config/pipewire/filter-chain.conf.d/riced-eq.conf")
    legacy_fc = pathlib.Path("/home/execorn/.config/pipewire/pipewire.conf.d/filter-chain.conf")
    assert riced_eq.exists()
    assert not legacy_fc.exists()
    fc_txt = riced_eq.read_text()
    assert "node.passive" in fc_txt and "true" in fc_txt
    assert "audio.rate" in fc_txt and "48000" in fc_txt
    assert "preamp" in fc_txt and "pk_24" in fc_txt
    assert re.search(r"channelmix\.upmix\s*=\s*true", fc_txt)

    # 2. WirePlumber Bluetooth policy includes local a2dp_source + hfp_ag, peer hw-volume profiles, and demotes bluez_input
    bt_conf = pathlib.Path("/home/execorn/.config/wireplumber/wireplumber.conf.d/50-bluetooth.conf")
    assert bt_conf.exists()
    bt_txt = bt_conf.read_text()
    assert "a2dp_source" in bt_txt
    assert "hfp_ag" in bt_txt
    hw_match = re.search(r"bluez5\.hw-volume\s*=\s*\[([^\]]+)\]", bt_txt)
    assert hw_match is not None, "bluez5.hw-volume must be explicitly configured"
    assert "a2dp_sink" in hw_match.group(1), "bluez5.hw-volume must include peer a2dp_sink profile"
    assert "hfp_hf" in hw_match.group(1), "bluez5.hw-volume must include peer hfp_hf profile"
    assert not re.search(r"^\s*bluez5\.dummy-avrcp-player\s*=\s*true\b", bt_txt, re.M)
    assert "priority.session = 500" in bt_txt
    if shutil.which("spa-json-dump"):
        res = subprocess.run(["spa-json-dump", str(bt_conf)], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr

    # 3. Hyprland keybinds & variables invariants
    kb_txt = pathlib.Path("/home/execorn/.config/hypr/hyprland/keybinds.lua").read_text()
    vars_txt = pathlib.Path("/home/execorn/.config/hypr/variables.lua").read_text()
    assert 'kbTodoWs' in vars_txt and 'SUPER + ALT + T' in vars_txt
    assert 'kbRecordSound' in vars_txt and 'SUPER + ALT + R' in vars_txt
    assert "locked_repeating" in kb_txt and "XF86MonBrightnessUp" in kb_txt
    assert "XF86AudioMicMute" in kb_txt and "toggleSourceMute" in kb_txt
    assert "pgrep -x quickshell.real" in kb_txt
    assert len(re.findall(r'vars\.kb(?:TodoWs|RecordSound)\b', kb_txt)) == 2
