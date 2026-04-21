import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const PROTOCOL_VERSION = 3;
const RUNTIME_DIR = path.resolve("examples/openclaw-gateway-ws/.runtime");
const DEVICE_IDENTITY_PATH = path.join(RUNTIME_DIR, "device-identity.json");
const DEVICE_TOKEN_PATH = path.join(RUNTIME_DIR, "device-token.json");
const ED25519_SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

function resolveGatewayPlatform(nodePlatform) {
  if (nodePlatform === "win32") return "windows";
  if (nodePlatform === "darwin") return "macos";
  if (nodePlatform === "linux") return "linux";
  return "linux";
}

function parseCliArgs(argv) {
  const parsed = {
    gatewayUrl: "",
    gatewayToken: "",
    deviceToken: "",
    sessionKey: "",
    message: "",
    listSessions: false,
    dumpEvents: false,
    dumpPath: "",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--gateway-url" && argv[i + 1]) {
      parsed.gatewayUrl = argv[++i];
    } else if (arg === "--gateway-token" && argv[i + 1]) {
      parsed.gatewayToken = argv[++i];
    } else if (arg === "--device-token" && argv[i + 1]) {
      parsed.deviceToken = argv[++i];
    } else if (arg === "--session" && argv[i + 1]) {
      parsed.sessionKey = argv[++i];
    } else if (arg === "--message" && argv[i + 1]) {
      parsed.message = argv[++i];
    } else if (arg === "--list-sessions") {
      parsed.listSessions = true;
    } else if (arg === "--dump-events") {
      parsed.dumpEvents = true;
    } else if (arg === "--dump-path" && argv[i + 1]) {
      parsed.dumpPath = argv[++i];
    }
  }

  return parsed;
}

function timestampForFilename() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

const cliArgs = parseCliArgs(process.argv.slice(2));
const defaultOperatorScopes = ["operator.read", "operator.write"];

const config = {
  gatewayUrl:
    cliArgs.gatewayUrl ||
    process.env.OPENCLAW_GATEWAY_URL ||
    "ws://192.168.4.188:18789",
  gatewayToken: cliArgs.gatewayToken || process.env.OPENCLAW_GATEWAY_TOKEN || "",
  explicitDeviceToken:
    cliArgs.deviceToken || process.env.OPENCLAW_DEVICE_TOKEN || "",
  message:
    cliArgs.message ||
    process.env.OPENCLAW_MESSAGE ||
    "你好，帮我回一句：OpenClaw Gateway WS 已连通。",
  sessionKey: cliArgs.sessionKey || process.env.OPENCLAW_SESSION_KEY || "",
  clientId: process.env.OPENCLAW_CLIENT_ID ?? "cli",
  clientVersion: process.env.OPENCLAW_CLIENT_VERSION ?? "0.1.0",
  platform:
    process.env.OPENCLAW_PLATFORM ?? resolveGatewayPlatform(process.platform),
  locale: process.env.OPENCLAW_LOCALE ?? "zh-CN",
  userAgent: process.env.OPENCLAW_USER_AGENT ?? "openclaw-cli/0.1.0",
  deviceFamily: process.env.OPENCLAW_DEVICE_FAMILY ?? "desktop",
  listSessionsOnly: cliArgs.listSessions,
  dumpEvents:
    cliArgs.dumpEvents ||
    /^(1|true|yes)$/i.test(process.env.OPENCLAW_DUMP_EVENTS ?? ""),
  dumpPath:
    cliArgs.dumpPath ||
    process.env.OPENCLAW_DUMP_PATH ||
    path.join(RUNTIME_DIR, `ws-events-${timestampForFilename()}.jsonl`),
  preferStoredDeviceToken: !/^(0|false|no)$/i.test(
    process.env.OPENCLAW_PREFER_DEVICE_TOKEN ?? "1",
  ),
};

const clientMode = process.env.OPENCLAW_CLIENT_MODE ?? "cli";
const waitForPairing = /^(1|true|yes)$/i.test(
  process.env.OPENCLAW_WAIT_FOR_PAIRING ?? "",
);
const pairingPollMs = Number(process.env.OPENCLAW_PAIRING_POLL_MS ?? "3000");

