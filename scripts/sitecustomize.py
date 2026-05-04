"""
Auto-installed when PYTHONPATH 包含 scripts/。
Python 启动后自动 import sitecustomize，这里把 _deepseek_shim 注入成 anthropic。
"""
import os
import sys

# 仅当 USE_DEEPSEEK_SHIM=1 时启用，避免污染其他 Python 项目
if os.environ.get("USE_DEEPSEEK_SHIM") == "1":
    from _deepseek_shim import install_shim
    install_shim()
