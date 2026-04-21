package com.reportclaw.openclawchat.api;

import com.reportclaw.openclawchat.api.dto.*;
import com.reportclaw.openclawchat.service.RagFlowService;
import org.springframework.http.MediaType;
import org.springframework.http.codec.multipart.FilePart;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/kb")
public class KnowledgeBaseController {

    private final RagFlowService ragFlowService;

    public KnowledgeBaseController(RagFlowService ragFlowService) {
        this.ragFlowService = ragFlowService;
    }

    @GetMapping("/datasets")
    public Mono<List<DatasetInfo>> listDatasets() {
        return ragFlowService.listDatasets();
    }

    @PostMapping("/datasets/init")
    public Mono<Map<String, String>> initDatasets() {
        return ragFlowService.ensureDatasets()
                .then(ragFlowService.listDatasets())
                .map(datasets -> {
                    Map<String, String> result = new java.util.LinkedHashMap<>();
                    for (DatasetInfo ds : datasets) {
                        result.put(ds.category(), ds.id());
                    }
                    return result;
                });
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<UploadResult> uploadDocument(
            @RequestParam("category") String category,
            @RequestPart("file") FilePart file) {
        return ragFlowService.uploadDocument(category, file);
    }

    @GetMapping("/documents")
    public Mono<List<DocumentInfo>> listDocuments(@RequestParam("category") String category) {
        return ragFlowService.listDocuments(category);
    }

    @DeleteMapping("/documents/{documentId}")
    public Mono<Void> deleteDocument(
            @RequestParam("category") String category,
            @PathVariable("documentId") String documentId) {
        return ragFlowService.deleteDocument(category, documentId);
    }

    @PostMapping("/retrieve")
    public Mono<RetrievalResponse> retrieve(@RequestBody RetrievalRequest request) {
        return ragFlowService.retrieveChunks(request);
    }

    @GetMapping("/chunks/{datasetId}/{docId}/{chunkId}")
    public Mono<ChunkResult> getChunk(
            @PathVariable("datasetId") String datasetId,
            @PathVariable("docId") String docId,
            @PathVariable("chunkId") String chunkId) {
        return ragFlowService.getChunk(datasetId, docId, chunkId);
    }
}
