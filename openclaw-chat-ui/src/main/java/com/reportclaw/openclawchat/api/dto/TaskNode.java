package com.reportclaw.openclawchat.api.dto;

public record TaskNode(
        String nodeId,
        String agentId,
        String taskName,
        String taskStatus,
        String parentId,
        long createdAt,
        long updatedAt
) {}
