import math
import pytest
from PySide6.QtQml import QJSValue, QQmlExpression


def _unwrap(val):
    if isinstance(val, QJSValue) and val.isQObject():
        return val.toQObject()
    return val


def _eval_js(engine, obj, code):
    obj = _unwrap(obj)
    expr = QQmlExpression(engine.rootContext(), obj, code)
    res, _ = expr.evaluate()
    if expr.hasError():
        raise RuntimeError(f"QML eval error for `{code}`: {expr.error().toString()}")
    if isinstance(res, QJSValue):
        if res.isQObject():
            return res.toQObject()
        return res.toVariant()
    return res


def _make_proc_net_dev(rows):
    header = (
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
    )
    lines = []
    for row in rows:
        if isinstance(row, str):
            lines.append(row)
            continue
        iface, rx, tx = row
        lines.append(f"{iface:>6}: {rx} 100 0 0 0 0 0 0 {tx} 100 0 0 0 0 0 0")
    return header + "\n".join(lines) + "\n"


def _get_network_usage(qml_engine):
    nu = _unwrap(qml_engine.singletonInstance("qs.services", "NetworkUsage"))
    assert nu is not None
    qml_engine.rootContext().setContextProperty("NetworkUsage", nu)
    _eval_js(qml_engine, nu, "NetworkUsage.reset()")
    _eval_js(qml_engine, nu, "NetworkUsage._sysfsPhysical = ({})")
    return nu


def test_normal_throughput_monotonic_totals_and_upload_before_download_signal(qml_engine):
    nu = _get_network_usage(qml_engine)
    down_buf = _eval_js(qml_engine, nu, "NetworkUsage.downloadBuffer")
    up_buf = _eval_js(qml_engine, nu, "NetworkUsage.uploadBuffer")

    # Capture uploadBuffer.maximum at the exact instant downloadBuffer.valuesChanged fires
    observed_up_max_on_down_signal = []
    down_buf.valuesChanged.connect(lambda: observed_up_max_on_down_signal.append(up_buf.property("maximum")))

    s0 = _make_proc_net_dev([("lo", 10_000, 10_000), ("wlp4s0", 1_000_000, 2_000_000)])
    s1 = _make_proc_net_dev([("lo", 99_999, 99_999), ("wlp4s0", 1_500_000, 4_000_000)])
    s2 = _make_proc_net_dev([("lo", 199_999, 199_999), ("wlp4s0", 2_500_000, 4_500_000)])

    nu.processSample(s0, 10_000)
    assert nu.property("downloadSpeed") == 0
    assert nu.property("uploadSpeed") == 0
    assert nu.property("downloadTotal") == 0
    assert nu.property("uploadTotal") == 0
    assert down_buf.property("count") == 0

    nu.processSample(s1, 11_000)
    assert math.isclose(nu.property("downloadSpeed"), 500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 2_000_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 2_000_000.0, rel_tol=1e-6)
    assert observed_up_max_on_down_signal == [2_000_000.0]

    nu.processSample(s2, 12_000)
    assert math.isclose(nu.property("downloadSpeed"), 1_000_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 1_500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 2_500_000.0, rel_tol=1e-6)
    assert down_buf.property("count") == 2
    assert up_buf.property("count") == 2


