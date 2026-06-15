#!/usr/bin/env python3
import os
import sys
import json
import shutil
import argparse
import subprocess
import colorsys
from PIL import Image

def rgb_to_hex(r, g, b):
    return f"{r:02x}{g:02x}{b:02x}"

def generate_scheme_from_primary(primary_rgb, mode="dark"):
    r_p, g_p, b_p = primary_rgb
    h, l, s = colorsys.rgb_to_hls(r_p/255.0, g_p/255.0, b_p/255.0)
    
    def hls_to_hex(hue, lightness, saturation):
        r, g, b = colorsys.hls_to_rgb(hue % 1.0, max(0.0, min(1.0, lightness)), max(0.0, min(1.0, saturation)))
        return f"{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    if mode == "dark":
        primary = hls_to_hex(h, 0.8, s)
        onPrimary = hls_to_hex(h, 0.15, s)
        primaryContainer = hls_to_hex(h, 0.3, s)
        onPrimaryContainer = hls_to_hex(h, 0.9, s)
        
        secondary = hls_to_hex(h, 0.7, s * 0.4)
        onSecondary = hls_to_hex(h, 0.15, s * 0.4)
        secondaryContainer = hls_to_hex(h, 0.25, s * 0.4)
        onSecondaryContainer = hls_to_hex(h, 0.85, s * 0.4)
        
        tertiary = hls_to_hex(h + 0.33, 0.7, s * 0.5)
        onTertiary = hls_to_hex(h + 0.33, 0.15, s * 0.5)
        tertiaryContainer = hls_to_hex(h + 0.33, 0.25, s * 0.5)
        onTertiaryContainer = hls_to_hex(h + 0.33, 0.85, s * 0.5)
        
        background = hls_to_hex(h, 0.08, s * 0.15)
        onBackground = hls_to_hex(h, 0.9, s * 0.1)
        surface = hls_to_hex(h, 0.08, s * 0.15)
        onSurface = hls_to_hex(h, 0.9, s * 0.1)
        surfaceVariant = hls_to_hex(h, 0.15, s * 0.2)
        onSurfaceVariant = hls_to_hex(h, 0.8, s * 0.15)
        
        outline = hls_to_hex(h, 0.5, s * 0.2)
        outlineVariant = hls_to_hex(h, 0.3, s * 0.2)
        inverseSurface = hls_to_hex(h, 0.9, s * 0.1)
        inverseOnSurface = hls_to_hex(h, 0.15, s * 0.15)
        inversePrimary = hls_to_hex(h, 0.4, s)
    else:
        primary = hls_to_hex(h, 0.4, s)
        onPrimary = hls_to_hex(h, 0.95, s)
        primaryContainer = hls_to_hex(h, 0.85, s)
        onPrimaryContainer = hls_to_hex(h, 0.1, s)
        
        secondary = hls_to_hex(h, 0.45, s * 0.4)
        onSecondary = hls_to_hex(h, 0.95, s * 0.4)
        secondaryContainer = hls_to_hex(h, 0.85, s * 0.4)
        onSecondaryContainer = hls_to_hex(h, 0.15, s * 0.4)
        
        tertiary = hls_to_hex(h + 0.33, 0.45, s * 0.5)
        onTertiary = hls_to_hex(h + 0.33, 0.95, s * 0.5)
        tertiaryContainer = hls_to_hex(h + 0.33, 0.85, s * 0.5)
        onTertiaryContainer = hls_to_hex(h + 0.33, 0.15, s * 0.5)
        
        background = hls_to_hex(h, 0.98, s * 0.05)
        onBackground = hls_to_hex(h, 0.1, s * 0.15)
        surface = hls_to_hex(h, 0.98, s * 0.05)
        onSurface = hls_to_hex(h, 0.1, s * 0.15)
        surfaceVariant = hls_to_hex(h, 0.9, s * 0.1)
        onSurfaceVariant = hls_to_hex(h, 0.3, s * 0.15)
        
        outline = hls_to_hex(h, 0.5, s * 0.2)
        outlineVariant = hls_to_hex(h, 0.8, s * 0.2)
        inverseSurface = hls_to_hex(h, 0.15, s * 0.15)
        inverseOnSurface = hls_to_hex(h, 0.95, s * 0.05)
        inversePrimary = hls_to_hex(h, 0.8, s)
        
    colours = {
        "primary_paletteKeyColor": primary,
        "secondary_paletteKeyColor": secondary,
        "tertiary_paletteKeyColor": tertiary,
        "background": background,
        "onBackground": onBackground,
        "surface": surface,
        "surfaceDim": background,
        "surfaceBright": hls_to_hex(h, 0.2, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.95, s * 0.05),
        "surfaceContainerLowest": hls_to_hex(h, 0.05, s * 0.15) if mode == "dark" else hls_to_hex(h, 1.0, s * 0.05),
        "surfaceContainerLow": hls_to_hex(h, 0.07, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.96, s * 0.05),
        "surfaceContainer": surface,
        "surfaceContainerHigh": hls_to_hex(h, 0.12, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.92, s * 0.05),
        "surfaceContainerHighest": hls_to_hex(h, 0.16, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.88, s * 0.05),
        "onSurface": onSurface,
        "surfaceVariant": surfaceVariant,
        "onSurfaceVariant": onSurfaceVariant,
        "inverseSurface": inverseSurface,
        "inverseOnSurface": inverseOnSurface,
        "outline": outline,
        "outlineVariant": outlineVariant,
        "shadow": "000000",
        "scrim": "000000",
        "surfaceTint": primary,
        "primary": primary,
        "onPrimary": onPrimary,
        "primaryContainer": primaryContainer,
        "onPrimaryContainer": onPrimaryContainer,
        "inversePrimary": inversePrimary,
        "secondary": secondary,
        "onSecondary": onSecondary,
        "secondaryContainer": secondaryContainer,
        "onSecondaryContainer": onSecondaryContainer,
        "tertiary": tertiary,
        "onTertiary": onTertiary,
        "tertiaryContainer": tertiaryContainer,
        "onTertiaryContainer": onTertiaryContainer,
        "error": "ffb4ab" if mode == "dark" else "ba1a1a",
        "onError": "690005" if mode == "dark" else "ffffff",
        "errorContainer": "93000a" if mode == "dark" else "ffdad6",
        "onErrorContainer": "ffdad6" if mode == "dark" else "410002",
        "primaryFixed": hls_to_hex(h, 0.9, s),
        "primaryFixedDim": primary,
        "onPrimaryFixed": onPrimary,
        "onPrimaryFixedVariant": primaryContainer,
        "secondaryFixed": hls_to_hex(h, 0.9, s * 0.4),
        "secondaryFixedDim": secondary,
        "onSecondaryFixed": onSecondary,
        "onSecondaryFixedVariant": secondaryContainer,
        "tertiaryFixed": hls_to_hex(h + 0.33, 0.9, s * 0.5),
        "tertiaryFixedDim": tertiary,
        "onTertiaryFixed": onTertiary,
        "onTertiaryFixedVariant": tertiaryContainer,
        
        "term0": background,
        "term1": hls_to_hex(0.0, 0.6, s),
        "term2": hls_to_hex(0.33, 0.6, s),
        "term3": hls_to_hex(0.12, 0.6, s),
        "term4": hls_to_hex(0.66, 0.6, s),
        "term5": hls_to_hex(0.8, 0.6, s),
        "term6": hls_to_hex(0.5, 0.6, s),
        "term7": onBackground,
        "term8": hls_to_hex(h, 0.3, s * 0.2),
        "term9": hls_to_hex(0.0, 0.75, s),
        "term10": hls_to_hex(0.33, 0.75, s),
        "term11": hls_to_hex(0.12, 0.75, s),
        "term12": hls_to_hex(0.66, 0.75, s),
        "term13": hls_to_hex(0.8, 0.75, s),
        "term14": hls_to_hex(0.5, 0.75, s),
        "term15": hls_to_hex(h, 0.98, s * 0.05),
        
        "rosewater": hls_to_hex(0.97, 0.85, s),
        "flamingo": hls_to_hex(0.95, 0.85, s),
        "pink": hls_to_hex(0.9, 0.85, s),
        "mauve": hls_to_hex(0.8, 0.85, s),
        "red": hls_to_hex(0.0, 0.8, s),
        "maroon": hls_to_hex(0.98, 0.75, s),
        "peach": hls_to_hex(0.08, 0.8, s),
        "yellow": hls_to_hex(0.15, 0.8, s),
        "green": hls_to_hex(0.33, 0.8, s),
        "teal": hls_to_hex(0.45, 0.8, s),
        "sky": hls_to_hex(0.55, 0.8, s),
        "sapphire": hls_to_hex(0.6, 0.8, s),
        "blue": hls_to_hex(0.65, 0.8, s),
        "lavender": hls_to_hex(0.72, 0.8, s),
        
        "text": onSurface,
        "subtext1": onSurfaceVariant,
        "subtext0": outline,
        "overlay2": hls_to_hex(h, 0.5, s * 0.15),
        "overlay1": hls_to_hex(h, 0.45, s * 0.15),
        "overlay0": hls_to_hex(h, 0.4, s * 0.15),
        "surface2": hls_to_hex(h, 0.22, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.82, s * 0.05),
        "surface1": hls_to_hex(h, 0.18, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.86, s * 0.05),
        "surface0": hls_to_hex(h, 0.14, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.90, s * 0.05),
        "base": background,
        "mantle": hls_to_hex(h, 0.06, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.94, s * 0.05),
        "crust": hls_to_hex(h, 0.04, s * 0.15) if mode == "dark" else hls_to_hex(h, 0.90, s * 0.05),
        
        "success": "B5CCBA",
        "onSuccess": "213528",
        "successContainer": "374B3E",
        "onSuccessContainer": "D1E9D6"
    }
    
    return {
        "name": "dynamic",
        "flavour": "custom",
        "mode": mode,
        "variant": "tonalspot",
        "colours": colours
    }