ensureDir(RUNTIME_DIR);

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function base64UrlEncode(buf) {
  return buf
    .toString("base64")
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/g, "");
}

function normalizeDeviceMetadataForAuth(value) {
  if (typeof value !== "string") return "";
  const trimmed = value.trim();
  return trimmed.replace(/[A-Z]/g, (char) =>
    String.fromCharCode(char.charCodeAt(0) + 32),
  );
}

function derivePublicKeyRaw(publicKeyPem) {
  const key = crypto.createPublicKey(publicKeyPem);
  const spki = key.export({ type: "spki", format: "der" });
  if (
    spki.length === ED25519_SPKI_PREFIX.length + 32 &&
    spki.subarray(0, ED25519_SPKI_PREFIX.length).equals(ED25519_SPKI_PREFIX)
  ) {
    return spki.subarray(ED25519_SPKI_PREFIX.length);
  }
  return spki;
}

function publicKeyRawBase64UrlFromPem(publicKeyPem) {
  return base64UrlEncode(derivePublicKeyRaw(publicKeyPem));
}

function fingerprintPublicKey(publicKeyPem) {
  return crypto
    .createHash("sha256")
    .update(derivePublicKeyRaw(publicKeyPem))
    .digest("hex");
}

function loadOrCreateDeviceIdentity(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
      if (
        parsed?.version === 1 &&
        typeof parsed.publicKeyPem === "string" &&
        typeof parsed.privateKeyPem === "string"
      ) {
        return {
          deviceId: fingerprintPublicKey(parsed.publicKeyPem),
          publicKeyPem: parsed.publicKeyPem,
          privateKeyPem: parsed.privateKeyPem,
        };
      }
    }
  } catch {
    // fall through and regenerate
  }

  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const identity = {
    deviceId: fingerprintPublicKey(
      publicKey.export({ type: "spki", format: "pem" }),
    ),
    publicKeyPem: publicKey.export({ type: "spki", format: "pem" }),
    privateKeyPem: privateKey.export({ type: "pkcs8", format: "pem" }),
  };

  fs.writeFileSync(
    filePath,
    `${JSON.stringify(
      {
        version: 1,
        ...identity,
        createdAtMs: Date.now(),
      },
      null,
      2,
    )}\n`,
    { mode: 0o600 },
  );

  return identity;
}

function buildDeviceAuthPayloadV3({
  deviceId,
  clientId,
  clientMode,
  role,
  scopes,
  nonce,
  signedAtMs,
  token,
  platform,
  deviceFamily,
}) {
  const normalizedPlatform = normalizeDeviceMetadataForAuth(platform);
  const normalizedFamily = normalizeDeviceMetadataForAuth(deviceFamily);
  const scopeList = Array.isArray(scopes) ? scopes.join(",") : "";
  return [
    "v3",
    deviceId,
    clientId,
    clientMode,
    role,
    scopeList,
    String(signedAtMs),
    token ?? "",
    nonce ?? "",
    normalizedPlatform,
    normalizedFamily,
  ].join("|");
}

function signDevicePayload(privateKeyPem, payload) {
  const sig = crypto.sign(
    null,
    Buffer.from(payload, "utf8"),
    crypto.createPrivateKey(privateKeyPem),
  );
  return base64UrlEncode(sig);
}

function saveDeviceToken(authPayload) {
  if (!authPayload?.deviceToken) return;
  fs.writeFileSync(
    DEVICE_TOKEN_PATH,
    `${JSON.stringify(
      {
        savedAt: new Date().toISOString(),
        ...authPayload,
      },
      null,
      2,
    )}\n`,
  );
}

function loadSavedDeviceToken(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
    if (!parsed?.deviceToken || typeof parsed.deviceToken !== "string") {
      return null;
    }
    return {
      deviceToken: parsed.deviceToken,
      role: typeof parsed.role === "string" ? parsed.role : "operator",
      scopes: Array.isArray(parsed.scopes) ? parsed.scopes : [],
      issuedAtMs: parsed.issuedAtMs ?? null,
    };
  } catch {
    return null;
  }
}

