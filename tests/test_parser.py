import os
import sys
import json
import subprocess
import tempfile
import pathlib
import pytest

PARSER_PATH = "/home/execorn/programming/projects/hyprland_cheat_sheet/parser/parse_keybinds.py"

def run_parser(variables_paths, keybinds_path, output_path):
    cmd = ["python3", PARSER_PATH]
    if variables_paths:
        cmd.extend(["--variables"] + [str(p) for p in variables_paths])
    else:
        cmd.extend(["--variables", "/dev/null"])
    cmd.extend(["--keybinds", str(keybinds_path)])
    cmd.extend(["--output", str(output_path)])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res

def run_parser_with_content(var_content, keybinds_content, is_caelestia=True):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        var_file = tmp_path / "variables.conf"
        keybinds_filename = "caelestia_keybinds.conf" if is_caelestia else "keybinds.conf"
        key_file = tmp_path / keybinds_filename
        out_file = tmp_path / "keybinds.json"
        
        var_file.write_text(var_content, encoding='utf-8')
        key_file.write_text(keybinds_content, encoding='utf-8')
        
        res = run_parser([var_file], key_file, out_file)
        
        data = None
        if res.returncode == 0 and out_file.exists():
            with open(out_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    pass
                
        return res, data

def validate_json_schema(data):
    assert isinstance(data, list), "Root must be a list"
    for section in data:
        assert isinstance(section, dict), "Section must be a dict"
        assert "section" in section, "Section must contain 'section'"
        assert isinstance(section["section"], str), "Section name must be a string"
        assert "categories" in section, "Section must contain 'categories'"
        assert isinstance(section["categories"], list), "Categories must be a list"
        for category in section["categories"]:
            assert isinstance(category, dict), "Category must be a dict"
            assert "category" in category, "Category must contain 'category'"
            assert isinstance(category["category"], str), "Category name must be a string"
            assert "keybinds" in category, "Category must contain 'keybinds'"
            assert isinstance(category["keybinds"], list), "Keybinds must be a list"
            for keybind in category["keybinds"]:
                assert isinstance(keybind, dict), "Keybind must be a dict"
                assert "mods" in keybind, "Keybind must contain 'mods'"
                assert isinstance(keybind["mods"], list), "mods must be a list"
                for mod in keybind["mods"]:
                    assert isinstance(mod, str), "Modifier must be a string"
                assert "key" in keybind, "Keybind must contain 'key'"
                assert isinstance(keybind["key"], str), "Key must be a string"
                assert "action" in keybind, "Keybind must contain 'action'"
                assert isinstance(keybind["action"], str), "Action must be a string"
                assert "desc" in keybind, "Keybind must contain 'desc'"
                assert isinstance(keybind["desc"], str), "Desc must be a string"


# ==========================================
# FEATURE 1: Variable Declaration Extraction
# ==========================================

def test_var_extract_standard():
    var_content = "$var = val\n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec val"

def test_var_extract_whitespace():
    var_content = "  $var   \t = \t  val  \n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec val"

def test_var_extract_inline_comment():
    var_content = "$var = val # inline comment here\n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec val"

def test_var_extract_unicode():
    var_content = "$var = 🚀unicode\n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec 🚀unicode"

def test_var_extract_multiple():
    var_content = "$v1 = first\n$v2 = second\n"
    key_content = "bind = SUPER, T, exec, $v1 $v2"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec first second"

def test_t2_var_extract_unbalanced_quotes():
    var_content = '$var = "val\n'
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == 'exec "val'

def test_t2_var_extract_empty_definition():
    var_content = "$var =\n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == 'exec'

def test_t2_var_extract_duplicate_declarations():
    var_content = "$var = first\n$var = second\n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec second"

def test_t2_var_extract_special_symbols_names():
    var_content = "$var_name_123 = val\n"
    key_content = "bind = SUPER, T, exec, $var_name_123"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec val"

def test_t2_var_extract_malformed_lines():
    var_content = "$var val\n"
    key_content = "bind = SUPER, T, exec, $var"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert "$var" in data[0]["categories"][0]["keybinds"][0]["action"]


# ==========================================
# FEATURE 2: Recursive Variable Resolution
# ==========================================

def test_var_resolve_single():
    var_content = "$v1 = hello\n"
    key_content = "bind = SUPER, T, exec, $v1"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec hello"

def test_var_resolve_multi():
    var_content = "$v1 = hello\n$v2 = world\n"
    key_content = "bind = SUPER, T, exec, $v1 $v2"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec hello world"

def test_var_resolve_nested():
    var_content = "$v2 = nested\n$v1 = $v2\n"
    key_content = "bind = SUPER, T, exec, $v1"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec nested"

def test_var_resolve_undefined():
    var_content = ""
    key_content = "bind = SUPER, T, exec, $nonexistent"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec $nonexistent"

def test_var_resolve_mixed():
    var_content = "$v1 = hello\n"
    key_content = "bind = SUPER, T, exec, prefix $v1 suffix"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec prefix hello suffix"

def test_t2_var_resolve_deep_chain():
    var_lines = [f"$v{i} = $v{i+1}" for i in range(1, 100)]
    var_lines.append("$v100 = deepval")
    var_content = "\n".join(var_lines)
    key_content = "bind = SUPER, T, exec, $v1"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec deepval"

def test_t2_var_resolve_dollar_no_var():
    var_content = ""
    key_content = "bind = SUPER, T, exec, $100 dollars"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec $100 dollars"

def test_t2_var_resolve_whitespace_in_ref():
    var_content = "$var = value\n"
    key_content = "bind = SUPER, T, exec, $var name"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec value name"

def test_t2_var_resolve_multiple_duplicate_refs():
    var_content = "$v = x\n"
    key_content = "bind = SUPER, T, exec, $v $v $v"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec x x x"

def test_t2_var_resolve_empty_resolutions():
    var_content = "$v = \n"
    key_content = "bind = SUPER, T, exec, start $v end"
    res, data = run_parser_with_content(var_content, key_content)
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec start  end"


# ==========================================
# FEATURE 3: Variable Cycle/Recursion Guard
# ==========================================

def test_cycle_guard_direct():
    var_content = "$v = $v\n"
    key_content = "bind = SUPER, T, exec, $v"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec $v"

def test_cycle_guard_indirect():
    var_content = "$a = $b\n$b = $a\n"
    key_content = "bind = SUPER, T, exec, $a"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] in ("exec $a", "exec $b")

