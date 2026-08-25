"""multica 适配器：模板格式化与输出解析（不执行真实命令）。"""
import re

from app.services.multica import _SafeDict
from app.services.multica import create_task  # noqa: F401  (确保模块可导入)


def test_safe_dict_keeps_unknown_placeholder():
    d = _SafeDict(title="t")
    assert "multica task create --title t --extra {extra}".format_map(d) == (
        "multica task create --title t --extra {extra}"
    )


def test_id_regex_default_extracts_id():
    pattern = r"(?:id|ID|编号)\s*[:#=]?\s*([A-Za-z0-9\-]+)"
    m = re.search(pattern, "Created task, ID: ABC-1234 owner=zhang")
    assert m.group(1) == "ABC-1234"
    m2 = re.search(pattern, "任务编号=MT-99 已创建")
    assert m2.group(1) == "MT-99"
