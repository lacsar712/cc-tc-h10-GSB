from hide_new import hide_if_recent, still_recomputing

def filter_overview(rows: list) -> list:
    if not still_recomputing():
        return rows
    return [r for r in rows if not hide_if_recent(r)]