def test_cycle_guard_deep():
    var_content = "$a = $b\n$b = $c\n$c = $a\n"
    key_content = "bind = SUPER, T, exec, $a"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] in ("exec $a", "exec $b", "exec $c")

def test_cycle_guard_recovery():
    var_content = "$a = $a\n$b = safe\n"
    key_content = "bind = SUPER, T, exec, $a $b"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec $a safe"

def test_cycle_guard_limit():
    var_lines = [f"$v{i} = $v{i+1}" for i in range(1, 50)]
    var_lines.append("$v50 = ok")
    var_content = "\n".join(var_lines)
    key_content = "bind = SUPER, T, exec, $v1"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec ok"

def test_t2_cycle_complex_mesh():
    var_content = "$a = $b $c\n$b = $d\n$d = $b\n$c = clean\n"
    key_content = "bind = SUPER, T, exec, $a"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    action = data[0]["categories"][0]["keybinds"][0]["action"]
    assert "clean" in action

def test_t2_cycle_extremely_deep_crash():
    var_lines = [f"$v{i} = $v{i+1}" for i in range(1, 1500)]
    var_lines.append("$v1500 = end")
    var_content = "\n".join(var_lines)
    key_content = "bind = SUPER, T, exec, $v1"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 1
    assert "RecursionError" in res.stderr

def test_t2_cycle_partial_resolution():
    var_content = "$a = $b $c\n$b = $b\n$c = clean\n"
    key_content = "bind = SUPER, T, exec, $a"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec $b clean"

