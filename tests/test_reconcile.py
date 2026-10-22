from queries import reconcile


def test_reconcile_drops():
    rows = reconcile({"bronze": 758512, "silver": 727208, "gold": 727208})
    assert [r["layer"] for r in rows] == ["Bronze", "Silver", "Gold"]
    assert rows[0]["dropped"] is None
    assert rows[1]["dropped"] == 31304 and round(rows[1]["dropped_pct"], 1) == 4.1
    assert rows[2]["dropped"] == 0 and rows[2]["dropped_pct"] == 0


def test_reconcile_missing_layer():
    rows = reconcile({"bronze": None, "silver": 5, "gold": 5})
    assert rows[1]["dropped"] is None and rows[1]["dropped_pct"] is None
    assert rows[2]["dropped"] == 0


def test_every_layer_explains_its_drops():
    assert all(r["why"] for r in reconcile({"bronze": 1, "silver": 1, "gold": 1}))
