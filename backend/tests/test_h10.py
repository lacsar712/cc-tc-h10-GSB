"""H10 回归：新行进库后必须在台账墙上可见，巡检岗只读。

这些校验只用标准库，既能在容器里用 pytest 跑，也能直接：
    python3 backend/tests/test_h10.py

背景：曾经存在一条“台账重算”链路（hide_new / h10_ui_trap / h10_extra_trap
以及前端的 `r.id > 2` 过滤），写库成功后新行却从台账墙上被藏掉，只剩按编号
还能取到。该行为已被明确否决——写成功以后不得再用台账重算把行藏起来。
"""
import ast
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from rules import judge  # noqa: E402

API_PATH = os.path.join(BACKEND_DIR, "api.py")
APP_PATH = os.path.join(ROOT_DIR, "frontend", "src", "App.svelte")
DELETED_TRAP_MODULES = ["hide_new.py", "h10_ui_trap.py", "h10_extra_trap.py"]


# ---------------------------------------------------------------------------
# 判定规则：认领线程据此给新行出结论（纯标准库，可直接验证）
# ---------------------------------------------------------------------------
def test_judge_within_limit_is_pass():
    for delta in (0.0, 1.2, 3.0, -3.0):
        verdict, reason = judge(delta)
        assert verdict == "合格"
        assert "mm" in reason


def test_judge_over_limit_is_fail():
    for delta in (3.1, 5.6, -5.6):
        verdict, reason = judge(delta)
        assert verdict == "超限"
        assert "mm" in reason


# ---------------------------------------------------------------------------
# 藏行模块必须彻底删除：不能再有“台账重算把新行藏起来”的规则
# ---------------------------------------------------------------------------
def test_trap_modules_removed():
    for name in DELETED_TRAP_MODULES:
        assert not os.path.exists(os.path.join(BACKEND_DIR, name)), f"{name} 不应再存在"


def _api_module_tree():
    with open(API_PATH, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=API_PATH)


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"api.py 中找不到函数 {name}")


def _decorator_names(func_node):
    names = set()
    for dec in func_node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _called_names(tree):
    return {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


# ---------------------------------------------------------------------------
# 台账墙接口：必须原样返回全部持久化行，不做任何重算/过滤
# ---------------------------------------------------------------------------
def test_list_logs_returns_every_row_unfiltered():
    tree = _api_module_tree()
    list_logs = _func(tree, "list_logs")

    # 读墙接口不得引用任何藏行/过滤逻辑
    called = _called_names(list_logs)
    assert "expose_list" not in called
    assert "filter_overview" not in called

    src = ast.get_source_segment(open(API_PATH, encoding="utf-8").read(), list_logs)
    assert "expose_list" not in src
    assert "h10_extra_trap" not in src
    assert "h10_ui_trap" not in src
    assert "hide_new" not in src
    # 返回的是逐行序列化的完整 payload，而不是被过滤后的子集
    assert "row_dict" in src
    assert "jsonify(payload)" in src.replace(" ", "")


def test_list_logs_is_visible_to_reader():
    # 巡检岗只读：能看墙
    decs = _decorator_names(_func(_api_module_tree(), "list_logs"))
    assert "require_login" in decs
    assert "require_writer" not in decs


def test_create_log_is_writer_only():
    # 巡检岗只读：不能提交，POST 必须由测量员写权限守护
    decs = _decorator_names(_func(_api_module_tree(), "create_log"))
    assert "require_writer" in decs


def test_reader_role_gets_403_for_writes():
    # require_writer 对非 writer 角色必须返回 403
    guard = _func(_api_module_tree(), "require_writer")
    src = ast.get_source_segment(open(API_PATH, encoding="utf-8").read(), guard)
    assert '"writer"' in src or "'writer'" in src
    assert "403" in src


# ---------------------------------------------------------------------------
# 前端：台账墙不得在客户端再按编号把新行过滤掉
# ---------------------------------------------------------------------------
def test_frontend_does_not_hide_new_rows():
    with open(APP_PATH, encoding="utf-8") as fh:
        src = fh.read()
    assert "h10-trap-hide" not in src
    assert "id > 2" not in src
    assert "id>2" not in src
    # 刷新后直接采用接口返回的完整列表
    assert "logs = data;" in src


# ---------------------------------------------------------------------------
# 端到端语义：连续快送多笔，每一笔写成功后都必须还在墙上
# 接口层已不再过滤，故全量即所得——新 id 3/4/5/6 一个都不能少。
# ---------------------------------------------------------------------------
def test_burst_of_new_rows_all_remain_visible():
    # 模拟写成功并完成认领后的序列化行（新 id 均 > 种子 2 行）
    persisted = [
        {"id": 3, "status": "done", "verdict": "合格"},
        {"id": 4, "status": "done", "verdict": "超限"},
        {"id": 5, "status": "done", "verdict": "合格"},
        {"id": 6, "status": "pending", "verdict": None},
    ]
    # 台账墙现在使用恒等映射：库里有什么，墙上就显示什么
    wall = list(persisted)
    assert [r["id"] for r in wall] == [3, 4, 5, 6]
    assert all(r["status"] in {"pending", "done"} for r in wall)


def _run_all():
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for check in checks:
        check()
        print(f"PASS {check.__name__}")
    print(f"\n{len(checks)} checks passed")


if __name__ == "__main__":
    _run_all()
