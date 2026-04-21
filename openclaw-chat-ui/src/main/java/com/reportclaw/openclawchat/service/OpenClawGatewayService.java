package com.reportclaw.openclawchat.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.reportclaw.openclawchat.api.dto.ChatRequest;
import com.reportclaw.openclawchat.api.dto.SessionSummary;
import com.reportclaw.openclawchat.api.dto.StreamEvent;
import com.reportclaw.openclawchat.config.OpenClawProperties;
import com.reportclaw.openclawchat.service.OpenClawDeviceStateStore.DeviceIdentity;
import com.reportclaw.openclawchat.service.OpenClawDeviceStateStore.StoredDeviceToken;
import jakarta.annotation.PreDestroy;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.FluxSink;
import reactor.core.publisher.Mono;

@Service
public class OpenClawGatewayService {

    private static final Logger log = LoggerFactory.getLogger(OpenClawGatewayService.class);

    private static final Set<String> SESSION_KEY_FIELDS = Set.of("sessionKey", "key", "resolvedKey", "requestedKey");
    private static final List<String> DEFAULT_SCOPES = List.of("operator.read", "operator.write");

    private final ObjectMapper objectMapper;
    private final OpenClawProperties properties;
    private final OpenClawDeviceStateStore deviceStateStore;
    private final ExecutorService gatewayExecutor;

    public OpenClawGatewayService(
            ObjectMapper objectMapper,
            OpenClawProperties properties,
            OpenClawDeviceStateStore deviceStateStore
    ) {
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.deviceStateStore = deviceStateStore;
        this.gatewayExecutor = java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor();
    }

    public Mono<List<SessionSummary>> listSessions() {
        return Mono.create(sink -> gatewayExecutor.submit(() -> {
            try (GatewayConnection connection = new GatewayConnection()) {
                connection.connect();
                List<String> keys = connection.listSessions();
                List<SessionSummary> sessions = keys.stream()
                        .map(key -> new SessionSummary(key, describeSessionKey(key)))
                        .toList();
                sink.success(sessions);
            } catch (Exception exception) {
                sink.error(exception);
            }
        }));
    }

    public Flux<StreamEvent> streamChat(ChatRequest request) {
        return Flux.create(emitter -> {
            AtomicBoolean cancelled = new AtomicBoolean(false);
            emitter.onDispose(() -> cancelled.set(true));
            gatewayExecutor.submit(() -> streamChatBlocking(request, emitter, cancelled));
        }, FluxSink.OverflowStrategy.BUFFER);
    }

    @PreDestroy
    public void shutdown() {
        gatewayExecutor.close();
    }

    private void streamChatBlocking(ChatRequest request, FluxSink<StreamEvent> emitter, AtomicBoolean cancelled) {
        try (GatewayConnection connection = new GatewayConnection()) {
            connection.connect();
            emitter.next(new StreamEvent(
                    "connected",
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    "OpenClaw gateway connected",
                    null,
                    null,
                    null,
                    null,
                    Instant.now(),
                    null
            ));
            connection.streamChat(request, emitter, cancelled);
        } catch (Exception exception) {
            emitter.next(errorEvent(exception.getMessage()));
        } finally {
            emitter.complete();
        }
    }

    private StreamEvent errorEvent(String message) {
        return new StreamEvent(
                "error",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                "Gateway error",
                null,
                null,
                message,
                null,
                Instant.now(),
                null
        );
    }

    private String describeSessionKey(String key) {
        if ("agent:main:main".equals(key)) {
            return "Main Session";
        }
        if (key.contains(":feishu:group:")) {
            return "Feishu Group";
        }
        if (key.contains(":feishu:direct:")) {
            return "Feishu Direct";
        }
        if (key.contains(":cron:")) {
            return "Cron Run";
        }
        if (key.contains(":subagent:")) {
            return "Sub-Agent";
        }
        return key;
    }

    private final class GatewayConnection implements AutoCloseable {