function resolveConnectAuth(savedDeviceAuth) {
  if (config.explicitDeviceToken) {
    return {
      auth: { deviceToken: config.explicitDeviceToken },
      authLabel: "explicit-device-token",
      authTokenForSignature: config.explicitDeviceToken,
      scopes: defaultOperatorScopes,
    };
  }

  if (config.preferStoredDeviceToken && savedDeviceAuth?.deviceToken) {
    return {
      auth: { deviceToken: savedDeviceAuth.deviceToken },
      authLabel: "stored-device-token",
      authTokenForSignature: savedDeviceAuth.deviceToken,
      scopes:
        savedDeviceAuth.scopes.length > 0
          ? savedDeviceAuth.scopes
          : defaultOperatorScopes,
    };
  }

  if (config.gatewayToken) {
    return {
      auth: { token: config.gatewayToken },
      authLabel: "shared-token",
      authTokenForSignature: config.gatewayToken,
      scopes: defaultOperatorScopes,
    };
  }

  if (savedDeviceAuth?.deviceToken) {
    return {
      auth: { deviceToken: savedDeviceAuth.deviceToken },
      authLabel: "stored-device-token-fallback",
      authTokenForSignature: savedDeviceAuth.deviceToken,
      scopes:
        savedDeviceAuth.scopes.length > 0
          ? savedDeviceAuth.scopes
          : defaultOperatorScopes,
    };
  }

  throw new Error(
    "Missing connect auth. Provide OPENCLAW_GATEWAY_TOKEN or an explicit/stored device token.",
  );
}

