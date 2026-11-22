import importlib.util
import json
import math
import pathlib
import sys
import pytest

EQ_CONTROL_PATH = pathlib.Path("/home/execorn/scripts/eq-control.py")


def load_eq_module(tmp_path, monkeypatch, pactl_state=None, eq_node_id=43, with_static_slots=True):
    spec = importlib.util.spec_from_file_location("eq_control_mod", str(EQ_CONTROL_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    state_dir = tmp_path / "eq_state"
    presets_dir = state_dir / "presets"
    fc_dir = state_dir / "filter-chain.conf.d"
    state_dir.mkdir(parents=True, exist_ok=True)
    presets_dir.mkdir(parents=True, exist_ok=True)
    fc_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(mod, "CONFIG_DIR", str(state_dir))
    monkeypatch.setattr(mod, "DEFAULT_PRESETS_DIR", str(presets_dir))
    monkeypatch.setattr(mod, "PRESETS_DIR", str(presets_dir))
    monkeypatch.setattr(mod, "FILTER_CHAIN_DIR", str(fc_dir))
    monkeypatch.setattr(mod, "CURRENT_EQ_FILE", str(state_dir / "current-eq.txt"))
    monkeypatch.setattr(mod, "ACTIVE_PRESET_FILE", str(state_dir / "active-preset"))
    monkeypatch.setattr(mod, "RICED_EQ_CONF", str(fc_dir / "riced-eq.conf"))
    monkeypatch.setattr(mod, "LOCK_FILE", str(tmp_path / "eq.lock"))
    monkeypatch.setattr(mod, "AUTOEQ_INDEX_CACHE", str(tmp_path / "autoeq-index.md"))

    fake_bin = tmp_path / "eq_bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    calls_log = tmp_path / "eq_cmds.log"
    state_file = tmp_path / "eq_pactl_state.json"
    state_file.write_text(json.dumps(pactl_state or {
        "default_sink": "riced_equalizer_sink",
        "sinks": [
            {"index": 10, "name": "riced_equalizer_sink", "description": "Riced Equalizer Sink"},
            {"index": 20, "name": "bluez_output.08_F0_B6_35_49_16.1", "description": "STAX SPIRIT S3"},
            {"index": 21, "name": "alsa_output.pci-0000_05_00.6.analog-stereo", "description": "Built-in Audio"},
        ],
        "sink-inputs": [
            {"index": 100, "sink": 20, "properties": {"node.name": "output.filter-chain-999-8", "media.name": "Riced Equalizer Sink"}},
            {"index": 101, "sink": 20, "properties": {"application.name": "Firefox", "node.name": "Firefox"}},
        ],
    }))

    # Stateful fake pactl supporting list/get-default-sink/set-default-sink/move-sink-input
    (fake_bin / "pactl").write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sf = pathlib.Path({str(state_file)!r})
log = pathlib.Path({str(calls_log)!r})
args = sys.argv[1:]
state = json.loads(sf.read_text())
json_mode = False
if "-f" in args:
    i = args.index("-f")
    if i + 1 < len(args) and args[i + 1] == "json":
        json_mode = True
    args = args[:i] + args[i + 2:]

cmd = args[0] if args else ""
if cmd == "get-default-sink":
    print(state.get("default_sink", ""))
elif cmd == "info":
    print(f"Default Sink: {{state.get('default_sink', '')}}")
elif cmd == "list" and len(args) >= 2 and json_mode:
    print(json.dumps(state.get(args[1], [])))
else:
    with log.open("a") as f:
        f.write("pactl " + " ".join(args) + "\\n")
    if cmd == "set-default-sink" and len(args) >= 2:
        state["default_sink"] = args[1]
        sf.write_text(json.dumps(state))
    elif cmd == "move-sink-input" and len(args) >= 3:
        sid = int(args[1])
        target_name = args[2]
        sink_map = {{s["name"]: s["index"] for s in state.get("sinks", [])}}
        for inp in state.get("sink-inputs", []):
            if inp.get("index") == sid and target_name in sink_map:
                inp["sink"] = sink_map[target_name]
        sf.write_text(json.dumps(state))
""")
    (fake_bin / "pactl").chmod(0o755)

    prop_info = [{"name": "preamp:Mult"}, {"name": "pk_24:Gain"}] if with_static_slots else [{"name": "eq_band_1:Gain"}]
    nodes_dump = []
    if eq_node_id is not None:
        nodes_dump.append({
            "id": eq_node_id,
            "info": {
                "props": {"node.name": "riced_equalizer_sink"},
                "params": {"PropInfo": prop_info},
            },
        })
    (fake_bin / "pw-dump").write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
with pathlib.Path({str(calls_log)!r}).open("a") as f:
    f.write("pw-dump " + " ".join(sys.argv[1:]) + "\\n")
print(json.dumps({json.dumps(nodes_dump)}))
""")
    (fake_bin / "pw-dump").chmod(0o755)

    (fake_bin / "pw-cli").write_text(f"""#!/usr/bin/env python3
import pathlib, sys
with pathlib.Path({str(calls_log)!r}).open("a") as f:
    f.write("pw-cli " + " ".join(sys.argv[1:]) + "\\n")
""")
    (fake_bin / "pw-cli").chmod(0o755)

    (fake_bin / "pw-metadata").write_text(f"""#!/usr/bin/env python3
import pathlib, sys
with pathlib.Path({str(calls_log)!r}).open("a") as f:
    f.write("pw-metadata " + " ".join(sys.argv[1:]) + "\\n")
""")
    (fake_bin / "pw-metadata").chmod(0o755)

    (fake_bin / "systemctl").write_text(f"""#!/usr/bin/env python3
import pathlib, sys
with pathlib.Path({str(calls_log)!r}).open("a") as f:
    f.write("systemctl " + " ".join(sys.argv[1:]) + "\\n")
""")
    (fake_bin / "systemctl").chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin}:{os_environ_path()}")
    return mod, presets_dir, state_dir, calls_log, state_file