        private final BlockingQueue<JsonNode> inbox = new LinkedBlockingQueue<>();
        private final HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(properties.getConnectTimeout())
                .build();
        private final DeviceIdentity identity = deviceStateStore.loadOrCreateIdentity(properties.resolveDeviceStateDir());
        private final StoredDeviceToken storedDeviceToken = deviceStateStore.loadStoredToken(properties.resolveDeviceStateDir());
        private final ConnectAuth connectAuth = resolveConnectAuth(storedDeviceToken);
        private final Duration readTimeout = properties.getReadTimeout();

        private final AtomicBoolean closed = new AtomicBoolean(false);
        private WebSocket webSocket;
        private int requestCounter = 0;

        void connect() {
            try {
                this.webSocket = httpClient.newWebSocketBuilder()
                        .connectTimeout(properties.getConnectTimeout())
                        .buildAsync(URI.create(properties.getGatewayUrl()), new QueueingListener())
                        .join();

                boolean connected = false;
                while (!connected) {
                    JsonNode frame = nextFrame(readTimeout);
                    if (isCloseMarker(frame)) {
                        throw new IllegalStateException("Gateway closed during connect: " + closeReason(frame));
                    }
                    if (isErrorMarker(frame)) {
                        throw new IllegalStateException("Gateway listener error: " + frame.path("message").asText("unknown"));
                    }

                    if (isEvent(frame, "connect.challenge")) {
                        sendConnect(frame.path("payload"));
                        continue;
                    }

                    if (isResponse(frame, "connect-1")) {
                        if (!frame.path("ok").asBoolean(false)) {
                            throw new IllegalStateException(readError(frame));
                        }
                        JsonNode auth = frame.path("payload").path("auth");
                        if (!auth.isMissingNode()) {
                            deviceStateStore.saveDeviceToken(properties.resolveDeviceStateDir(), auth);
                        }
                        connected = true;
                    }
                }
            } catch (RuntimeException exception) {
                close();
                throw exception;
            }
        }

        List<String> listSessions() {
            String requestId = nextRequestId();
            ObjectNode frame = requestFrame(requestId, "sessions.list", objectMapper.createObjectNode());
            sendFrame(frame);

            while (true) {
                JsonNode incoming = nextFrame(readTimeout);
                if (isCloseMarker(incoming)) {
                    throw new IllegalStateException("Gateway closed while listing sessions: " + closeReason(incoming));
                }
                if (isErrorMarker(incoming)) {
                    throw new IllegalStateException("Gateway listener error: " + incoming.path("message").asText("unknown"));
                }
                if (isResponse(incoming, requestId)) {
                    if (!incoming.path("ok").asBoolean(false)) {
                        throw new IllegalStateException(readError(incoming));
                    }
                    List<String> keys = new ArrayList<>();
                    extractSessionKeys(incoming.path("payload"), keys);
                    return keys.stream().distinct().toList();
                }
            }
        }