def test_t2_cycle_reentry():
    var_content = "$a = $b\n$b = $a\n$c = $d\n$d = $c\n"
    key_content = "bind = SUPER, T, exec, $a\nbind = SUPER, Y, exec, $c"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    binds = data[0]["categories"][0]["keybinds"]
    assert binds[0]["action"] in ("exec $a", "exec $b")
    assert binds[1]["action"] in ("exec $c", "exec $d")

def test_t2_cycle_empty_cycle():
    var_content = "$a = $b\n$b = \n"
    key_content = "bind = SUPER, T, exec, $a"
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert data[0]["categories"][0]["keybinds"][0]["action"] == "exec"


# ==========================================
# FEATURE 4: Keybinding Line Parse and Split
# ==========================================

def test_bind_split_standard():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["mods"] == ["SUPER"]
    assert bind["key"] == "T"
    assert bind["action"] == "exec kitty"

def test_bind_split_no_args():
    res, data = run_parser_with_content("", "bind = SUPER, T, killactive")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["mods"] == ["SUPER"]
    assert bind["key"] == "T"
    assert bind["action"] == "killactive"

def test_bind_split_special_chars():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, echo 'hello, world'")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["action"] == "exec echo 'hello, world'"

def test_bind_split_invalid_format():
    res, data = run_parser_with_content("", "bind = SUPER, T")
    assert len(data) == 0

def test_bind_split_multiple_delimiters():
    res, data = run_parser_with_content("", "bind = SUPER SHIFT ALT, T, exec, kitty")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert set(bind["mods"]) == {"SUPER", "SHIFT", "ALT"}

def test_t2_bind_split_too_many_commas():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty, extra1, extra2")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["action"] == "exec kitty, extra1, extra2"

def test_t2_bind_split_escaped_commas():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, command\\,with\\,escaped")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["action"] == "exec command\\,with\\,escaped"

def test_t2_bind_split_empty_fields():
    res, data = run_parser_with_content("", "bind = SUPER,,exec,")
    assert len(data[0]["categories"][0]["keybinds"]) == 1
    bind = data[0]["categories"][0]["keybinds"][0]
    assert bind["mods"] == ["SUPER"]
    assert bind["key"] == ""
    assert bind["action"] == "exec"

def test_t2_bind_split_tabs_as_delimiter():
    res, data = run_parser_with_content("", "bind\t=\tSUPER\tSHIFT\t,\tT\t,\texec\t,\tkitty")
    bind = data[0]["categories"][0]["keybinds"][0]
    assert set(bind["mods"]) == {"SUPER", "SHIFT"}
    assert bind["key"] == "T"
    assert bind["action"] == "exec kitty"

def test_t2_bind_split_missing_dispatcher():
    res, data = run_parser_with_content("", "bind = SUPER, T")
    assert len(data) == 0


# ==========================================
# FEATURE 5: Modifier Normalization
# ==========================================

