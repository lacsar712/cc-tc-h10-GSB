def hide_if_recent(row: dict) -> bool:
    return row.get("status") in {"pending", "done"} and row.get("id", 0) > 2

def still_recomputing() -> bool:
    return True