        void streamChat(ChatRequest request, FluxSink<StreamEvent> emitter, AtomicBoolean cancelled) {
            String sessionKey = request.sessionKey() == null || request.sessionKey().isBlank()
                    ? properties.getDefaultSessionKey()
                    : request.sessionKey().trim();

            String requestId = nextRequestId();
            ObjectNode params = objectMapper.createObjectNode();
            params.put("sessionKey", sessionKey);
            params.put("message", buildEnrichedMessage(request));
            params.put("idempotencyKey", "chat-" + UUID.randomUUID());
            sendFrame(requestFrame(requestId, "chat.send", params));

            String runId = null;
            String assistantSnapshot = "";

            while (!cancelled.get()) {
                JsonNode incoming = nextFrame(readTimeout);

                if (isCloseMarker(incoming)) {
                    emitter.next(errorEvent("Gateway closed mid-stream: " + closeReason(incoming)));
                    return;
                }
                if (isErrorMarker(incoming)) {
                    emitter.next(errorEvent("Gateway listener error: " + incoming.path("message").asText("unknown")));
                    return;
                }

                String frameType = incoming.path("type").asText("?");
                String frameEvent = incoming.path("event").asText("?");
                log.info("[stream] frame type={} event={} id={}", frameType, frameEvent, incoming.path("id").asText("?"));
                log.debug("[stream] full frame: {}", incoming.toString().substring(0, Math.min(incoming.toString().length(), 500)));

                if (runId == null && isResponse(incoming, requestId)) {
                    if (!incoming.path("ok").asBoolean(false)) {
                        emitter.next(errorEvent(readError(incoming)));
                        return;
                    }
                    runId = incoming.path("payload").path("runId").asText("");
                    emitter.next(new StreamEvent(
                            "run-started",
                            runId,
                            sessionKey,
                            null,
                            incoming.path("payload").path("status").asText(null),
                            null,
                            null,
                            null,
                            null,
                            "Chat run started",
                            null,
                            null,
                            null,
                            null,
                            Instant.now(),
                            incoming.path("payload")
                    ));
                    continue;
                }

                if (isEvent(incoming, "agent")) {
                    JsonNode payload = incoming.path("payload");
                    String eventRunId = payload.path("runId").asText();
                    String stream = payload.path("stream").asText("?");
                    log.info("[agent] stream={} runId={} (expecting={})", stream, eventRunId, runId);
                    if (!Objects.equals(runId, eventRunId)) {
                        log.info("[agent] skipped: runId mismatch");
                        continue;
                    }
                    StreamEvent activity = mapAgentEvent(payload);
                    if (activity != null) {
                        emitter.next(activity);
                    } else {
                        log.info("[agent] mapAgentEvent returned null for stream={}", stream);
                    }
                    continue;
                }

                if (isEvent(incoming, "chat")) {
                    JsonNode payload = incoming.path("payload");
                    String eventRunId = payload.path("runId").asText();
                    log.info("[chat] state={} runId={} (expecting={})", payload.path("state").asText("?"), eventRunId, runId);
                    if (!Objects.equals(runId, eventRunId)) {
                        log.info("[chat] skipped: runId mismatch");
                        continue;
                    }

                    String state = payload.path("state").asText("unknown");
                    String fullText = renderMessageText(payload.path("message").path("content"));
                    log.info("[chat] fullText length={}, content structure={}", fullText.length(),
                            payload.path("message").path("content").getNodeType());
                    String delta = "";
                    if (!fullText.equals(assistantSnapshot)) {
                        delta = fullText.startsWith(assistantSnapshot)
                                ? fullText.substring(assistantSnapshot.length())
                                : fullText;
                        assistantSnapshot = fullText;
                        emitter.next(new StreamEvent(
                                "assistant-delta",
                                runId,
                                payload.path("sessionKey").asText(sessionKey),
                                "chat",
                                state,
                                null,
                                null,
                                null,
                                null,
                                null,
                                null,
                                null,
                                fullText,
                                delta,
                                Instant.now(),
                                payload
                        ));
                    }

                    if ("final".equals(state)) {
                        emitter.next(new StreamEvent(
                                "done",
                                runId,
                                payload.path("sessionKey").asText(sessionKey),
                                "chat",
                                state,
                                null,
                                null,
                                null,
                                null,
                                "Chat completed",
                                null,
                                null,
                                assistantSnapshot,
                                null,
                                Instant.now(),
                                payload
                        ));
                        return;
                    }

                    if ("error".equals(state) || "aborted".equals(state)) {
                        emitter.next(errorEvent("Chat ended with state=" + state));
                        return;
                    }
                }
            }
        }

