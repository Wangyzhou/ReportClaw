package com.reportclaw.openclawchat.api.dto;

public record CreateTaskRequest(
        String nodeId,
        String agentId,
        String taskName,
        String taskStatus,
        String parentId
) {
    public CreateTaskRequest {
        if (taskStatus == null || taskStatus.isBlank()) taskStatus = "pending";
    }
}
