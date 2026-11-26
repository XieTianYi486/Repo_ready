from __future__ import annotations

AI_SYSTEM_PROMPT = """你是资深的软件接入与开源仓库治理顾问。你的任务是根据给定的仓库体检摘要，给出可执行的接入建议。

必须遵守：
1. 只能使用输入 JSON 中提供的事实；不得编造文件、风险、依赖或命令。
2. 不得要求发送完整源码或任何明文密钥；输入中的敏感值已经脱敏。
3. 确定性主评分由规则引擎给出，你不能修改它。你可以给出一个独立的“AI 参考分”（0–100），并解释与主评分的差异。
4. 优先处理阻断接入的问题：真实凭据泄露、无启动方式、无依赖清单、硬编码绝对路径导致无法迁移。
5. 建议要具体到“改什么文件 / 补什么内容 / 怎么验证”，避免空泛。
6. 只输出 JSON，不要输出 Markdown、代码围栏或额外解释。"""

AI_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "reference_score": {"type": "integer"},
        "score_reason": {"type": "string"},
        "blockers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    "fix": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                    },
                },
                "required": ["title", "why", "fix", "severity"],
                "additionalProperties": False,
            },
        },
        "quick_wins": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "effect": {"type": "string"},
                },
                "required": ["action", "effect"],
                "additionalProperties": False,
            },
        },
        "integration_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step": {"type": "integer"},
                    "detail": {"type": "string"},
                },
                "required": ["step", "detail"],
                "additionalProperties": False,
            },
        },
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "reference_score",
        "score_reason",
        "blockers",
        "quick_wins",
        "integration_plan",
        "caveats",
    ],
    "additionalProperties": False,
}

AI_SCHEMA_HINT = (
    "\n\n输出必须是以下结构的 JSON（不要添加额外字段）：\n"
    '{"summary": "...", "reference_score": 0, "score_reason": "...", '
    '"blockers": [{"title": "...", "why": "...", "fix": "...", "severity": "high"}], '
    '"quick_wins": [{"action": "...", "effect": "..."}], '
    '"integration_plan": [{"step": 1, "detail": "..."}], "caveats": ["..."]}'
)
