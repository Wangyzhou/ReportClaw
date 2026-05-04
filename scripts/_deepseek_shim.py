"""
Anthropic → DeepSeek shim
─────────────────────────
让 ReportClaw 的 quick_verify.sh / generate_demo_report.py / smoke_*.py
等使用 `from anthropic import Anthropic` 的脚本，**不改一行代码** 就能用
DeepSeek 跑（OpenAI 兼容协议，DeepSeek 比 Claude 便宜 ~10x）。

启用方法（quick_verify.sh 之前 export 即可）：

    export ANTHROPIC_API_KEY="$(jq -r '.profiles."deepseek:default".key' \
        ~/.openclaw/agents/main/agent/auth-profiles.json)"
    export PYTHONPATH="$(pwd)/scripts:$PYTHONPATH"
    bash scripts/quick_verify.sh

PYTHONPATH 让 Python 优先找到本目录的 sitecustomize.py，它会自动调用
本 shim 的 install_shim() 把 sys.modules['anthropic'] 替换成 fake module。

—— 写于 2026-05-03，让 ReportClaw 评委验证主线脱离 Anthropic billing。
"""
import json
import os
import sys
import urllib.request
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Anthropic 兼容数据结构
# ---------------------------------------------------------------------------


class _TextBlock:
    """对应 anthropic.types.TextBlock。"""

    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Usage:
    """对应 anthropic.types.Usage。

    DeepSeek 真返回字段（已映射到 Anthropic 兼容 + 自有扩展）：
      prompt_tokens          → input_tokens (total)
      completion_tokens      → output_tokens
      prompt_cache_hit_tokens   → cache_read_input_tokens (10x 便宜价格)
      prompt_cache_miss_tokens  → input_tokens 减去 hit 后的部分（标价）
    """

    def __init__(self, input_tokens: int = 0, output_tokens: int = 0,
                 cache_hit_tokens: int = 0, cache_miss_tokens: int = 0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        # Anthropic 接口名（前端如直接读 anthropic 字段）
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = cache_hit_tokens
        # 自有扩展（DeepSeek 真有的字段）
        self.cache_hit_tokens = cache_hit_tokens
        self.cache_miss_tokens = cache_miss_tokens


class _Message:
    """对应 anthropic.types.Message。脚本会读 .content[0].text / .usage / .stop_reason。"""

    def __init__(self, text: str, model: str, usage: dict):
        self.id = "msg_deepseek_shim"
        self.type = "message"
        self.role = "assistant"
        self.content: List[_TextBlock] = [_TextBlock(text)]
        self.model = model
        self.stop_reason = "end_turn"
        self.stop_sequence: Optional[str] = None
        # DeepSeek 真返回 prompt_cache_hit_tokens / prompt_cache_miss_tokens — 取这俩
        prompt_total = int(usage.get("prompt_tokens", 0))
        cache_hit = int(usage.get("prompt_cache_hit_tokens", 0))
        cache_miss = int(usage.get("prompt_cache_miss_tokens", prompt_total - cache_hit))
        self.usage = _Usage(
            input_tokens=prompt_total,
            output_tokens=int(usage.get("completion_tokens", 0)),
            cache_hit_tokens=cache_hit,
            cache_miss_tokens=cache_miss,
        )


# ---------------------------------------------------------------------------
# 主客户端
# ---------------------------------------------------------------------------


# Claude 模型名 → DeepSeek 模型名的映射（quick_verify.sh 用 claude-sonnet-4-6）
_MODEL_MAP = {
    "claude-sonnet-4-6": "deepseek-chat",
    "claude-opus-4-5": "deepseek-reasoner",
    "claude-haiku-4-5": "deepseek-chat",
    # 任何 claude-* 默认回落到 deepseek-chat
}


def _map_model(model: str) -> str:
    if model in _MODEL_MAP:
        return _MODEL_MAP[model]
    # 任何 claude-* 默认 deepseek-chat
    if model.startswith("claude-"):
        return "deepseek-chat"
    # 已是 deepseek-* 直接传
    return model


class _Messages:
    """对应 anthropic.Anthropic().messages。"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def create(
        self,
        model: str,
        max_tokens: int,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[list] = None,
        **kwargs: Any,
    ) -> _Message:
        ds_model = _map_model(model)
        ds_messages = []
        if system:
            ds_messages.append({"role": "system", "content": system})

        # Anthropic message content 可以是 str 或 list of blocks。展平为 OpenAI 格式 str。
        for m in messages:
            content = m.get("content")
            if isinstance(content, list):
                # 把 [{type:text, text:"..."}, ...] 拼成 str
                content = "\n".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            ds_messages.append({"role": m["role"], "content": content})

        body: dict = {
            "model": ds_model,
            "max_tokens": max_tokens,
            "messages": ds_messages,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if top_p is not None:
            body["top_p"] = top_p
        if stop_sequences is not None:
            body["stop"] = stop_sequences

        url = f"{self._base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"[deepseek-shim] HTTP {e.code} from DeepSeek: {err_body}"
            ) from e

        text = data["choices"][0]["message"]["content"]
        return _Message(text, ds_model, data.get("usage", {}))


class Anthropic:
    """drop-in replacement for `from anthropic import Anthropic`."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        # api_key 优先从参数取，其次从 env（兼容 quick_verify.sh 的 ANTHROPIC_API_KEY）
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get(
            "DEEPSEEK_API_KEY"
        )
        if not api_key:
            raise RuntimeError(
                "[deepseek-shim] no API key. Set ANTHROPIC_API_KEY (will be sent to DeepSeek) "
                "or DEEPSEEK_API_KEY."
            )
        # 允许 env 显式 override DeepSeek base URL（如走代理）
        ds_base = (
            base_url
            or os.environ.get("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )
        self.messages = _Messages(api_key=api_key, base_url=ds_base)

    # 兼容部分调用 client.close() 的脚本（noop）
    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 把自己注册成 sys.modules['anthropic']
# ---------------------------------------------------------------------------


# 同时暴露顶层 module-level __version__ 让 quick_verify.sh 的 print 不挂
__version__ = "0.1-deepseek-shim"


def install_shim() -> None:
    """让 `import anthropic` 拿到这个 shim。sitecustomize.py 调用此函数。"""
    if "anthropic" in sys.modules:
        # 已被装真包占用，shim 可能已经无效；强制覆盖
        pass
    sys.modules["anthropic"] = sys.modules[__name__]


if __name__ == "__main__":
    # quick selftest: 跑一次 DeepSeek 调用
    install_shim()
    import anthropic as _a  # 应该返回 self

    print(f"[selftest] anthropic.__version__ = {_a.__version__}")
    print(f"[selftest] anthropic.Anthropic = {_a.Anthropic}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[selftest] no key in env, skip live call")
        sys.exit(0)

    client = _a.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=64,
        messages=[{"role": "user", "content": "用一句话回答：1+1=?"}],
    )
    print(f"[selftest] LLM said: {msg.content[0].text!r}")
    print(
        f"[selftest] usage: input={msg.usage.input_tokens} output={msg.usage.output_tokens}"
    )
    print("[selftest] PASS")