        private StreamEvent mapAgentEvent(JsonNode payload) {
            String stream = payload.path("stream").asText("");
            JsonNode data = payload.path("data");
            String runId = payload.path("runId").asText(null);
            String sessionKey = payload.path("sessionKey").asText(null);
            Instant timestamp = Instant.ofEpochMilli(payload.path("ts").asLong(System.currentTimeMillis()));

            return switch (stream) {
                case "item" -> new StreamEvent(
                        "activity",
                        runId,
                        sessionKey,
                        stream,
                        null,
                        data.path("kind").asText(null),
                        data.path("phase").asText(null),
                        data.path("name").asText(null),
                        data.path("status").asText(null),
                        data.path("title").asText(null),
                        data.path("itemId").asText(null),
                        data.path("toolCallId").asText(null),
                        pickFirstText(data, "progressText", "summary", "meta"),
                        null,
                        timestamp,
                        data
                );
                case "command_output" -> new StreamEvent(
                        "command-output",
                        runId,
                        sessionKey,
                        stream,
                        null,
                        null,
                        data.path("phase").asText(null),
                        data.path("name").asText(null),
                        data.path("status").asText(null),
                        data.path("title").asText(null),
                        data.path("itemId").asText(null),
                        data.path("toolCallId").asText(null),
                        data.path("output").asText(null),
                        null,
                        timestamp,
                        data
                );
                case "assistant" -> new StreamEvent(
                        "assistant-trace",
                        runId,
                        sessionKey,
                        stream,
                        null,
                        "assistant",
                        null,
                        null,
                        null,
                        "Assistant stream",
                        null,
                        null,
                        data.path("delta").asText(data.path("text").asText(null)),
                        data.path("delta").asText(null),
                        timestamp,
                        data
                );
                case "lifecycle" -> new StreamEvent(
                        "lifecycle",
                        runId,
                        sessionKey,
                        stream,
                        null,
                        null,
                        data.path("phase").asText(null),
                        null,
                        data.path("livenessState").asText(null),
                        "Agent lifecycle",
                        null,
                        null,
                        null,
                        null,
                        timestamp,
                        data
                );
                default -> null;
            };
        }

        private String pickFirstText(JsonNode node, String... fields) {
            for (String field : fields) {
                JsonNode candidate = node.path(field);
                if (candidate.isTextual() && !candidate.asText().isBlank()) {
                    return candidate.asText();
                }
            }
            return null;
        }

        private void sendConnect(JsonNode challengePayload) {
            long signedAt = System.currentTimeMillis();
            String nonce = challengePayload.path("nonce").asText("");
            String publicKey = deviceStateStore.publicKeyBase64Url(identity);
            String payload = String.join("|",
                    "v3",
                    identity.deviceId(),
                    properties.getClientId(),
                    "cli",
                    "operator",
                    String.join(",", connectAuth.scopes()),
                    Long.toString(signedAt),
                    connectAuth.tokenForSignature(),
                    nonce,
                    properties.getPlatform().trim().toLowerCase(),
                    properties.getDeviceFamily().trim().toLowerCase()
            );

            ObjectNode params = objectMapper.createObjectNode();
            params.put("minProtocol", 3);
            params.put("maxProtocol", 3);

            ObjectNode client = params.putObject("client");
            client.put("id", properties.getClientId());
            client.put("version", properties.getClientVersion());
            client.put("platform", properties.getPlatform());
            client.put("deviceFamily", properties.getDeviceFamily());
            client.put("mode", "cli");

            params.put("role", "operator");
            ArrayNode scopes = params.putArray("scopes");
            connectAuth.scopes().forEach(scopes::add);
            params.set("caps", objectMapper.createArrayNode());
            params.set("commands", objectMapper.createArrayNode());
            params.set("permissions", objectMapper.createObjectNode());
            params.set("auth", connectAuth.authNode());
            params.put("locale", properties.getLocale());
            params.put("userAgent", properties.getUserAgent());

            ObjectNode device = params.putObject("device");
            device.put("id", identity.deviceId());
            device.put("publicKey", publicKey);
            device.put("signature", deviceStateStore.signPayload(identity, payload));
            device.put("signedAt", signedAt);
            device.put("nonce", nonce);

            sendFrame(requestFrame("connect-1", "connect", params));
        }

