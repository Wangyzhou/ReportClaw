# OpenClaw Gateway WS Demo

一个最小的 Node.js 示例，直接通过 WebSocket 连接 OpenClaw Gateway，完成：

- 等待 `connect.challenge`
- 生成并持久化设备身份
- 按 `openclaw-device-auth-v3` 规则签名
- 优先复用本地保存的 `deviceToken`
- 发送 `connect`
- 调用 `status` / `sessions.list`
- 自动选择一个会话并发送 `chat.send`
- 接收 `chat` 事件直到 `final`

## 运行

PowerShell:

```powershell
$env:OPENCLAW_GATEWAY_URL = "ws://192.168.4.188:18789"
$env:OPENCLAW_GATEWAY_TOKEN = "<your-shared-token>"
$env:OPENCLAW_MESSAGE = "你好，帮我回一句：OpenClaw Gateway WS 已连通。"
node .\examples\openclaw-gateway-ws\openclaw-ws-chat.mjs
```

也可以直接指定会话键：

```powershell
node .\examples\openclaw-gateway-ws\openclaw-ws-chat.mjs --session agent:main:main --message "你好"
```

只列出会话，不发消息：

```powershell
node .\examples\openclaw-gateway-ws\openclaw-ws-chat.mjs --list-sessions
```

可选环境变量：

- `OPENCLAW_SESSION_KEY`: 指定会话键；不传则先查 `sessions.list` 再自动选
- `OPENCLAW_DEVICE_TOKEN`: 显式指定设备令牌
- `OPENCLAW_CLIENT_ID`: 默认 `cli`
- `OPENCLAW_CLIENT_VERSION`: 默认 `0.1.0`
- `OPENCLAW_PLATFORM`: 默认按 Node 平台映射成 `windows/linux/macos`
- `OPENCLAW_DEVICE_FAMILY`: 默认 `desktop`
- `OPENCLAW_LOCALE`: 默认 `zh-CN`
- `OPENCLAW_USER_AGENT`: 默认 `openclaw-cli/0.1.0`
- `OPENCLAW_PREFER_DEVICE_TOKEN`: 默认 `1`，优先使用本地保存的 `deviceToken`；设为 `0` 可强制优先走共享 token

运行时文件：

- `examples/openclaw-gateway-ws/.runtime/device-identity.json`: 本地设备身份
- `examples/openclaw-gateway-ws/.runtime/device-token.json`: Gateway 下发的设备令牌

认证优先级（这个示例的默认策略）：

1. `OPENCLAW_DEVICE_TOKEN`
2. 本地保存的 `deviceToken`
3. `OPENCLAW_GATEWAY_TOKEN`
4. 若 2 存在但 3 不存在，则回退到本地保存的 `deviceToken`

## 预期结果

成功时你会看到：

1. 收到 `connect.challenge`
2. `connect` 返回 `hello-ok`
3. `status` / `sessions.list` 返回成功
4. `chat.send` 返回 `status=started`
5. 逐步打印 `chat` 事件中的 assistant 文本
6. `state=final` 后退出

如果报 `1008 pairing required` 或 `DEVICE_*` 错误，说明这个设备还没通过 Gateway 配对审批。
