package com.reportclaw.openclawchat.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.reportclaw.openclawchat.api.dto.*;
import com.reportclaw.openclawchat.config.RagFlowProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.http.codec.multipart.FilePart;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class RagFlowService {

    private static final Logger log = LoggerFactory.getLogger(RagFlowService.class);
    private static final Map<String, String> CATEGORY_DATASET_NAMES = new LinkedHashMap<>();

    static {
        CATEGORY_DATASET_NAMES.put("政策法规", "reportclaw_policy");
        CATEGORY_DATASET_NAMES.put("行业报告", "reportclaw_industry");
        CATEGORY_DATASET_NAMES.put("历史报告", "reportclaw_history");
        CATEGORY_DATASET_NAMES.put("媒体资讯", "reportclaw_media");
    }

    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    private final String embeddingModel;
    private final Map<String, String> categoryToDatasetId = new LinkedHashMap<>();
    private final Map<String, ChunkResult> chunkCache = new java.util.concurrent.ConcurrentHashMap<>();

    public RagFlowService(RagFlowProperties props, ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.embeddingModel = props.getEmbeddingModel();
        this.webClient = WebClient.builder()
                .baseUrl(props.getBaseUrl())
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + props.getApiKey())
                .build();
    }

    @PostConstruct
    void init() {
        listDatasets()
                .doOnNext(ds -> log.info("Loaded {} datasets on startup", ds.size()))
                .doOnError(e -> log.warn("Failed to load datasets on startup: {}", e.getMessage()))
                .subscribe();
    }

    public Mono<List<DatasetInfo>> listDatasets() {
        return webClient.get()
                .uri("/api/v1/datasets")
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(root -> {
                    List<DatasetInfo> result = new ArrayList<>();
                    JsonNode data = root.path("data");
                    if (data.isArray()) {
                        for (JsonNode ds : data) {
                            String id = ds.path("id").asText();
                            String name = ds.path("name").asText();
                            String category = datasetNameToCategory(name);
                            if (category != null) {
                                result.add(new DatasetInfo(id, name, category));
                                categoryToDatasetId.put(category, id);
                            }
                        }
                    }
                    return result;
                });
    }

    public Mono<Void> ensureDatasets() {
        return listDatasets().flatMap(existing -> {
            List<String> existingNames = existing.stream().map(DatasetInfo::name).toList();
            List<Mono<Void>> creates = new ArrayList<>();
            for (var entry : CATEGORY_DATASET_NAMES.entrySet()) {
                if (!existingNames.contains(entry.getValue())) {
                    creates.add(createDataset(entry.getValue(), entry.getKey()));
                }
            }
            if (creates.isEmpty()) {
                return Mono.empty();
            }
            return Flux.merge(creates).then();
        });
    }

    private Mono<Void> createDataset(String name, String category) {
        ObjectNode body = objectMapper.createObjectNode();
        body.put("name", name);
        body.put("description", "ReportClaw KB - " + name);
        body.put("chunk_method", "naive");
        if (embeddingModel != null && !embeddingModel.isEmpty()) {
            body.put("embedding_model", embeddingModel);
        }

        return webClient.post()
                .uri("/api/v1/datasets")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .doOnNext(resp -> {
                    int code = resp.path("code").asInt(-1);
                    if (code != 0) {
                        log.error("Failed to create dataset '{}': {}", name, resp);
                        return;
                    }
                    String id = resp.path("data").path("id").asText("");
                    if (!id.isEmpty()) {
                        categoryToDatasetId.put(category, id);
                        log.info("Created dataset '{}' (category={}) with id={}", name, category, id);
                    }
                })
                .doOnError(e -> log.error("Error creating dataset '{}': {}", name, e.getMessage()))
                .then();
    }

    public Mono<UploadResult> uploadDocument(String category, FilePart file) {
        String datasetId = categoryToDatasetId.get(category);
        if (datasetId == null) {
            return Mono.error(new IllegalArgumentException("Unknown category: " + category));
        }

        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.asyncPart("file", file.content(), DataBuffer.class)
                .filename(file.filename());

        return webClient.post()
                .uri("/api/v1/datasets/{datasetId}/documents", datasetId)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(builder.build()))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .flatMap(resp -> {
                    JsonNode data = resp.path("data");
                    String docId;
                    if (data.isArray() && !data.isEmpty()) {
                        docId = data.get(0).path("id").asText("");
                    } else {
                        docId = data.path("id").asText("");
                    }
                    if (docId.isEmpty()) {
                        return Mono.error(new RuntimeException("Upload failed: " + resp));
                    }
                    return triggerParse(datasetId, docId)
                            .thenReturn(new UploadResult(docId, file.filename(), datasetId, "parsing"));
                });
    }

    private Mono<Void> triggerParse(String datasetId, String documentId) {
        ObjectNode body = objectMapper.createObjectNode();
        ArrayNode docIds = body.putArray("document_ids");
        docIds.add(documentId);

        return webClient.post()
                .uri("/api/v1/datasets/{datasetId}/chunks", datasetId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .doOnNext(resp -> log.info("Parse triggered for doc={} in dataset={}", documentId, datasetId))
                .then();
    }

    public Mono<List<DocumentInfo>> listDocuments(String category) {
        String datasetId = categoryToDatasetId.get(category);
        if (datasetId == null) {
            return Mono.just(List.of());
        }

        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/datasets/{datasetId}/documents")
                        .queryParam("page", 1)
                        .queryParam("page_size", 100)
                        .build(datasetId))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(resp -> {
                    List<DocumentInfo> docs = new ArrayList<>();
                    JsonNode data = resp.path("data");
                    JsonNode docArray = data.isArray() ? data : data.path("docs");
                    if (docArray.isArray()) {
                        for (JsonNode doc : docArray) {
                            docs.add(new DocumentInfo(
                                    doc.path("id").asText(),
                                    doc.path("name").asText(doc.path("display_name").asText("")),
                                    category,
                                    datasetId,
                                    doc.path("size").asLong(0),
                                    mapStatus(doc.path("status").asText("0"), doc.path("run").asText("")),
                                    doc.path("chunk_count").asInt(0),
                                    doc.path("token_count").asLong(0),
                                    doc.path("create_time").asText("")));
                        }
                    }
                    return docs;
                });
    }

    public Mono<Void> deleteDocument(String category, String documentId) {
        String datasetId = categoryToDatasetId.get(category);
        if (datasetId == null) {
            return Mono.error(new IllegalArgumentException("Unknown category: " + category));
        }

        return webClient.delete()
                .uri("/api/v1/datasets/{datasetId}/documents/{documentId}", datasetId, documentId)
                .retrieve()
                .bodyToMono(Void.class);
    }

    public String getDatasetId(String category) {
        return categoryToDatasetId.get(category);
    }

    public List<String> getAllDatasetIds() {
        return new ArrayList<>(categoryToDatasetId.values());
    }

    private String datasetNameToCategory(String name) {
        for (var entry : CATEGORY_DATASET_NAMES.entrySet()) {
            if (entry.getValue().equals(name)) {
                return entry.getKey();
            }
        }
        return null;
    }

    public Mono<RetrievalResponse> retrieveChunks(RetrievalRequest request) {
        List<String> datasetIds = new ArrayList<>();
        for (String category : request.categories()) {
            String dsId = categoryToDatasetId.get(category);
            if (dsId != null) datasetIds.add(dsId);
        }
        if (datasetIds.isEmpty()) {
            datasetIds.addAll(categoryToDatasetId.values());
        }

        ObjectNode body = objectMapper.createObjectNode();
        body.put("question", request.question());
        ArrayNode dsIds = body.putArray("dataset_ids");
        datasetIds.forEach(dsIds::add);
        body.put("top_k", request.topK());
        body.put("similarity_threshold", 0.1);
        if (request.docIds() != null && !request.docIds().isEmpty()) {
            ArrayNode docIds = body.putArray("document_ids");
            request.docIds().forEach(docIds::add);
        }

        log.info("Retrieving chunks: question={}, dataset_ids={}", request.question(), datasetIds);
        return webClient.post()
                .uri("/api/v1/retrieval")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .onStatus(status -> status.is4xxClientError() || status.is5xxServerError(),
                        resp -> resp.bodyToMono(String.class)
                                .doOnNext(b -> log.error("RAGFlow retrieval error HTTP {}: {}", resp.statusCode(), b))
                                .thenReturn(new RuntimeException("RAGFlow retrieval HTTP error: " + resp.statusCode())))
                .bodyToMono(JsonNode.class)
                .doOnNext(resp -> {
                    int code = resp.path("code").asInt(0);
                    if (code != 0) log.warn("RAGFlow retrieval code={}: {}", code, resp.path("message").asText());
                })
                .map(resp -> {
                    List<ChunkResult> chunks = new ArrayList<>();
                    JsonNode data = resp.path("data");
                    JsonNode chunkArray = data.path("chunks");
                    if (!chunkArray.isArray()) chunkArray = data;
                    if (chunkArray.isArray()) {
                        for (JsonNode c : chunkArray) {
                            chunks.add(new ChunkResult(
                                    c.path("id").asText(c.path("chunk_id").asText("")),
                                    c.path("document_keyword").asText(c.path("document_name").asText(c.path("doc_name").asText(""))),
                                    c.path("content").asText(c.path("content_with_weight").asText("")),
                                    c.path("similarity").asDouble(c.path("score").asDouble(0)),
                                    c.path("dataset_id").asText(""),
                                    c.path("document_id").asText(c.path("doc_id").asText(""))));
                        }
                    }
                    chunks.forEach(c -> chunkCache.put(c.chunkId(), c));
                    if (chunkCache.size() > 500) {
                        chunkCache.keySet().stream().findFirst().ifPresent(chunkCache::remove);
                    }
                    return new RetrievalResponse(chunks, chunks.size());
                })
                .onErrorResume(ex -> {
                    log.error("retrieveChunks failed (datasets={}): {}", datasetIds, ex.getMessage());
                    return Mono.just(new RetrievalResponse(List.of(), 0));
                });
    }

    public java.util.Optional<ChunkResult> lookupChunkById(String chunkId) {
        return java.util.Optional.ofNullable(chunkCache.get(chunkId));
    }

    public Mono<ChunkResult> getChunk(String datasetId, String documentId, String chunkId) {
        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/datasets/{datasetId}/documents/{docId}/chunks")
                        .queryParam("page", 1)
                        .queryParam("page_size", 100)
                        .build(datasetId, documentId))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(resp -> {
                    JsonNode data = resp.path("data");
                    JsonNode chunkArray = data.path("chunks");
                    if (!chunkArray.isArray()) chunkArray = data;
                    if (chunkArray.isArray()) {
                        for (JsonNode c : chunkArray) {
                            String id = c.path("id").asText(c.path("chunk_id").asText(""));
                            if (chunkId.equals(id)) {
                                return new ChunkResult(
                                        id,
                                        c.path("document_name").asText(""),
                                        c.path("content").asText(c.path("content_with_weight").asText("")),
                                        c.path("score").asDouble(0),
                                        datasetId,
                                        documentId);
                            }
                        }
                    }
                    return new ChunkResult(chunkId, "", "", 0, datasetId, documentId);
                });
    }

    private String mapStatus(String status, String run) {
        if ("FAIL".equalsIgnoreCase(run)) return "error";
        if ("RUNNING".equalsIgnoreCase(run)) return "parsing";
        if ("2".equals(status) || "DONE".equalsIgnoreCase(run)) return "ready";
        if ("1".equals(status)) return "parsing";
        if ("-1".equals(status) || "3".equals(status)) return "error";
        return "uploading";
    }
}
