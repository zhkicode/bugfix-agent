"""用 Claude CLI 分析增量日志，识别需要修复的服务端错误。"""
from dataclasses import dataclass, field

from app.services import claude_cli
from app.services.claude_cli import ClaudeCliError

ANALYSIS_PROMPT = """你是日志分析专家。以下是 Docker 容器 `{container}`（服务于代码仓库 {repo}）最近一段时间的增量日志。

请判断其中是否存在需要修复代码的服务端错误（如 500 错误、未捕获异常堆栈、panic、数据库错误等）。
忽略：纯客户端错误（4xx）、访问日志中的正常记录、由外部依赖暂时不可用引起且代码无法修复的错误。

{logs}

若存在需要修复的错误，只输出一个 JSON 对象（不要输出任何其他内容）：
{{
  "has_error": true,
  "error_type": "错误类型，如 ZeroDivisionError / HTTP 500 / NullPointerException",
  "message": "错误关键信息（一句话）",
  "fingerprint": "规范化错误签名：错误类型+关键消息+出错文件:行号。必须去除时间戳、请求ID、端口号、随机数、具体数值等易变内容，只保留错误本质特征",
  "stack_summary": "关键堆栈摘要（保留最重要的几行）",
  "suspect_files": ["根据堆栈推断的仓库中可疑源码文件路径"]
}}

若不存在需要修复的错误，只输出：{{"has_error": false}}"""


@dataclass
class AnalysisResult:
    has_error: bool = False
    error_type: str = ""
    message: str = ""
    fingerprint: str = ""
    stack_summary: str = ""
    suspect_files: list[str] = field(default_factory=list)


async def analyze_logs(log_text: str, container_name: str, repo_url: str) -> AnalysisResult | None:
    """返回分析结果；None 表示分析本身失败（如 CLI 出错/输出无法解析）。"""
    prompt = ANALYSIS_PROMPT.format(
        container=container_name, repo=repo_url or "未知仓库", logs=log_text
    )
    last_err: Exception | None = None
    for _ in range(2):  # 失败重试一次
        try:
            result_text = await claude_cli.run_claude(prompt)
            data = claude_cli.extract_json(result_text)
            if data is None:
                raise ClaudeCliError("无法从输出中解析 JSON")
            return AnalysisResult(
                has_error=bool(data.get("has_error")),
                error_type=str(data.get("error_type", ""))[:200],
                message=str(data.get("message", "")),
                fingerprint=str(data.get("fingerprint", "")),
                stack_summary=str(data.get("stack_summary", "")),
                suspect_files=[str(f) for f in (data.get("suspect_files") or [])][:20],
            )
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"日志分析失败: {last_err}")