        private void sendFrame(ObjectNode frame) {
            try {
                webSocket.sendText(frame.toString(), true)
                        .orTimeout(30, TimeUnit.SECONDS)
                        .join();
            } catch (java.util.concurrent.CompletionException ex) {
                if (ex.getCause() instanceof java.util.concurrent.TimeoutException) {
                    throw new IllegalStateException("Timed out sending frame to OpenClaw gateway");
                }
                throw ex;
            }
        }

        private ObjectNode requestFrame(String id, String method, JsonNode params) {
            ObjectNode frame = objectMapper.createObjectNode();
            frame.put("type", "req");
            frame.put("id", id);
            frame.put("method", method);
            frame.set("params", params);
            return frame;
        }

        private String nextRequestId() {
            requestCounter += 1;
            return "req-" + requestCounter;
        }

        private JsonNode nextFrame(Duration timeout) {
            try {
                JsonNode frame = inbox.poll(timeout.toMillis(), TimeUnit.MILLISECONDS);
                if (frame == null) {
                    throw new IllegalStateException("Timed out waiting for OpenClaw gateway response");
                }
                return frame;
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("Interrupted while waiting for OpenClaw gateway response", exception);
            }
        }

        private boolean isEvent(JsonNode frame, String eventName) {
            return "event".equals(frame.path("type").asText()) && eventName.equals(frame.path("event").asText());
        }

        private boolean isResponse(JsonNode frame, String requestId) {
            return "res".equals(frame.path("type").asText()) && requestId.equals(frame.path("id").asText());
        }

        private boolean isCloseMarker(JsonNode frame) {
            return frame.path("__close").asBoolean(false);
        }

        private boolean isErrorMarker(JsonNode frame) {
            return frame.path("__error").asBoolean(false);
        }

        private String closeReason(JsonNode frame) {
            return "code=" + frame.path("statusCode").asText("?") + " reason=" + frame.path("reason").asText("");
        }

        private String readError(JsonNode frame) {
            JsonNode error = frame.path("error");
            String code = error.path("code").asText("UNKNOWN");
            String message = error.path("message").asText("Gateway request failed");
            JsonNode details = error.path("details");
            if (details.isObject() && !details.isEmpty()) {
                return code + ": " + message + " (" + details.toString() + ")";
            }
            return code + ": " + message;
        }

        private String buildEnrichedMessage(ChatRequest request) {
            String mode = request.mode();
            if (mode == null || mode.equals("smart")) {
                return request.message();
            }
            StringBuilder sb = new StringBuilder();
            sb.append("【模式:").append(mode).append("】\n");
            var docs = request.mentionedDocs();
            if (docs != null && !docs.isEmpty()) {
                for (var doc : docs) {
                    sb.append("【参考文件:").append(doc.name())
                      .append("(").append(doc.category())
                      .append(",id=").append(doc.id()).append(")】\n");
                }
            }
            sb.append(request.message());
            return sb.toString();
        }

        private String renderMessageText(JsonNode content) {
            if (content == null || content.isMissingNode() || !content.isArray()) {
                return "";
            }
            StringBuilder builder = new StringBuilder();
            for (JsonNode block : content) {
                if (block.isTextual()) {
                    builder.append(block.asText());
                    continue;
                }
                String type = block.path("type").asText("");
                if ("text".equals(type) || "input_text".equals(type)) {
                    builder.append(block.path("text").asText(""));
                }
            }
            return builder.toString();
        }

        private void extractSessionKeys(JsonNode node, List<String> keys) {
            if (node == null || node.isMissingNode()) {
                return;
            }
            if (node.isArray()) {
                for (JsonNode child : node) {
                    extractSessionKeys(child, keys);
                }
                return;
            }
            if (!node.isObject()) {
                return;
            }
            node.fields().forEachRemaining(entry -> {
                if (SESSION_KEY_FIELDS.contains(entry.getKey()) && entry.getValue().isTextual()) {
                    keys.add(entry.getValue().asText());
                }
                extractSessionKeys(entry.getValue(), keys);
            });
        }

