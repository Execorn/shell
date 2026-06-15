import os
import sys
import json
import shutil
import pathlib
import subprocess
import pytest
from PIL import Image

def run_apply_theme(wallpaper_path, mock_bin_dir, tmp_home_dir, force_fallback=False):
    script_path = "/home/execorn/ricing/shell/scripts/apply-theme.py"
    env = os.environ.copy()
    env["HOME"] = str(tmp_home_dir)
    env["PATH"] = f"{mock_bin_dir}:{env.get('PATH', '')}"
    if force_fallback:
        env["FORCE_COLOR_FALLBACK"] = "1"
    
    res = subprocess.run(
        ["python3", script_path, "--wallpaper", str(wallpaper_path)],
        env=env,
        capture_output=True,
        text=True
    )
    return res

def create_dummy_image(path, color=(255, 0, 0)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (100, 100), color=color)
    img.save(path)

@pytest.fixture
def test_dirs(tmp_path):
    mock_bin_dir = tmp_path / "bin"
    mock_bin_dir.mkdir(exist_ok=True)
    
    tmp_home_dir = tmp_path / "home"
    tmp_home_dir.mkdir(exist_ok=True)
    
    wallpaper_path = tmp_path / "wallpaper.png"
    create_dummy_image(wallpaper_path, color=(255, 0, 0)) # Red image
    
    return mock_bin_dir, tmp_home_dir, wallpaper_path

def test_apply_theme_matugen_flow(test_dirs):
    mock_bin_dir, tmp_home_dir, wallpaper_path = test_dirs
    
    # Write mock matugen binary
    matugen_script = f"""#!/usr/bin/env python3
import os
import json
import sys
home = os.environ["HOME"]
with open(os.path.join(home, "matugen_calls.log"), "a") as f:
    f.write(" ".join(sys.argv) + "\\n")
scheme = {{
    "name": "dynamic",
    "flavour": "custom",
    "mode": "dark",
    "colours": {{
        "primary": "ff0000",
        "onSurfaceVariant": "00ff00",
        "background": "111111",
        "onBackground": "eeeeee",
        "term0": "111111",
        "term1": "222222"
    }}
}}
scheme_dir = os.path.join(home, ".local/state/caelestia")
os.makedirs(scheme_dir, exist_ok=True)
with open(os.path.join(scheme_dir, "scheme.json"), "w") as f:
    json.dump(scheme, f)
"""
    matugen_path = mock_bin_dir / "matugen"
    matugen_path.write_text(matugen_script)
    matugen_path.chmod(0o755)

    # Write mock hyprctl and killall
    (mock_bin_dir / "hyprctl").write_text(f"""#!/usr/bin/env python3
import os, sys
with open(os.path.join(os.environ["HOME"], "hyprctl_calls.log"), "a") as f:
    f.write(" ".join(sys.argv) + "\\n")
""")
    (mock_bin_dir / "hyprctl").chmod(0o755)

    (mock_bin_dir / "killall").write_text(f"""#!/usr/bin/env python3
import os, sys
with open(os.path.join(os.environ["HOME"], "killall_calls.log"), "a") as f:
    f.write(" ".join(sys.argv) + "\\n")
""")
    (mock_bin_dir / "killall").chmod(0o755)

    # Pre-create a dummy alacritty.toml to test appending import
    alacritty_dir = tmp_home_dir / ".config/alacritty"
    alacritty_dir.mkdir(parents=True, exist_ok=True)
    alacritty_conf = alacritty_dir / "alacritty.toml"
    alacritty_conf.write_text("[window]\nopacity = 0.8\n")

    res = run_apply_theme(wallpaper_path, mock_bin_dir, tmp_home_dir)
    assert res.returncode == 0, f"Script failed with output: {res.stdout}\n{res.stderr}"

    # Verify matugen was run
    matugen_calls = (tmp_home_dir / "matugen_calls.log").read_text()
    assert "matugen image" in matugen_calls

    # Verify hyprctl was called to apply colors
    hyprctl_calls = (tmp_home_dir / "hyprctl_calls.log").read_text()
    assert "keyword general:col.active_border rgba(ff0000e6)" in hyprctl_calls
    assert "keyword general:col.inactive_border rgba(00ff0011)" in hyprctl_calls

    # Verify killall was called for kitty
    killall_calls = (tmp_home_dir / "killall_calls.log").read_text()
    assert "-USR1 kitty" in killall_calls

    # Verify Kitty config output
    kitty_conf = tmp_home_dir / ".cache/wal/colors-kitty.conf"
    assert kitty_conf.exists()
    kitty_content = kitty_conf.read_text()
    assert "cursor #ff0000" in kitty_content
    assert "background #111111" in kitty_content

    # Verify Alacritty config output
    alacritty_colors = tmp_home_dir / ".cache/caelestia/colors-alacritty.toml"
    assert alacritty_colors.exists()
    alacritty_content = alacritty_colors.read_text()
    assert 'background = "#111111"' in alacritty_content
    assert 'black = "#111111"' in alacritty_content

    # Verify alacritty.toml import statement prepended
    main_alacritty = alacritty_conf.read_text()
    assert main_alacritty.startswith('import = ["~/.cache/caelestia/colors-alacritty.toml"]')

