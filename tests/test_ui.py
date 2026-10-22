from ui import Node, defs, flow, status_pill, tile, tiles


def test_pill_pairs_color_with_label():
    html = status_pill("delayed", "Delayed · last order 4 h ago")
    assert "fd-state--delayed" in html and "fd-dot" in html
    assert "Delayed · last order 4 h ago" in html


def test_builders_escape_text():
    html = tile("<script>", "1")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "&lt;b&gt;" in defs([("<b>", "x")])


def test_tile_state_shows_word_next_to_dot():
    html = tile("Freshness", "12 min", state="live")
    assert "fd-state--live" in html and "Live" in html


def test_tiles_wraps_items_in_a_grid():
    html = tiles(["<div>a</div>", "<div>b</div>"])
    assert html.startswith('<div class="fd-tiles">') and "<div>a</div><div>b</div>" in html


def test_flow_can_omit_counts_for_source_and_serving():
    html = flow([Node("Source", "Simulator", counts=False)])
    assert "fd-node__rows" not in html


def test_flow_shows_dash_for_missing_rows():
    html = flow([Node("Bronze", "Auto Loader", None, "—")])
    assert "—" in html and "None" not in html


def test_flow_formats_counts_and_joins_nodes_with_arrows():
    html = flow([Node("Bronze", "Auto Loader", 758512, "1 h ago"), Node("Silver", "Dedup", 727208, "1 h ago")])
    assert "758,512" in html and "727,208" in html
    assert html.count("fd-arrow") == 1


def test_palette_reads_the_theme_config():
    from ui import palette

    light = palette("light")
    assert light["categorical"] == ["#007AFF", "#FF2D55", "#AF52DE", "#1A9AB0"]
    assert len(light["sequential"]) == 10 and light["sequential"][0] == "#cde2fb"
    assert palette("dark")["sequential"][0] == "#0d366b"


def test_number_formats_and_dashes_missing_values():
    from ui import number

    assert [number(None), number(31304), number(4.129, ".1f", "%"), number(0, ".1f", "%")] == ["—", "31,304", "4.1%", "0.0%"]


def test_pill_carries_its_freshness_for_the_monitor():
    assert 'data-freshness="stale"' in status_pill("stale", "Stale · last order 3 d ago")