def os_environ_path():
    import os
    return os.environ.get("PATH", "")


def test_validate_preset_id_rejects_traversal_and_bad_names(tmp_path, monkeypatch):
    mod, presets_dir, _, _, _ = load_eq_module(tmp_path, monkeypatch)
    for bad in ("", ".", "..", "../etc/passwd", "/tmp/evil", "foo/bar", "bad preset", "a$b"):
        with pytest.raises(ValueError):
            mod.validate_preset_id(bad)

    p = mod.validate_preset_id("stax-s3_v2")
    assert p == str(presets_dir / "stax-s3_v2.txt")


def test_biquad_math_and_headroom_preamp_safety(tmp_path, monkeypatch):
    mod, _, _, _, _ = load_eq_module(tmp_path, monkeypatch)
    # 10 dB peaking boost at 1 kHz without enough explicit preamp must auto-compensate headroom <= -10.1 dB
    raw = "Preamp: 0.0 dB\nFilter 1: ON PK Fc 1000 Hz Gain 10.0 dB Q 1.41\n"
    parsed = mod.parse_preset_text(raw, fallback_name="boost-test")
    assert len(parsed.bands) == 1
    assert parsed.max_cascade_db >= 9.9
    assert parsed.effective_preamp_db <= -(parsed.max_cascade_db + 0.1) + 1e-6

    # Evaluate single biquad magnitude at center freq = 1000 Hz (~ +10 dB) and far away ~ 0 dB
    band = mod.EqBand(True, "PK", 1000.0, 10.0, 1.41)
    coeffs = mod.compute_biquad_coeffs(band)
    def eval_db(freq):
        w = 2.0 * math.pi * freq / 48000.0
        z1 = complex(math.cos(-w), math.sin(-w))
        z2 = z1 * z1
        mag = abs((coeffs.b0 + coeffs.b1 * z1 + coeffs.b2 * z2) / (coeffs.a0 + coeffs.a1 * z1 + coeffs.a2 * z2))
        return 20.0 * math.log10(max(mag, 1e-12))

    assert abs(eval_db(1000.0) - 10.0) < 0.05
    assert abs(eval_db(20.0)) < 0.1
    assert abs(mod.evaluate_cascade_peak_db([band], 48000.0) - 10.0) < 0.05