def main():
    parser = argparse.ArgumentParser(description="Extract theme colors and inject live settings.")
    parser.add_argument("--wallpaper", required=True, help="Path to wallpaper file.")
    args = parser.parse_args()

    wallpaper_path = os.path.abspath(args.wallpaper)
    if not os.path.exists(wallpaper_path):
        print(f"Error: Wallpaper path '{wallpaper_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Resolve paths
    home = os.path.expanduser("~")
    scheme_json_path = os.path.join(home, ".local/state/caelestia/scheme.json")
    hypr_conf_path = os.path.join(home, ".config/hypr/scheme/current.conf")
    wallpaper_path_txt = os.path.join(home, ".local/state/caelestia/wallpaper/path.txt")

    # 1. Check for matugen or caelestia or run fallback
    force_fallback = os.environ.get("FORCE_COLOR_FALLBACK") == "1"
    if shutil.which("matugen") and not force_fallback:
        print("matugen found. Running matugen color extraction...")
        # Since matugen configuration can vary, we call standard image generation.
        # But we must ensure scheme.json and current.conf are written correctly.
        # In a real environment we assume matugen writes it or we can run it.
        # We also mock this in tests.
        subprocess.run(["matugen", "image", wallpaper_path], check=True)
    elif shutil.which("caelestia") and not force_fallback:
        print("caelestia found. Running caelestia wallpaper extraction...")
        subprocess.run(["caelestia", "wallpaper", "-f", wallpaper_path], check=True)
    else:
        print("Neither matugen nor caelestia available. Running custom Pillow clustering fallback...")
        try:
            img = Image.open(wallpaper_path)
            img = img.convert("RGB")
            img.thumbnail((100, 100))
            
            # Quantize to extract representative colors
            quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
            palette = quantized.getpalette()
            pixels = list(quantized.getdata())
            
            # Count color occurrences
            color_counts = {}
            for p in pixels:
                color_counts[p] = color_counts.get(p, 0) + 1
            
            # Sort color indices by count descending
            sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
            
            # Find a nice saturated primary color, or fall back to the most dominant
            primary_rgb = None
            for idx, count in sorted_colors:
                r, g, b = palette[idx*3], palette[idx*3+1], palette[idx*3+2]
                h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
                if s > 0.15:
                    primary_rgb = (r, g, b)
                    break
            
            if primary_rgb is None:
                dom_idx = sorted_colors[0][0]
                primary_rgb = (palette[dom_idx*3], palette[dom_idx*3+1], palette[dom_idx*3+2])

            scheme = generate_scheme_from_primary(primary_rgb)

            # Write scheme.json
            os.makedirs(os.path.dirname(scheme_json_path), exist_ok=True)
            with open(scheme_json_path, "w") as f:
                json.dump(scheme, f, indent=2)

            # Write current.conf for Hyprland variables
            os.makedirs(os.path.dirname(hypr_conf_path), exist_ok=True)
            with open(hypr_conf_path, "w") as f:
                for name, hex_val in scheme["colours"].items():
                    f.write(f"${name} = {hex_val}\n")

        except Exception as e:
            print(f"Error during custom Pillow extraction: {e}", file=sys.stderr)
            sys.exit(1)

    # Always ensure the wallpaper path state is written
    try:
        os.makedirs(os.path.dirname(wallpaper_path_txt), exist_ok=True)
        with open(wallpaper_path_txt, "w") as f:
            f.write(wallpaper_path)
    except Exception as e:
        print(f"Warning: Could not write active wallpaper path: {e}", file=sys.stderr)

    # 2. Perform live color injection
    
    # Read the newly generated scheme.json to perform injection
    if not os.path.exists(scheme_json_path):
        print(f"Error: scheme.json not found at '{scheme_json_path}' after extraction.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(scheme_json_path, "r") as f:
            scheme = json.load(f)
    except Exception as e:
        print(f"Error reading scheme.json: {e}", file=sys.stderr)
        sys.exit(1)

    colours = scheme.get("colours", {})
    primary = colours.get("primary")
    onSurfaceVariant = colours.get("onSurfaceVariant")

    if not primary or not onSurfaceVariant:
        print("Error: scheme.json does not contain primary or onSurfaceVariant colors.", file=sys.stderr)
        sys.exit(1)

    # a. Hyprland Injection
    if shutil.which("hyprctl"):
        print("Injecting colors into Hyprland active instances...")
        try:
            subprocess.run(["hyprctl", "keyword", "general:col.active_border", f"rgba({primary}e6)"], check=True)
            subprocess.run(["hyprctl", "keyword", "general:col.inactive_border", f"rgba({onSurfaceVariant}11)"], check=True)
        except Exception as e:
            print(f"Warning: hyprctl command failed: {e}", file=sys.stderr)

    # b. Kitty Injection
    kitty_colors_path = os.path.join(home, ".cache/wal/colors-kitty.conf")
    os.makedirs(os.path.dirname(kitty_colors_path), exist_ok=True)
    try:
        with open(kitty_colors_path, "w") as f:
            f.write(f"background #{colours.get('background', '131317')}\n")
            f.write(f"foreground #{colours.get('onBackground', 'e5e1e7')}\n")
            f.write(f"cursor #{primary}\n")
            f.write(f"selection_background #{primary}\n")
            for i in range(16):
                f.write(f"color{i} #{colours.get(f'term{i}', 'ffffff')}\n")
        
        if shutil.which("killall"):
            print("Reloading Kitty instances...")
            subprocess.run(["killall", "-USR1", "kitty"], stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Warning: failed to update Kitty colors: {e}", file=sys.stderr)

    # c. Alacritty Injection
    alacritty_colors_path = os.path.join(home, ".cache/caelestia/colors-alacritty.toml")
    os.makedirs(os.path.dirname(alacritty_colors_path), exist_ok=True)
    try:
        with open(alacritty_colors_path, "w") as f:
            f.write("[colors.primary]\n")
            f.write(f"background = \"#{colours.get('background', '131317')}\"\n")
            f.write(f"foreground = \"#{colours.get('onBackground', 'e5e1e7')}\"\n\n")
            
            f.write("[colors.normal]\n")
            f.write(f"black = \"#{colours.get('term0', '353434')}\"\n")
            f.write(f"red = \"#{colours.get('term1', 'ac73ff')}\"\n")
            f.write(f"green = \"#{colours.get('term2', '44def5')}\"\n")
            f.write(f"yellow = \"#{colours.get('term3', 'ffdcf2')}\"\n")
            f.write(f"blue = \"#{colours.get('term4', '99aad8')}\"\n")
            f.write(f"magenta = \"#{colours.get('term5', 'b49fea')}\"\n")
            f.write(f"cyan = \"#{colours.get('term6', '9dceff')}\"\n")
            f.write(f"white = \"#{colours.get('term7', 'e8d3de')}\"\n\n")
            
            f.write("[colors.bright]\n")
            f.write(f"black = \"#{colours.get('term8', 'ac9fa9')}\"\n")
            f.write(f"red = \"#{colours.get('term9', 'c093ff')}\"\n")
            f.write(f"green = \"#{colours.get('term10', '89ecff')}\"\n")
            f.write(f"yellow = \"#{colours.get('term11', 'fff0f6')}\"\n")
            f.write(f"blue = \"#{colours.get('term12', 'b5c1dd')}\"\n")
            f.write(f"magenta = \"#{colours.get('term13', 'c9b5f4')}\"\n")
            f.write(f"cyan = \"#{colours.get('term14', 'bae0ff')}\"\n")
            f.write(f"white = \"#{colours.get('term15', 'ffffff')}\"\n")

        # Ensure main config includes it
        alacritty_main = os.path.join(home, ".config/alacritty/alacritty.toml")
        import_str = 'import = ["~/.cache/caelestia/colors-alacritty.toml"]'
        if os.path.exists(alacritty_main):
            with open(alacritty_main, "r") as f:
                content = f.read()
            # Parse lines and check if colors-alacritty.toml is already imported
            lines = content.splitlines()
            has_import = False
            for line in lines:
                if "colors-alacritty.toml" in line and "import" in line:
                    has_import = True
                    break
            if not has_import:
                print("Adding colors-alacritty.toml import to alacritty.toml...")
                with open(alacritty_main, "w") as f:
                    f.write(import_str + "\n" + content)
        else:
            print("Creating alacritty.toml with colors-alacritty.toml import...")
            os.makedirs(os.path.dirname(alacritty_main), exist_ok=True)
            with open(alacritty_main, "w") as f:
                f.write(import_str + "\n")
    except Exception as e:
        print(f"Warning: failed to update Alacritty colors: {e}", file=sys.stderr)

    print("Theme applied successfully.")

if __name__ == "__main__":
    main()