function randomId(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function incrementCounter(map, key) {
  map.set(key, (map.get(key) ?? 0) + 1);
}

function sortedEntries(map) {
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function writeJsonlLine(filePath, value) {
  fs.appendFileSync(filePath, `${JSON.stringify(value)}\n`);
}

function createTraceCollector({ enabled, filePath }) {
  const stats = {
    inboundFrames: new Map(),
    outboundFrames: new Map(),
    chatStates: new Map(),
    messageBlockTypes: new Map(),
    payloadKeys: new Map(),
  };

  if (enabled) {
    ensureDir(path.dirname(filePath));
  }

  function record(direction, frame, context = {}) {
    const frameKey =
      frame?.type === "event"
        ? `event:${frame.event ?? "<missing>"}`
        : frame?.type === "res"
          ? `res:${context.method ?? frame.id ?? "<missing>"}`
          : frame?.type === "req"
            ? `req:${frame.method ?? "<missing>"}`
            : `${frame?.type ?? "unknown"}`;

    incrementCounter(
      direction === "inbound" ? stats.inboundFrames : stats.outboundFrames,
      frameKey,
    );

    if (frame?.type === "event" && frame.event === "chat") {
      incrementCounter(stats.chatStates, frame.payload?.state ?? "unknown");
      const payload = frame.payload ?? {};
      for (const key of Object.keys(payload)) {
        incrementCounter(stats.payloadKeys, key);
      }

      const blocks = Array.isArray(payload.message?.content)
        ? payload.message.content
        : [];
      for (const block of blocks) {
        if (typeof block === "string") {
          incrementCounter(stats.messageBlockTypes, "string");
        } else if (block && typeof block === "object") {
          incrementCounter(
            stats.messageBlockTypes,
            block.type ?? "<object-without-type>",
          );
        } else {
          incrementCounter(stats.messageBlockTypes, typeof block);
        }
      }
    }

    if (enabled) {
      writeJsonlLine(filePath, {
        ts: new Date().toISOString(),
        direction,
        frameKey,
        context,
        frame,
      });
    }
  }

  return {
    enabled,
    filePath,
    recordInbound(frame, context = {}) {
      record("inbound", frame, context);
    },
    recordOutbound(frame, context = {}) {
      record("outbound", frame, context);
    },
    printSummary() {
      console.log("\n--- WS event summary ---");
      console.log("Inbound frames:");
      for (const [key, count] of sortedEntries(stats.inboundFrames)) {
        console.log(`  ${key}: ${count}`);
      }
      console.log("Outbound frames:");
      for (const [key, count] of sortedEntries(stats.outboundFrames)) {
        console.log(`  ${key}: ${count}`);
      }
      if (stats.chatStates.size > 0) {
        console.log("Chat states:");
        for (const [key, count] of sortedEntries(stats.chatStates)) {
          console.log(`  ${key}: ${count}`);
        }
      }
      if (stats.messageBlockTypes.size > 0) {
        console.log("Message block types:");
        for (const [key, count] of sortedEntries(stats.messageBlockTypes)) {
          console.log(`  ${key}: ${count}`);
        }
      }
      if (stats.payloadKeys.size > 0) {
        console.log("Chat payload keys:");
        for (const [key, count] of sortedEntries(stats.payloadKeys)) {
          console.log(`  ${key}: ${count}`);
        }
      }
      if (enabled) {
        console.log(`Raw WS frames saved to: ${filePath}`);
      }
    },
  };
}

function renderMessageText(message) {
  if (!message) return "";
  if (typeof message === "string") return message;
  if (typeof message.text === "string") return message.text;
  if (Array.isArray(message.content)) {
    return message.content
      .map((block) => {
        if (typeof block === "string") return block;
        if (block?.type === "text" && typeof block.text === "string") {
          return block.text;
        }
        if (block?.type === "input_text" && typeof block.text === "string") {
          return block.text;
        }
        return "";
      })
      .filter(Boolean)
      .join("");
  }
  return JSON.stringify(message);
}

function extractSessionKeys(payload) {
  const found = new Set();

  function visit(value) {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }
    for (const [key, child] of Object.entries(value)) {
      if (
        typeof child === "string" &&
        ["sessionKey", "key", "resolvedKey", "requestedKey"].includes(key)
      ) {
        found.add(child);
      } else {
        visit(child);
      }
    }
  }

  visit(payload);
  return [...found];
}

function pickSessionKey(explicitKey, discoveredKeys) {
  if (explicitKey) return explicitKey;
  const preferred = ["agent:main:main", "main"];
  for (const key of preferred) {
    if (discoveredKeys.includes(key)) return key;
  }
  return discoveredKeys[0] ?? "agent:main:main";
}

function formatSessionKeys(keys) {
  if (!keys.length) return "(none)";
  return keys.map((key, index) => `${index + 1}. ${key}`).join("\n");
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runSingleAttempt(identity) {
  const publicKey = publicKeyRawBase64UrlFromPem(identity.publicKeyPem);
  const savedDeviceAuth = loadSavedDeviceToken(DEVICE_TOKEN_PATH);
  const connectAuth = resolveConnectAuth(savedDeviceAuth);
  const ws = new WebSocket(config.gatewayUrl);
  const trace = createTraceCollector({
    enabled: config.dumpEvents,
    filePath: config.dumpPath,
  });

  let requestCounter = 0;
  let currentRunId = null;
  let currentSessionKey = config.sessionKey;
  let lastAssistantText = "";
  let settled = false;
  const pending = new Map();
  const requestMethods = new Map();

  function closeSocket(code = 1000, reason = "done") {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close(code, reason);
    }
  }

  function request(method, params = {}) {
    const id = `req-${++requestCounter}`;
    const frame = { type: "req", id, method, params };
    requestMethods.set(id, method);
    trace.recordOutbound(frame, { method });
    ws.send(JSON.stringify(frame));
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject, method });
      setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(new Error(`Timed out waiting for ${method}`));
        }
      }, 30000);
    });
  }

  function settlePendingOnClose(error) {
    for (const { reject, method } of pending.values()) {
      reject(error ?? new Error(`Connection closed during ${method}`));
    }
    pending.clear();
  }

  function finish(kind, payload = {}) {
    trace.printSummary();
    settled = true;
    return { kind, ...payload };
  }

  const finished = new Promise((resolve, reject) => {
    ws.addEventListener("open", () => {
      console.log(
        `WS connected -> ${config.gatewayUrl} (auth=${connectAuth.authLabel})`,
      );
    });

    ws.addEventListener("error", (event) => {
      if (settled) return;
      settled = true;
      reject(event.error ?? new Error("WebSocket error"));
    });

    ws.addEventListener("close", (event) => {
      const msg = `WS closed code=${event.code} reason=${event.reason || "<empty>"}`;
      console.log(msg);
      settlePendingOnClose(new Error(msg));
      if (settled) {
        resolve({ kind: "closed" });
      } else {
        settled = true;
        reject(new Error(msg));
      }
    });

    ws.addEventListener("message", async (event) => {
      const raw = event.data.toString();
      let frame;
      try {
        frame = JSON.parse(raw);
      } catch (error) {
        console.error("Non-JSON frame:", raw);
        return;
      }

      trace.recordInbound(frame, {
        method:
          frame.type === "res"
            ? requestMethods.get(frame.id) ??
              (frame.id === "connect-1" ? "connect" : undefined)
            : undefined,
      });

      if (frame.type === "event" && frame.event === "tick") {
        return;
      }

      if (frame.type === "event" && frame.event === "connect.challenge") {
        console.log("Received connect.challenge");
        const signedAt = Date.now();
        const scopes = connectAuth.scopes;
        const payload = buildDeviceAuthPayloadV3({
          deviceId: identity.deviceId,
          clientId: config.clientId,
          clientMode,
          role: "operator",
          scopes,
          nonce: frame.payload?.nonce ?? "",
          signedAtMs: signedAt,
          token: connectAuth.authTokenForSignature,
          platform: config.platform,
          deviceFamily: config.deviceFamily,
        });

        const connectParams = {
          minProtocol: PROTOCOL_VERSION,
          maxProtocol: PROTOCOL_VERSION,
          client: {
            id: config.clientId,
            version: config.clientVersion,
            platform: config.platform,
            deviceFamily: config.deviceFamily,
            mode: clientMode,
          },
          role: "operator",
          scopes,
          caps: [],
          commands: [],
          permissions: {},
          auth: connectAuth.auth,
          locale: config.locale,
          userAgent: config.userAgent,
          device: {
            id: identity.deviceId,
            publicKey,
            signature: signDevicePayload(identity.privateKeyPem, payload),
            signedAt,
            nonce: frame.payload?.nonce ?? "",
          },
        };

        const connectFrame = {
          type: "req",
          id: "connect-1",
          method: "connect",
          params: connectParams,
        };
        requestMethods.set("connect-1", "connect");
        trace.recordOutbound(connectFrame, { method: "connect" });
        ws.send(JSON.stringify(connectFrame));
        return;
      }

      if (frame.type === "res") {
        if (frame.id === "connect-1") {
          if (!frame.ok) {
            const details = frame.error?.details ?? {};
            if (details.code === "PAIRING_REQUIRED") {
              console.log(
                `Pairing required -> requestId=${details.requestId ?? "<missing>"} deviceId=${identity.deviceId}`,
              );
              resolve(
                finish("pairing_required", {
                  requestId: details.requestId ?? null,
                  error: frame.error ?? {},
                }),
              );
            } else {
              settled = true;
              reject(
                new Error(
                  `connect failed: ${JSON.stringify(frame.error ?? {}, null, 2)}`,
                ),
              );
            }
            closeSocket(1000, "connect-result");
            return;
          }

          console.log(
            `Connected. hello type=${frame.payload?.type} protocol=${frame.payload?.protocol}`,
          );

          if (frame.payload?.auth?.deviceToken) {
            saveDeviceToken(frame.payload.auth);
            console.log("Saved gateway-issued device token.");
          }

          try {
            const status = await request("status");
            console.log(
              `status ok -> gateway=${
                status?.payload?.name ??
                status?.payload?.gateway?.name ??
                "available"
              }`,
            );

            let discoveredKeys = [];
            if (config.sessionKey) {
              currentSessionKey = config.sessionKey;
              console.log(
                `Using explicit sessionKey="${currentSessionKey}" (skipped sessions.list)`,
              );
            } else {
              const sessions = await request("sessions.list");
              discoveredKeys = extractSessionKeys(sessions.payload);
              currentSessionKey = pickSessionKey("", discoveredKeys);
              console.log(
                `sessions.list ok -> discovered ${discoveredKeys.length} session(s), using "${currentSessionKey}"`,
              );
              if (config.listSessionsOnly) {
                console.log(`Sessions:\n${formatSessionKeys(discoveredKeys)}`);
                resolve(
                  finish("listed_sessions", {
                    sessionKeys: discoveredKeys,
                  }),
                );
                closeSocket(1000, "listed-sessions");
                return;
              }
            }

            const sendResult = await request("chat.send", {
              sessionKey: currentSessionKey,
              message: config.message,
              idempotencyKey: randomId("chat"),
            });
            currentRunId = sendResult?.payload?.runId ?? null;
            console.log(
              `chat.send ok -> runId=${currentRunId ?? "<missing>"} status=${sendResult?.payload?.status ?? "<unknown>"}`,
            );
          } catch (error) {
            settled = true;
            reject(error);
            closeSocket(1011, "request-failed");
          }
          return;
        }

        const pendingRequest = pending.get(frame.id);
        if (!pendingRequest) return;
        pending.delete(frame.id);

        if (frame.ok) {
          pendingRequest.resolve(frame);
        } else {
          pendingRequest.reject(
            new Error(
              `${pendingRequest.method} failed: ${JSON.stringify(
                frame.error ?? {},
                null,
                2,
              )}`,
            ),
          );
        }
        return;
      }

      if (frame.type === "event" && frame.event === "chat") {
        const payload = frame.payload ?? {};
        if (currentRunId && payload.runId && payload.runId !== currentRunId) {
          return;
        }

        const state = payload.state ?? "unknown";
        const assistantText = renderMessageText(payload.message);
        if (assistantText && assistantText !== lastAssistantText) {
          const delta = assistantText.startsWith(lastAssistantText)
            ? assistantText.slice(lastAssistantText.length)
            : `\n[full snapshot]\n${assistantText}`;
          process.stdout.write(delta);
          lastAssistantText = assistantText;
        }

        if (state === "final") {
          process.stdout.write("\n");
          console.log(`chat completed for session=${payload.sessionKey ?? currentSessionKey}`);
          resolve(finish("completed", { runId: currentRunId, sessionKey: payload.sessionKey ?? currentSessionKey }));
          closeSocket(1000, "done");
        } else if (state === "aborted" || state === "error") {
          settled = true;
          reject(new Error(`chat ended with state=${state}: ${JSON.stringify(payload, null, 2)}`));
          closeSocket(1011, "chat-error");
        }
      }
    });
  });

  return await finished;
}

