from h10_ui_trap import filter_overview
from hide_new import still_recomputing

def expose_list(rows: list) -> list:
    return filter_overview(rows)

def armed() -> bool:
    return still_recomputing()