def test_vpn_disconnect_and_counter_reset_no_uint64_overflow(qml_engine):
    nu = _get_network_usage(qml_engine)
    up_buf = _eval_js(qml_engine, nu, "NetworkUsage.uploadBuffer")

    # Reproduce live layout: wlp4s0 + USB ethernet enp5s0f3u1u4 + happ-xray VPN
    s0 = _make_proc_net_dev([
        ("lo", 1_820_006_100, 1_820_006_100),
        ("eno1", 0, 0),
        ("wlp4s0", 104_297_101, 2_463_743_057),
        ("enp5s0f3u1u4", 296_466_698, 611_444_350),
        ("happ-xray", 124_189_932, 436_507_097),
    ])
    nu.processSample(s0, 100_000)

    # Normal upload/download on both physical NIC and VPN tunnel
    s1 = _make_proc_net_dev([
        ("lo", 1_820_006_100, 1_820_006_100),
        ("eno1", 0, 0),
        ("wlp4s0", 104_397_101, 2_463_943_057),
        ("enp5s0f3u1u4", 296_966_698, 612_444_350),
        ("happ-xray", 124_689_932, 437_507_097),
    ])
    nu.processSample(s1, 101_000)
    # Only physical deltas counted (wlp4s0 + enp5s0f3u1u4), NOT happ-xray
    assert math.isclose(nu.property("downloadTotal"), 600_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 1_200_000.0, rel_tol=1e-6)

    # happ-xray disconnects AND enp5s0f3u1u4 disappears simultaneously
    s2 = _make_proc_net_dev([
        ("lo", 1_820_006_100, 1_820_006_100),
        ("eno1", 0, 0),
        ("wlp4s0", 104_497_101, 2_464_043_057),
    ])
    nu.processSample(s2, 102_000)

    # Zero 2^64 overflow, zero sparkline spike, monotonic totals preserved
    assert math.isclose(nu.property("downloadSpeed"), 100_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 100_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 700_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 1_300_000.0, rel_tol=1e-6)
    assert up_buf.property("maximum") <= 1_200_000.0


def test_switch_ethernet_to_wifi_and_back_with_unplug_and_replug(qml_engine):
    nu = _get_network_usage(qml_engine)
    down_buf = _eval_js(qml_engine, nu, "NetworkUsage.downloadBuffer")
    up_buf = _eval_js(qml_engine, nu, "NetworkUsage.uploadBuffer")

    # Start on Ethernet (enp5s0f3u1u4) with Wi-Fi (wlp4s0) idle
    nu.processSample(
        _make_proc_net_dev([
            ("enp5s0f3u1u4", 10_000_000, 5_000_000),
            ("wlp4s0", 2_000_000, 1_000_000),
        ]),
        10_000,
    )

    # Tick 1: Active Ethernet transfer (+2 MB down, +1 MB up)
    nu.processSample(
        _make_proc_net_dev([
            ("enp5s0f3u1u4", 12_000_000, 6_000_000),
            ("wlp4s0", 2_000_000, 1_000_000),
        ]),
        11_000,
    )
    assert math.isclose(nu.property("downloadTotal"), 2_000_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 1_000_000.0, rel_tol=1e-6)

    # Tick 2: Soft switch from Ethernet to Wi-Fi (both stay present)
    nu.processSample(
        _make_proc_net_dev([
            ("enp5s0f3u1u4", 12_000_000, 6_000_000),
            ("wlp4s0", 2_500_000, 1_250_000),
        ]),
        12_000,
    )
    assert math.isclose(nu.property("downloadSpeed"), 500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 250_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 2_500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 1_250_000.0, rel_tol=1e-6)

    # Tick 3: USB Ethernet physically unplugged while Wi-Fi continues transferring
    nu.processSample(
        _make_proc_net_dev([
            ("wlp4s0", 3_500_000, 1_750_000),
        ]),
        13_000,
    )
    assert math.isclose(nu.property("downloadSpeed"), 1_000_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 3_500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 1_750_000.0, rel_tol=1e-6)

    # Tick 4: USB Ethernet plugged back in with huge pre-existing counters -> must seed without spiking
    nu.processSample(
        _make_proc_net_dev([
            ("enp5s0f3u1u4", 500_000_000, 900_000_000),
            ("wlp4s0", 3_600_000, 1_800_000),
        ]),
        14_000,
    )
    assert math.isclose(nu.property("downloadSpeed"), 100_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 50_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 3_600_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 1_800_000.0, rel_tol=1e-6)

    # Tick 5: Switch back to re-plugged Ethernet -> normal deltas resume immediately
    nu.processSample(
        _make_proc_net_dev([
            ("enp5s0f3u1u4", 501_500_000, 900_750_000),
            ("wlp4s0", 3_600_000, 1_800_000),
        ]),
        15_000,
    )
    assert math.isclose(nu.property("downloadSpeed"), 1_500_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 750_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 5_100_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 2_550_000.0, rel_tol=1e-6)
    assert down_buf.property("maximum") <= 2_000_000.0
    assert up_buf.property("maximum") <= 1_000_000.0


