package com.reportclaw.openclawchat.api.dto;

public record DocumentInfo(
        String id,
        String name,
        String category,
        String datasetId,
        long size,
        String status,
        int chunkCount,
        long tokenCount,
        String createdAt) {}
