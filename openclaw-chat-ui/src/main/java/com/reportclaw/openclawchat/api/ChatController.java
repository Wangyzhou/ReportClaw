package com.reportclaw.openclawchat.api;

import com.reportclaw.openclawchat.api.dto.ChatRequest;
import com.reportclaw.openclawchat.api.dto.SessionSummary;
import com.reportclaw.openclawchat.api.dto.StreamEvent;
import com.reportclaw.openclawchat.service.OpenClawGatewayService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api")
public class ChatController {

    private final OpenClawGatewayService gatewayService;

    public ChatController(OpenClawGatewayService gatewayService) {
        this.gatewayService = gatewayService;
    }

    @GetMapping("/sessions")
    public Mono<List<SessionSummary>> sessions() {
        return gatewayService.listSessions();
    }

    @PostMapping(value = "/chat/stream", produces = MediaType.APPLICATION_NDJSON_VALUE)
    public Flux<StreamEvent> stream(@Valid @RequestBody ChatRequest request) {
        return gatewayService.streamChat(request);
    }
}