def test_virtual_exclusion_sysfs_classification_and_container_fallback(qml_engine):
    nu = _get_network_usage(qml_engine)

    # 1. Name heuristics exclude common VPN/container/bridge devices immediately
    for vname in ("lo", "happ-xray", "tun0", "wg0", "docker0", "veth9a3f1", "br-1234", "virbr0", "tailscale0", "CloudflareWARP"):
        assert nu.isVirtualInterfaceName(vname) is True
    for pname in ("eno1", "eth0", "wlp4s0", "enp5s0f3u1u4", "wlan0", "usb0"):
        assert nu.isVirtualInterfaceName(pname) is False

    # 2. Arbitrarily-named VPN interface is excluded once sysfs reports it virtual (0)
    nu.applySysfsClassification("wlp4s0 1\nmycustomvpn0 0\nlo 0\n")
    nu.processSample(
        _make_proc_net_dev([("wlp4s0", 1_000, 2_000), ("mycustomvpn0", 1_000, 2_000)]),
        10_000,
    )
    nu.processSample(
        _make_proc_net_dev([("wlp4s0", 6_000, 12_000), ("mycustomvpn0", 6_000, 12_000)]),
        11_000,
    )
    assert math.isclose(nu.property("downloadTotal"), 5_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 10_000.0, rel_tol=1e-6)

    # 3. Container fallback: if NO hardware-backed NICs exist (only virtual eth0), track eth0 anyway
    _eval_js(qml_engine, nu, "NetworkUsage.reset()")
    _eval_js(qml_engine, nu, "NetworkUsage._sysfsPhysical = ({})")
    nu.applySysfsClassification("eth0 0\nlo 0\ntun0 0\n")
    nu.processSample(_make_proc_net_dev([("eth0", 10_000, 20_000), ("tun0", 10_000, 20_000)]), 20_000)
    nu.processSample(_make_proc_net_dev([("eth0", 15_000, 28_000), ("tun0", 15_000, 28_000)]), 21_000)
    assert math.isclose(nu.property("downloadTotal"), 5_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 8_000.0, rel_tol=1e-6)


def test_same_interface_driver_counter_reset_clamps_to_zero(qml_engine):
    nu = _get_network_usage(qml_engine)
    up_buf = _eval_js(qml_engine, nu, "NetworkUsage.uploadBuffer")

    nu.processSample(_make_proc_net_dev([("wlp4s0", 5_000_000_000, 8_000_000_000)]), 10_000)
    nu.processSample(_make_proc_net_dev([("wlp4s0", 5_000_200_000, 8_000_300_000)]), 11_000)
    assert math.isclose(nu.property("downloadTotal"), 200_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 300_000.0, rel_tol=1e-6)

    # Driver reload / suspend resets wlp4s0 counters back near 0
    nu.processSample(_make_proc_net_dev([("wlp4s0", 4_096, 8_192)]), 12_000)
    assert nu.property("downloadSpeed") == 0
    assert nu.property("uploadSpeed") == 0
    assert math.isclose(nu.property("downloadTotal"), 200_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 300_000.0, rel_tol=1e-6)
    assert up_buf.property("maximum") == 300_000.0

    # Next tick resumes cleanly from the reset baseline
    nu.processSample(_make_proc_net_dev([("wlp4s0", 104_096, 208_192)]), 13_000)
    assert math.isclose(nu.property("downloadSpeed"), 100_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 200_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("downloadTotal"), 300_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 500_000.0, rel_tol=1e-6)


def test_parse_net_dev_unspaced_colon_and_malformed_lines(qml_engine):
    nu = _get_network_usage(qml_engine)
    raw = _make_proc_net_dev([
        "wlp4s0:12345678901 500 0 0 0 0 0 0 98765432109 600 0 0 0 0 0 0",
        "   malformed_line_without_colon 123 456",
        "short0: 100 200",
        "badnum0: abc 0 0 0 0 0 0 0 def 0 0 0 0 0 0 0",
        "lo: 999999 10 0 0 0 0 0 0 999999 10 0 0 0 0 0 0",
    ])
    parsed = _eval_js(qml_engine, nu, f"NetworkUsage.parseNetDev({raw!r})")
    assert list(parsed.keys()) == ["wlp4s0"]
    assert parsed["wlp4s0"]["rx"] == 12_345_678_901
    assert parsed["wlp4s0"]["tx"] == 98_765_432_109