def test_apply_theme_caelestia_flow(test_dirs):
    mock_bin_dir, tmp_home_dir, wallpaper_path = test_dirs
    
    # Write mock caelestia binary
    caelestia_script = f"""#!/usr/bin/env python3
import os
import json
import sys
home = os.environ["HOME"]
with open(os.path.join(home, "caelestia_calls.log"), "a") as f:
    f.write(" ".join(sys.argv) + "\\n")
scheme = {{
    "name": "dynamic",
    "flavour": "custom",
    "mode": "dark",
    "colours": {{
        "primary": "ff0000",
        "onSurfaceVariant": "00ff00",
        "background": "111111",
        "onBackground": "eeeeee"
    }}
}}
scheme_dir = os.path.join(home, ".local/state/caelestia")
os.makedirs(scheme_dir, exist_ok=True)
with open(os.path.join(scheme_dir, "scheme.json"), "w") as f:
    json.dump(scheme, f)
"""
    caelestia_path = mock_bin_dir / "caelestia"
    caelestia_path.write_text(caelestia_script)
    caelestia_path.chmod(0o755)

    res = run_apply_theme(wallpaper_path, mock_bin_dir, tmp_home_dir)
    assert res.returncode == 0, f"Script failed with output: {res.stdout}\n{res.stderr}"

    # Verify caelestia was run
    caelestia_calls = (tmp_home_dir / "caelestia_calls.log").read_text()
    assert "caelestia wallpaper -f" in caelestia_calls

def test_apply_theme_fallback_flow(test_dirs):
    mock_bin_dir, tmp_home_dir, wallpaper_path = test_dirs
    
    # Ensure no matugen or caelestia in mock PATH
    # Run script - will trigger Pillow clustering fallback
    res = run_apply_theme(wallpaper_path, mock_bin_dir, tmp_home_dir, force_fallback=True)
    assert res.returncode == 0, f"Script failed with output: {res.stdout}\n{res.stderr}"

    # Verify scheme.json was generated by Pillow fallback
    scheme_file = tmp_home_dir / ".local/state/caelestia/scheme.json"
    assert scheme_file.exists()
    
    with open(scheme_file, "r") as f:
        scheme = json.load(f)
        
    assert scheme["name"] == "dynamic"
    assert "primary" in scheme["colours"]
    assert "onSurfaceVariant" in scheme["colours"]
    
    # Since we passed a solid Red image (255, 0, 0), let's check the primary color.
    # Hue of red is 0. Lightness in dark mode primary is 0.8. Saturation is 1.0.
    # HLS (0, 0.8, 1.0) -> RGB (1.0, 0.6, 0.6) -> "ff9999".
    assert scheme["colours"]["primary"] == "ff9999"

    # Verify current.conf contains variables
    conf_file = tmp_home_dir / ".config/hypr/scheme/current.conf"
    assert conf_file.exists()
    conf_content = conf_file.read_text()
    assert "$primary = ff9999" in conf_content

    # Verify active wallpaper path was recorded
    wall_path_txt = tmp_home_dir / ".local/state/caelestia/wallpaper/path.txt"
    assert wall_path_txt.exists()
    assert wall_path_txt.read_text() == str(wallpaper_path.resolve())
