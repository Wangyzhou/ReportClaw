package com.reportclaw.openclawchat.api.dto;

import jakarta.validation.constraints.NotBlank;

public record ChatRequest(
        @NotBlank(message = "message is required")
        String message,
        String sessionKey
) {
}