def test_clock_backward_jump_and_suspend_reopen_gap(qml_engine):
    nu = _get_network_usage(qml_engine)
    down_buf = _eval_js(qml_engine, nu, "NetworkUsage.downloadBuffer")
    up_buf = _eval_js(qml_engine, nu, "NetworkUsage.uploadBuffer")

    nu.processSample(_make_proc_net_dev([("wlp4s0", 1_000_000, 1_000_000)]), 50_000)
    nu.processSample(_make_proc_net_dev([("wlp4s0", 1_100_000, 1_200_000)]), 51_000)
    assert down_buf.property("count") == 1

    # NTP clock steps backward (51_000 -> 49_000): no negative/NaN speed, no history point pushed
    nu.processSample(_make_proc_net_dev([("wlp4s0", 1_150_000, 1_250_000)]), 49_000)
    assert nu.property("downloadSpeed") == 0
    assert nu.property("uploadSpeed") == 0
    assert down_buf.property("count") == 1
    assert up_buf.property("count") == 1
    assert math.isclose(nu.property("downloadTotal"), 150_000.0, rel_tol=1e-6)

    # Next regular tick recovers cleanly (49_000 -> 50_000)
    nu.processSample(_make_proc_net_dev([("wlp4s0", 1_250_000, 1_350_000)]), 50_000)
    assert math.isclose(nu.property("downloadSpeed"), 100_000.0, rel_tol=1e-6)
    assert down_buf.property("count") == 2

    # Laptop suspends or dashboard closes for 1 hour (3_600_000 ms) while 50 MB transfers
    nu.processSample(_make_proc_net_dev([("wlp4s0", 51_250_000, 11_350_000)]), 3_650_000)
    assert nu.property("downloadSpeed") == 0
    assert nu.property("uploadSpeed") == 0
    assert down_buf.property("count") == 2  # no distorted 1-hour average pushed into sparkline
    assert math.isclose(nu.property("downloadTotal"), 50_250_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadTotal"), 10_350_000.0, rel_tol=1e-6)

    # Next 1s tick resumes instantaneously
    nu.processSample(_make_proc_net_dev([("wlp4s0", 51_500_000, 11_450_000)]), 3_651_000)
    assert math.isclose(nu.property("downloadSpeed"), 250_000.0, rel_tol=1e-6)
    assert math.isclose(nu.property("uploadSpeed"), 100_000.0, rel_tol=1e-6)
    assert down_buf.property("count") == 3


def test_format_bytes_and_totals_units_and_invalid_inputs(qml_engine):
    nu = _get_network_usage(qml_engine)

    for expr_str, expected_val, expected_unit in [
        ("NetworkUsage.formatBytes(-10)", 0, "B/s"),
        ("NetworkUsage.formatBytes(NaN)", 0, "B/s"),
        ("NetworkUsage.formatBytes(Infinity)", 0, "B/s"),
        ("NetworkUsage.formatBytes(512)", 512, "B/s"),
        ("NetworkUsage.formatBytes(2048)", 2.0, "KB/s"),
        ("NetworkUsage.formatBytes(3 * 1024 * 1024)", 3.0, "MB/s"),
        ("NetworkUsage.formatBytes(2 * 1024 * 1024 * 1024)", 2.0, "GB/s"),
        ("NetworkUsage.formatBytesTotal(-1)", 0, "B"),
        ("NetworkUsage.formatBytesTotal(NaN)", 0, "B"),
        ("NetworkUsage.formatBytesTotal(512)", 512, "B"),
        ("NetworkUsage.formatBytesTotal(4096)", 4.0, "KB"),
        ("NetworkUsage.formatBytesTotal(5 * 1024 * 1024)", 5.0, "MB"),
        ("NetworkUsage.formatBytesTotal(6 * 1024 * 1024 * 1024)", 6.0, "GB"),
        ("NetworkUsage.formatBytesTotal(2.5 * 1024 * 1024 * 1024 * 1024)", 2.5, "TB"),
    ]:
        res = _eval_js(qml_engine, nu, expr_str)
        assert res["unit"] == expected_unit
        assert math.isclose(res["value"], expected_val, rel_tol=1e-6)
