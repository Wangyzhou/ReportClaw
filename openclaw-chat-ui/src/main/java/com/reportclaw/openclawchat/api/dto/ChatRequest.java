package com.reportclaw.openclawchat.api.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.List;

public record ChatRequest(
        @NotBlank(message = "message is required")
        String message,
        String sessionKey,
        String mode,
        List<MentionedDoc> mentionedDocs
) {
    public record MentionedDoc(String id, String name, String category) {}
}
