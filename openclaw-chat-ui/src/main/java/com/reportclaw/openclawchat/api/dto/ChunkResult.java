package com.reportclaw.openclawchat.api.dto;

public record ChunkResult(
        String chunkId,
        String documentName,
        String content,
        double score,
        String datasetId,
        String documentId
) {}