        @Override
        public void close() {
            if (closed.compareAndSet(false, true) && webSocket != null) {
                try {
                    webSocket.sendClose(WebSocket.NORMAL_CLOSURE, "done").join();
                } catch (Exception ignored) {
                    webSocket.abort();
                }
            }
        }

        private final class QueueingListener implements WebSocket.Listener {
            private final StringBuilder buffer = new StringBuilder();

            @Override
            public void onOpen(WebSocket webSocket) {
                webSocket.request(1);
            }

            @Override
            public java.util.concurrent.CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
                buffer.append(data);
                if (last) {
                    try {
                        inbox.offer(objectMapper.readTree(buffer.toString()));
                    } catch (Exception exception) {
                        ObjectNode error = objectMapper.createObjectNode();
                        error.put("__error", true);
                        error.put("message", exception.getMessage());
                        inbox.offer(error);
                    } finally {
                        buffer.setLength(0);
                    }
                }
                webSocket.request(1);
                return null;
            }

            @Override
            public java.util.concurrent.CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
                ObjectNode close = objectMapper.createObjectNode();
                close.put("__close", true);
                close.put("statusCode", statusCode);
                close.put("reason", reason == null ? "" : reason);
                inbox.offer(close);
                return WebSocket.Listener.super.onClose(webSocket, statusCode, reason);
            }

            @Override
            public void onError(WebSocket webSocket, Throwable error) {
                ObjectNode marker = objectMapper.createObjectNode();
                marker.put("__error", true);
                marker.put("message", error.getMessage());
                inbox.offer(marker);
            }
        }
    }

    private ConnectAuth resolveConnectAuth(StoredDeviceToken storedDeviceToken) {
        if (properties.getExplicitDeviceToken() != null && !properties.getExplicitDeviceToken().isBlank()) {
            ObjectNode auth = objectMapper.createObjectNode();
            auth.put("deviceToken", properties.getExplicitDeviceToken());
            return new ConnectAuth(auth, properties.getExplicitDeviceToken(), DEFAULT_SCOPES);
        }

        if (properties.isPreferStoredDeviceToken() && storedDeviceToken != null && !storedDeviceToken.deviceToken().isBlank()) {
            ObjectNode auth = objectMapper.createObjectNode();
            auth.put("deviceToken", storedDeviceToken.deviceToken());
            List<String> scopes = storedDeviceToken.scopes() == null || storedDeviceToken.scopes().isEmpty()
                    ? DEFAULT_SCOPES
                    : storedDeviceToken.scopes();
            return new ConnectAuth(auth, storedDeviceToken.deviceToken(), scopes);
        }

        if (properties.getGatewayToken() != null && !properties.getGatewayToken().isBlank()) {
            ObjectNode auth = objectMapper.createObjectNode();
            auth.put("token", properties.getGatewayToken());
            return new ConnectAuth(auth, properties.getGatewayToken(), DEFAULT_SCOPES);
        }

        if (storedDeviceToken != null && !storedDeviceToken.deviceToken().isBlank()) {
            ObjectNode auth = objectMapper.createObjectNode();
            auth.put("deviceToken", storedDeviceToken.deviceToken());
            List<String> scopes = storedDeviceToken.scopes() == null || storedDeviceToken.scopes().isEmpty()
                    ? DEFAULT_SCOPES
                    : storedDeviceToken.scopes();
            return new ConnectAuth(auth, storedDeviceToken.deviceToken(), scopes);
        }

        throw new IllegalStateException("Missing OpenClaw auth. Configure OPENCLAW_GATEWAY_TOKEN or reuse an approved device token.");
    }

    private record ConnectAuth(
            ObjectNode authNode,
            String tokenForSignature,
            List<String> scopes
    ) {
    }
}