def test_render_riced_eq_conf_and_props_payload_static_and_fallback(tmp_path, monkeypatch):
    import re
    mod, _, _, _, _ = load_eq_module(tmp_path, monkeypatch)
    raw = (
        "# Name: Custom Ref\n"
        "# Description: Test profile\n"
        "Preamp: -4.0 dB\n"
        "Filter 1: ON LSC Fc 105 Hz Gain 3.5 dB Q 0.70\n"
        "Filter 2: ON PK Fc 1500 Hz Gain -2.5 dB Q 1.80\n"
        "Filter 3: ON HSC Fc 8000 Hz Gain 2.0 dB Q 0.71\n"
        "Filter 4: OFF PK Fc 500 Hz Gain 9.0 dB Q 1.0\n"
    )
    parsed = mod.parse_preset_text(raw, fallback_name="custom")
    assert len(parsed.bands) == 3  # OFF filter excluded
    conf_text, static_fit = mod.render_riced_eq_conf(parsed)
    assert static_fit is True
    assert "node.passive" in conf_text and "true" in conf_text
    assert "audio.rate" in conf_text and "48000" in conf_text
    assert re.search(r"name\s*=\s*ls_1\b", conf_text)
    assert re.search(r"name\s*=\s*hs_4\b", conf_text)
    assert re.search(r"name\s*=\s*pk_24\b", conf_text)

    payload = mod.build_props_payload(parsed)
    params = payload["params"]
    kv = dict(zip(params[0::2], params[1::2]))
    assert math.isclose(kv["ls_1:Gain"], 3.5, rel_tol=1e-4)
    assert math.isclose(kv["ls_2:Gain"], 0.0, abs_tol=1e-9)
    assert math.isclose(kv["pk_1:Gain"], -2.5, rel_tol=1e-4)
    assert math.isclose(kv["hs_1:Gain"], 2.0, rel_tol=1e-4)
    assert math.isclose(kv["preamp:Mult"], 10.0 ** (parsed.effective_preamp_db / 20.0), rel_tol=1e-4)

    # >24 peaking filters triggers static_fit = False cleanly without crashing
    many_pk = "\n".join(f"Filter {i}: ON PK Fc {100 + i*20} Hz Gain 1.0 dB Q 1.0" for i in range(1, 27))
    parsed_many = mod.parse_preset_text(many_pk, fallback_name="many")
    conf_many, static_many = mod.render_riced_eq_conf(parsed_many)
    assert static_many is False
    assert "custom_band_26" in conf_many


def test_apply_zero_drop_and_preserves_bypassed_state(tmp_path, monkeypatch):
    mod, presets_dir, state_dir, calls_log, state_file = load_eq_module(tmp_path, monkeypatch)
    (presets_dir / "stax-s3.txt").write_text("Preamp: -3.5 dB\nFilter 1: ON PK Fc 200 Hz Gain 2.0 dB Q 1.2\n")

    # 1. With EQ enabled, cmd_apply uses live pw-cli Props and never restarts pipewire or filter-chain
    mod.cmd_apply("stax-s3")
    calls = calls_log.read_text().splitlines()
    assert any(c.startswith("pw-cli set-param 43 Props ") for c in calls)
    assert not any("systemctl" in c for c in calls)
    assert (state_dir / "active-preset").read_text().strip() == "stax-s3"

    # 2. When EQ is bypassed (default_sink != riced_equalizer_sink), cmd_apply stays bypassed
    calls_log.unlink()
    st = json.loads(state_file.read_text())
    st["default_sink"] = "bluez_output.08_F0_B6_35_49_16.1"
    state_file.write_text(json.dumps(st))

    mod.cmd_apply("stax-s3")
    calls2 = calls_log.read_text().splitlines()
    assert any(c.startswith("pw-cli set-param 43 Props ") for c in calls2)
    assert not any("set-default-sink riced_equalizer_sink" in c for c in calls2)


