package com.reportclaw.openclawchat.api.dto;

public record UpdateTaskStatusRequest(
        String agentId,
        String taskStatus
) {}
