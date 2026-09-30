from h10_extra_trap import armed, expose_list

def test_hide():
    rows = [{"id": 1, "status": "done"}, {"id": 9, "status": "done"}]
    out = expose_list(rows)
    assert len(out) == 1
    assert armed() is True