def test_mod_norm_lower():
    res, data = run_parser_with_content("", "bind = super, T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == ["SUPER"]

def test_mod_norm_alternative():
    res, data = run_parser_with_content("", "bind = mod4, T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == ["SUPER"]

def test_mod_norm_multiple():
    res, data = run_parser_with_content("", "bind = super+ctrl+shift, T, exec, kitty")
    assert set(data[0]["categories"][0]["keybinds"][0]["mods"]) == {"SUPER", "CTRL", "SHIFT"}

def test_mod_norm_variable():
    res, data = run_parser_with_content("", "bind = $mainMod, T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == ["$mainMod"]

def test_mod_norm_unknown():
    res, data = run_parser_with_content("", "bind = custom_mod, T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == ["CUSTOM_MOD"]

def test_t2_mod_norm_duplicate_mods():
    res, data = run_parser_with_content("", "bind = super+super, T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == ["SUPER"]

def test_t2_mod_norm_trailing_plus():
    res, data = run_parser_with_content("", "bind = super+shift+, T, exec, kitty")
    assert set(data[0]["categories"][0]["keybinds"][0]["mods"]) == {"SUPER", "SHIFT"}

def test_t2_mod_norm_space_plus_mix():
    res, data = run_parser_with_content("", "bind = super + shift alt+ctrl, T, exec, kitty")
    assert set(data[0]["categories"][0]["keybinds"][0]["mods"]) == {"SUPER", "SHIFT", "ALT", "CTRL"}

def test_t2_mod_norm_non_standard_case():
    res, data = run_parser_with_content("", "bind = SuPeR, T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == ["SUPER"]

def test_t2_mod_norm_only_key():
    res, data = run_parser_with_content("", "bind = , T, exec, kitty")
    assert data[0]["categories"][0]["keybinds"][0]["mods"] == []


# ==========================================
# FEATURE 6: Internal Keybinding Filtering
# ==========================================

def test_filter_interrupt():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, my_command --interrupt\nbind = SUPER, G, exec, normal")
    binds = data[0]["categories"][0]["keybinds"]
    assert len(binds) == 1
    assert binds[0]["action"] == "exec normal"

def test_filter_catchall():
    res, data = run_parser_with_content("", "bind = SUPER, catchall, exec, normal\nbind = SUPER, G, exec, normal")
    binds = data[0]["categories"][0]["keybinds"]
    assert len(binds) == 1
    assert binds[0]["key"] == "G"

def test_filter_mouse_actions():
    res, data = run_parser_with_content("", "bind = SUPER, mouse:272, exec, normal\nbind = SUPER, G, exec, normal")
    binds = data[0]["categories"][0]["keybinds"]
    assert len(binds) == 1
    assert binds[0]["key"] == "G"

def test_filter_mouse_scroll():
    res, data = run_parser_with_content("", "bind = SUPER, mouse_down, exec, normal\nbind = SUPER, G, exec, normal")
    binds = data[0]["categories"][0]["keybinds"]
    assert len(binds) == 1

def test_filter_empty():
    # Ignore line if it has fewer than 3 elements, e.g. "bind = SUPER"
    res, data = run_parser_with_content("", "bind = SUPER")
    assert len(data) == 0

def test_t2_filter_mixed_case():
    res, data = run_parser_with_content("", "bind = SUPER, CaTcHaLl, exec, normal")
    assert len(data) == 0

def test_t2_filter_partial_match():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, mousepad\nbind = SUPER, G, exec, normal")
    binds = data[0]["categories"][0]["keybinds"]
    actions = [b["action"] for b in binds]
    assert "exec mousepad" in actions

def test_t2_filter_mouse_key_bounds():
    res, data = run_parser_with_content("", "bind = SUPER, mouse:273, exec, normal")
    assert len(data) == 0

def test_t2_filter_spaces():
    res, data = run_parser_with_content("", "bind = SUPER,   catchall   , exec, normal")
    assert len(data) == 0

def test_t2_filter_all_ignored():
    res, data = run_parser_with_content("", "bind = SUPER, catchall, exec, normal")
    assert len(data) == 0


# ==========================================
# FEATURE 7: Description Association
# ==========================================

def test_desc_assoc_inline():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty # Open terminal")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Open terminal"

def test_desc_assoc_accumulated():
    # Adding periods to prevent comments from being treated as category headers
    res, data = run_parser_with_content("", """
# Preceding description line 1.
# Preceding description line 2.
bind = SUPER, T, exec, kitty
""")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Preceding description line 1. Preceding description line 2."

def test_desc_assoc_friendly_fallback():
    res, data = run_parser_with_content("", "bind = SUPER, C, killactive")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Close Active Window"

def test_desc_assoc_exec_fallback():
    res, data = run_parser_with_content("", "bind = SUPER, E, exec, Nemo")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Launch Nemo"

def test_desc_assoc_workspace_fallback():
    res, data = run_parser_with_content("", "bind = SUPER, 1, workspace, 1")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Switch to Workspace 1"

def test_t2_desc_multiline_empty_lines():
    res, data = run_parser_with_content("", """
# First Block.

# Second Block.
bind = SUPER, T, exec, kitty
""")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Second Block."

def test_t2_desc_unfriendly_fallback():
    res, data = run_parser_with_content("", "bind = SUPER, T, unrecognized_dispatcher, arg")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "unrecognized_dispatcher, arg"

def test_t2_desc_special_characters():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty # Test with special \"quotes\" and \\ backslashes")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Test with special \"quotes\" and \\ backslashes"

def test_t2_desc_empty_comments():
    res, data = run_parser_with_content("", """
#   
#  
bind = SUPER, C, killactive
""")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Close Active Window"

def test_t2_desc_very_long_comment():
    long_desc = "X" * 1000
    res, data = run_parser_with_content("", f"bind = SUPER, T, exec, kitty # {long_desc}")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == long_desc


# ==========================================
# FEATURE 8: Explicit Section & Category Headers
# ==========================================

def test_header_section_explicit():
    # Run with is_caelestia=False to prevent section overriding via implicit auto-routing
    res, data = run_parser_with_content("", """
# Section: My Section
# Category: My Category
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert data[0]["section"] == "My Section"
    assert data[0]["categories"][0]["category"] == "My Category"

def test_header_category_explicit():
    res, data = run_parser_with_content("", """
# Section: Custom Section
# Category: Custom Category
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert data[0]["section"] == "Custom Section"
    assert data[0]["categories"][0]["category"] == "Custom Category"

def test_header_case_insensitive():
    res, data = run_parser_with_content("", """
# sEcTiOn: Case Section
# cAtEgOrY: Case Category
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert data[0]["section"] == "Case Section"
    assert data[0]["categories"][0]["category"] == "Case Category"

def test_header_hierarchy():
    res, data = run_parser_with_content("", """
# Section: S1
# Category: C1
bind = SUPER, T, exec, kitty
# Category: C2
bind = SUPER, G, exec, normal
""", is_caelestia=False)
    assert len(data[0]["categories"]) == 2
    assert data[0]["categories"][0]["category"] == "C1"
    assert data[0]["categories"][1]["category"] == "C2"

def test_header_duplicate_prevention():
    res, data = run_parser_with_content("", """
# Section: S1
# Category: C1
bind = SUPER, T, exec, kitty
# Section: S1
# Category: C1
bind = SUPER, G, exec, normal
""", is_caelestia=False)
    assert len(data) == 1
    assert len(data[0]["categories"]) == 1
    assert len(data[0]["categories"][0]["keybinds"]) == 2

def test_t2_header_empty_section_name():
    res, data = run_parser_with_content("", """
## 
# Category: C1
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert len(data) > 0

def test_t2_header_nested_categories():
    res, data = run_parser_with_content("", """
# Category: Cat1
# Category: Cat2
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert data[0]["categories"][0]["category"] == "Cat2"

def test_t2_header_leading_trailing_junk():
    res, data = run_parser_with_content("", """
# Section:  --- My Section ***
# Category: === My Category ===
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert data[0]["section"] == "--- My Section ***"
    assert data[0]["categories"][0]["category"] == "=== My Category ==="

def test_t2_header_category_no_section():
    res, data = run_parser_with_content("", """
# Category: Cat Without Section
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    assert len(data) > 0

def test_t2_header_overwrite_implicit():
    res, data = run_parser_with_content("", """
# Section: System
# Category: Volume
bind = SUPER, T, exec, kitty
# Category: Window Management
bind = SUPER, G, exec, kitty
""", is_caelestia=False)
    assert len(data) > 0


# ==========================================
# FEATURE 9: Implicit Category Auto-Routing
# ==========================================

def test_implicit_route_window():
    res, data = run_parser_with_content("", """
# Window Resize
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "Windows"

def test_implicit_route_system():
    res, data = run_parser_with_content("", """
# Volume Up
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "System"

def test_implicit_route_app():
    res, data = run_parser_with_content("", """
# Open Browser
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "Applications"

def test_implicit_route_utility():
    res, data = run_parser_with_content("", """
# Screenshot Region
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "Utilities"

def test_implicit_route_general():
    res, data = run_parser_with_content("", """
# Random Category Name
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "General"

def test_t2_implicit_route_priority():
    res, data = run_parser_with_content("", """
# Window Volume
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "Windows"

def test_t2_implicit_route_boundary():
    short_header = "W" * 39
    res, data = run_parser_with_content("", f"""
# {short_header}
bind = SUPER, T, exec, kitty
""")
    assert len(data[0]["categories"]) == 1
    assert data[0]["categories"][0]["category"] == short_header.title()

def test_t2_implicit_route_with_actions():
    res, data = run_parser_with_content("", """
# Toggle to full screen.
bind = SUPER, T, exec, kitty
""")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "Toggle to full screen."

def test_t2_implicit_route_special_chars():
    res, data = run_parser_with_content("", """
# Window 管理
bind = SUPER, T, exec, kitty
""")
    assert data[0]["section"] == "Windows"

def test_t2_implicit_route_mixed_mode():
    res, data = run_parser_with_content("", """
# Category: Explicit Cat
bind = SUPER, T, exec, kitty
# Volume Control
bind = SUPER, G, exec, kitty
""")
    sections = [s["section"] for s in data]
    assert "General" in sections
    assert "System" in sections


# ==========================================
# FEATURE 10: JSON Serialization & Integration
# ==========================================

def test_json_write_success():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty")
    assert res.returncode == 0
    assert data is not None

def test_json_schema_validation():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty")
    validate_json_schema(data)

def test_json_utf8():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty # 中文描述")
    assert data[0]["categories"][0]["keybinds"][0]["desc"] == "中文描述"

def test_json_create_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        nested_dir = tmp_path / "deep" / "nested" / "dir"
        out_file = nested_dir / "keybinds.json"
        
        var_file = tmp_path / "var.conf"
        var_file.write_text("", encoding='utf-8')
        key_file = tmp_path / "key.conf"
        key_file.write_text("bind = SUPER, T, exec, kitty", encoding='utf-8')
        
        res = run_parser([var_file], key_file, out_file)
        assert res.returncode == 0
        assert out_file.exists()

def test_json_clean_empty():
    res, data = run_parser_with_content("", """
# Section: Empty Section
# Category: Empty Category
# Section: Active Section
# Category: Active Category
bind = SUPER, T, exec, kitty
""", is_caelestia=False)
    sections = [s["section"] for s in data]
    assert "Empty Section" not in sections
    assert "Active Section" in sections

def test_t2_json_write_permission_denied():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        out_file = tmp_path / "denied" / "keybinds.json"
        parent = tmp_path / "denied"
        parent.mkdir()
        parent.chmod(0o400)
        
        var_file = tmp_path / "var.conf"
        var_file.write_text("", encoding='utf-8')
        key_file = tmp_path / "key.conf"
        key_file.write_text("bind = SUPER, T, exec, kitty", encoding='utf-8')
        
        try:
            res = run_parser([var_file], key_file, out_file)
            assert res.returncode in (0, 1)
        finally:
            parent.chmod(0o700)

def test_t2_json_large_payload():
    var_content = ""
    key_lines = [f"bind = SUPER, K{i}, exec, action{i}" for i in range(2000)]
    key_content = "\n".join(key_lines)
    res, data = run_parser_with_content(var_content, key_content)
    assert res.returncode == 0
    assert len(data[0]["categories"][0]["keybinds"]) == 2000

def test_t2_json_existing_file_lock():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        out_file = tmp_path / "keybinds.json"
        out_file.write_text("existing content", encoding='utf-8')
        
        var_file = tmp_path / "var.conf"
        var_file.write_text("", encoding='utf-8')
        key_file = tmp_path / "key.conf"
        key_file.write_text("bind = SUPER, T, exec, kitty", encoding='utf-8')
        
        res = run_parser([var_file], key_file, out_file)
        assert res.returncode == 0
        assert out_file.exists()
        with open(out_file) as f:
            data = json.load(f)
        assert len(data) > 0

def test_t2_json_empty_source():
    res, data = run_parser_with_content("", "")
    assert res.returncode == 0
    assert data == []

def test_t2_json_output_corruption_recovery():
    res, data = run_parser_with_content("", "bind = SUPER, T, exec, kitty")
    assert res.returncode == 0
