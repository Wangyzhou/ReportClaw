package com.reportclaw.openclawchat.api.dto;

import java.util.List;

public record RetrievalRequest(
        String question,
        List<String> categories,
        List<String> docIds,
        int topK
) {
    public RetrievalRequest {
        if (topK <= 0) topK = 5;
    }
}
