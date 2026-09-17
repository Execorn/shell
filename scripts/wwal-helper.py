#!/usr/bin/env python3
"""
wwal-helper.py: Helper script connecting Quickshell/Caelestia wallpaper panel with wwal.
Handles scroll preview transitions (random effect), permanent wallpaper application,
and daemon management.
"""

import sys
import os
import json
import random
import shutil
import subprocess
import datetime

LOG_FILE = "/tmp/wwal-helper.log"

ALL_EFFECTS = [
    "fade", "wipe", "grow", "outer", "wave", "noise",
    "crosszoom", "slide", "glitch", "burn", "ripple",
    "pixelate", "doom", "swirl", "cube", "luma",
    "light_leak", "page_curl"
]

def log_msg(msg):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(LOG_FILE, "a") as f:
            f.write(f"[{now}] {msg}\n")
    except Exception:
        pass

def load_config():
    home = os.path.expanduser("~")
    wwal_json = os.path.join(home, ".config/caelestia/wwal.json")
    cfg = {}
    if os.path.exists(wwal_json):
        try:
            with open(wwal_json, "r") as f:
                cfg = json.load(f)
        except Exception as e:
            log_msg(f"Failed to read wwal.json: {e}")
    return cfg

def is_daemon_running():
    try:
        res = subprocess.run(["pgrep", "-x", "wwald"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

def ensure_daemon():
    if not shutil.which("wwal") or not shutil.which("wwald"):
        log_msg("wwal or wwald binary not found in PATH")
        return False
    if is_daemon_running():
        return True

    log_msg("wwald not running, spawning background instance...")
    subprocess.Popen(["wwald"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(20):
        import time
        time.sleep(0.05)
        if is_daemon_running():
            log_msg("wwald daemon successfully spawned")
            return True
    return False

def apply_image(path, effect, duration, fps=60, scaling="fill", pos="center"):
    if not os.path.exists(path):
        log_msg(f"apply_image failed: path does not exist: {path}")
        return False
    if not ensure_daemon():
        log_msg("apply_image failed: daemon could not be verified")
        return False

    cmd = [
        "wwal", "img", path,
        "--transition-type", str(effect),
        "--transition-duration", str(duration),
        "--transition-fps", str(fps),
        "--scaling-mode", str(scaling),
        "--transition-pos", str(pos)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2.0)
        log_msg(f"cmd={' '.join(cmd)} -> exit={res.returncode} stdout={res.stdout.strip()} stderr={res.stderr.strip()}")
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        log_msg(f"cmd={' '.join(cmd)} TIMED OUT after 2.0s")
        return False
    except Exception as e:
        log_msg(f"cmd={' '.join(cmd)} error: {e}")
        return False

def handle_scroll(path):
    cfg = load_config()
    scroll_effect = cfg.get("scrollEffect", "random")
    duration = cfg.get("scrollDuration", 0.5)
    fps = cfg.get("fps", 60)
    scaling = cfg.get("scalingMode", "fill")
    pos = cfg.get("pos", "center")

    if scroll_effect == "random":
        available_effects = cfg.get("effects", ALL_EFFECTS)
        if not available_effects:
            available_effects = ALL_EFFECTS
        chosen = random.choice(available_effects)
    else:
        chosen = scroll_effect

    log_msg(f"handle_scroll: path={path}, effect={chosen}, duration={duration}")
    apply_image(path, chosen, duration, fps, scaling, pos)

def handle_set(path, explicit_effect=None):
    cfg = load_config()
    if explicit_effect:
        set_effect = explicit_effect
    else:
        set_effect = cfg.get("setEffect", "fade")
    duration = cfg.get("setDuration", 1.0)
    fps = cfg.get("fps", 60)
    scaling = cfg.get("scalingMode", "fill")
    pos = cfg.get("pos", "center")

    if set_effect == "random":
        available_effects = cfg.get("effects", ALL_EFFECTS)
        if not available_effects:
            available_effects = ALL_EFFECTS
        chosen = random.choice(available_effects)
    else:
        chosen = set_effect

    log_msg(f"handle_set: path={path}, effect={chosen}, duration={duration}")
    apply_image(path, chosen, duration, fps, scaling, pos)

def handle_restore(explicit_path=None):
    if explicit_path and os.path.exists(explicit_path):
        path = explicit_path
    else:
        home = os.path.expanduser("~")
        path_file = os.path.join(home, ".local/state/caelestia/wallpaper/path.txt")
        path = None
        if os.path.exists(path_file):
            try:
                with open(path_file, "r") as f:
                    path = f.read().strip()
            except Exception as e:
                log_msg(f"Error reading path.txt: {e}")

    if path and os.path.exists(path):
        cfg = load_config()
        duration = cfg.get("scrollDuration", 0.5)
        fps = cfg.get("fps", 60)
        scaling = cfg.get("scalingMode", "fill")
        log_msg(f"handle_restore: path={path}")
        apply_image(path, "fade", duration, fps, scaling, "center")
    else:
        log_msg(f"handle_restore: no valid path found (explicit={explicit_path})")

def save_config(cfg):
    home = os.path.expanduser("~")
    wwal_json = os.path.join(home, ".config/caelestia/wwal.json")
    try:
        os.makedirs(os.path.dirname(wwal_json), exist_ok=True)
        with open(wwal_json, "w") as f:
            json.dump(cfg, f, indent=4)
        log_msg("Saved config successfully")
        return True
    except Exception as e:
        log_msg(f"Failed to save config: {e}")
        return False

def toggle_random_boot():
    cfg = load_config()
    current = cfg.get("randomOnBoot", False)
    new_val = not current
    cfg["randomOnBoot"] = new_val
    save_config(cfg)
    log_msg(f"toggle_random_boot: {current} -> {new_val}")
    print(f"randomOnBoot: {new_val}")
    return new_val

def toggle_slideshow():
    cfg = load_config()
    slideshow_cfg = cfg.get("slideshow")
    if isinstance(slideshow_cfg, dict):
        current = slideshow_cfg.get("enabled", False)
        slideshow_cfg["enabled"] = not current
        new_val = not current
    else:
        current = bool(slideshow_cfg)
        new_val = not current
        cfg["slideshow"] = {
            "enabled": new_val,
            "interval": cfg.get("slideshowInterval", 300),
            "effect": cfg.get("slideshowEffect", "random")
        }
    save_config(cfg)
    log_msg(f"toggle_slideshow: {current} -> {new_val}")
    print(f"slideshow: {new_val}")
    return new_val

def parse_interval(val_str):
    try:
        val_str = str(val_str).strip().lower()
        if val_str.endswith("m"):
            return int(float(val_str[:-1]) * 60)
        elif val_str.endswith("s"):
            return int(float(val_str[:-1]))
        elif val_str.endswith("h"):
            return int(float(val_str[:-1]) * 3600)
        else:
            v = float(val_str)
            if v < 60:
                return int(v * 60)
            return int(v)
    except Exception:
        return 300

def set_slideshow_interval(interval_str):
    cfg = load_config()
    sec = parse_interval(interval_str)
    if isinstance(cfg.get("slideshow"), dict):
        cfg["slideshow"]["interval"] = sec
        cfg["slideshow"]["enabled"] = True
    else:
        cfg["slideshow"] = {
            "enabled": True,
            "interval": sec,
            "effect": "random"
        }
    save_config(cfg)
    log_msg(f"set_slideshow_interval: {interval_str} -> {sec}s (enabled=True)")
    print(f"slideshowInterval: {sec}")
    return sec

def get_all_wallpapers():
    home = os.path.expanduser("~")
    walls_dir = os.path.join(home, "Pictures/Wallpapers")
    valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    files = []
    if os.path.exists(walls_dir):
        for r, _, filenames in os.walk(walls_dir):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext in valid_exts:
                    files.append(os.path.join(r, fn))
    return files

def set_random(explicit_effect=None):
    files = get_all_wallpapers()
    if not files:
        log_msg("set_random: no wallpapers found")
        return False

    home = os.path.expanduser("~")
    path_file = os.path.join(home, ".local/state/caelestia/wallpaper/path.txt")
    current_wall = None
    if os.path.exists(path_file):
        try:
            with open(path_file, "r") as f:
                current_wall = f.read().strip()
        except Exception:
            pass

    available = [f for f in files if f != current_wall] if len(files) > 1 and current_wall else files
    chosen = random.choice(available)
    log_msg(f"set_random: chosen={chosen}")

    cfg = load_config()
    eff = explicit_effect or cfg.get("slideshow", {}).get("effect", "random")
    handle_set(chosen, eff)
    apply_theme = os.path.join(os.path.dirname(__file__), "apply-theme.py")
    if os.path.exists(apply_theme):
        subprocess.run([sys.executable, apply_theme, "--wallpaper", chosen, "--no-wwal"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: wwal-helper.py <scroll|set|restore|ensure|random|toggle-random-boot|toggle-slideshow|set-slideshow-interval> [ARGS...]")
        sys.exit(1)

    action = sys.argv[1]
    if action == "scroll" and len(sys.argv) >= 3:
        handle_scroll(sys.argv[2])
    elif action == "set" and len(sys.argv) >= 3:
        eff = sys.argv[3] if len(sys.argv) >= 4 else None
        handle_set(sys.argv[2], eff)
    elif action == "restore":
        explicit = sys.argv[2] if len(sys.argv) >= 3 else None
        handle_restore(explicit)
    elif action == "ensure":
        ensure_daemon()
    elif action == "random":
        eff = sys.argv[2] if len(sys.argv) >= 3 else None
        set_random(eff)
    elif action == "toggle-random-boot":
        toggle_random_boot()
    elif action == "toggle-slideshow":
        toggle_slideshow()
    elif action == "set-slideshow-interval" and len(sys.argv) >= 3:
        set_slideshow_interval(sys.argv[2])
    else:
        log_msg(f"Unknown command or insufficient args: {sys.argv}")
        sys.exit(1)

if __name__ == "__main__":
    main()

