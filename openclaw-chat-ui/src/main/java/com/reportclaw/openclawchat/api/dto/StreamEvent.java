package com.reportclaw.openclawchat.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record StreamEvent(
        String type,
        String runId,
        String sessionKey,
        String stream,
        String state,
        String kind,
        String phase,
        String name,
        String status,
        String title,
        String itemId,
        String toolCallId,
        String text,
        String delta,
        Instant timestamp,
        JsonNode raw
) {
}
