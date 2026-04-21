# OpenClaw Chat UI

一个最小可用的 Spring Boot 3 + Java 21 应用：

- 前端是仿 AI 助手的对话 UI
- 后端直接连 OpenClaw Gateway WebSocket
- 浏览器拿到的是流式 NDJSON
- 文字回复和工具轨迹同时可见

## 技术栈

- Java 21
- Spring Boot 3
- Maven
- 原生浏览器 JS / CSS

## 运行前提

本项目默认会优先复用已经配对过的设备状态目录：

`../examples/openclaw-gateway-ws/.runtime`

如果你已经用仓库里的 Node 示例完成过配对，这里通常不需要再次审批。

## 本地启动

PowerShell:

```powershell
cd .\openclaw-chat-ui
$env:JAVA_HOME = 'D:\jdk-21.0.8'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
mvn -s .\settings.xml spring-boot:run
```

如果要强制指定 Gateway：

```powershell
$env:OPENCLAW_GATEWAY_URL = 'ws://192.168.4.188:18789'
$env:OPENCLAW_GATEWAY_TOKEN = '<shared-token>'
$env:OPENCLAW_SESSION_KEY = 'agent:main:main'
mvn -s .\settings.xml spring-boot:run
```

也可以直接运行 Maven 构建出的可执行 jar：

```powershell
.\scripts\build.ps1
& 'D:\jdk-21.0.8\bin\java.exe' -jar .\.build\openclaw-chat-ui-0.1.0-exec.jar --server.port=8090
```

打开：

`http://localhost:8080`

如果 8080 已被占用，就像上面那样加 `--server.port=8090`，然后打开 `http://localhost:8090`。

## 可调环境变量

- `OPENCLAW_GATEWAY_URL`
- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_DEVICE_TOKEN`
- `OPENCLAW_SESSION_KEY`
- `OPENCLAW_DEVICE_STATE_DIR`
- `OPENCLAW_PREFER_DEVICE_TOKEN`

## 接口

- `GET /api/sessions`
- `POST /api/chat/stream`

`/api/chat/stream` 返回 `application/x-ndjson`，每行一个 JSON 事件。

## 事件类型

- `connected`
- `run-started`
- `assistant-delta`
- `activity`
- `command-output`
- `lifecycle`
- `done`
- `error`
