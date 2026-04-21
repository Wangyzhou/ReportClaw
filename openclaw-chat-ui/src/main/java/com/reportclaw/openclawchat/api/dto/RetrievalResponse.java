package com.reportclaw.openclawchat.api.dto;

import java.util.List;

public record RetrievalResponse(
        List<ChunkResult> chunks,
        int total
) {}