def test_apply_oversized_preset_reloads_isolated_filter_chain_only(tmp_path, monkeypatch):
    mod, presets_dir, _, calls_log, _ = load_eq_module(tmp_path, monkeypatch)
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    many_pk = "\n".join(f"Filter {i}: ON PK Fc {100 + i*20} Hz Gain 0.5 dB Q 1.0" for i in range(1, 27))
    (presets_dir / "huge.txt").write_text(many_pk + "\n")

    mod.cmd_apply("huge")
    calls = calls_log.read_text().splitlines()
    assert any("systemctl --user restart filter-chain.service" in c for c in calls)
    assert not any("pipewire.service" in c for c in calls)
    # Firefox moved back onto riced_equalizer_sink while output.filter-chain stays on BT sink
    assert any("pactl move-sink-input 101 riced_equalizer_sink" in c for c in calls)
    assert not any("pactl move-sink-input 100 riced_equalizer_sink" in c for c in calls)


def test_cmd_off_and_on_roundtrip_routing(tmp_path, monkeypatch):
    mod, _, _, calls_log, state_file = load_eq_module(tmp_path, monkeypatch)
    # Put Firefox on EQ sink first
    st = json.loads(state_file.read_text())
    st["sink-inputs"][1]["sink"] = 10
    state_file.write_text(json.dumps(st))

    mod.cmd_off()
    assert json.loads(state_file.read_text())["default_sink"] == "bluez_output.08_F0_B6_35_49_16.1"
    calls = calls_log.read_text().splitlines()
    assert any("move-sink-input 101 bluez_output.08_F0_B6_35_49_16.1" in c for c in calls)
    assert not any("move-sink-input 100 bluez_output" in c for c in calls)

    calls_log.unlink()
    mod.cmd_on()
    assert json.loads(state_file.read_text())["default_sink"] == "riced_equalizer_sink"
    calls_on = calls_log.read_text().splitlines()
    assert any("set-sink-volume riced_equalizer_sink 100%" in c for c in calls_on)
    assert any("set-sink-mute riced_equalizer_sink 0" in c for c in calls_on)
    assert any("move-sink-input 101 riced_equalizer_sink" in c for c in calls_on)


def test_autoeq_candidate_ranking_and_offline_download(tmp_path, monkeypatch):
    mod, presets_dir, _, _, _ = load_eq_module(tmp_path, monkeypatch)
    index_md = (
        "- [Edifier Stax Spirit S3](./crinacle/over-ear/Edifier%20Stax%20Spirit%20S3)\n"
        "- [Edifier Stax Spirit S3](./oratory1990/over-ear/Edifier%20Stax%20Spirit%20S3)\n"
        "- [Sony WH-1000XM5](./rtings/over-ear/Sony%20WH-1000XM5)\n"
    )
    sample_eq = "Preamp: -4.2 dB\nFilter 1: ON PK Fc 200 Hz Gain 3.0 dB Q 1.0\n"

    def fake_fetch(url, timeout=10.0):
        if "INDEX.md" in url:
            return index_md
        if "oratory1990" in url and "Edifier%20Stax%20Spirit%20S3%20ParametricEQ.txt" in url:
            return sample_eq
        raise RuntimeError(f"unexpected URL {url}")

    monkeypatch.setattr(mod, "_fetch_text", fake_fetch)
    mod.cmd_download("Edifier Stax Spirit S3")

    out_file = presets_dir / "edifier-stax-spirit-s3.txt"
    assert out_file.exists()
    content = out_file.read_text()
    assert "# Name: Edifier Stax Spirit S3" in content
    assert "oratory1990" in content
    assert "Filter 1: ON PK" in content