async function main() {
  const identity = loadOrCreateDeviceIdentity(DEVICE_IDENTITY_PATH);
  console.log(`Using deviceId=${identity.deviceId}`);

  let attempt = 0;
  let lastRequestId = null;

  while (true) {
    attempt += 1;
    console.log(`\n=== Attempt ${attempt} ===`);
    const result = await runSingleAttempt(identity);

    if (result.kind === "completed") {
      return;
    }

    if (result.kind === "listed_sessions") {
      return;
    }

    if (result.kind === "pairing_required" && waitForPairing) {
      const requestId = result.requestId ?? "<missing>";
      const suffix =
        lastRequestId && lastRequestId !== requestId
          ? ` (requestId changed from ${lastRequestId})`
          : "";
      lastRequestId = requestId;
      console.log(
        `Still waiting for pairing approval. requestId=${requestId}${suffix}. Retrying in ${pairingPollMs}ms...`,
      );
      await wait(pairingPollMs);
      continue;
    }

    if (result.kind === "pairing_required") {
      throw new Error(
        `Pairing required. requestId=${result.requestId ?? "<missing>"} deviceId=${identity.deviceId}`,
      );
    }

    if (result.kind === "closed") {
      throw new Error("Connection closed before the chat completed.");
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack : error);
  process.exitCode = 1;
});
