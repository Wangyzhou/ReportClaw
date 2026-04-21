package com.reportclaw.openclawchat.service;

import com.reportclaw.openclawchat.api.dto.CreateTaskRequest;
import com.reportclaw.openclawchat.api.dto.TaskNode;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class TaskProgressService {

    private final ConcurrentHashMap<String, TaskNode> store = new ConcurrentHashMap<>();

    public TaskNode create(CreateTaskRequest req) {
        long now = System.currentTimeMillis();
        TaskNode node = new TaskNode(req.nodeId(), req.agentId(), req.taskName(), req.taskStatus(), req.parentId(), now, now);
        store.put(req.nodeId(), node);
        return node;
    }

    public Optional<TaskNode> updateStatus(String nodeId, String agentId, String taskStatus) {
        TaskNode existing = store.get(nodeId);
        if (existing == null) return Optional.empty();
        long now = System.currentTimeMillis();
        String resolvedAgent = (agentId != null && !agentId.isBlank()) ? agentId : existing.agentId();
        TaskNode updated = new TaskNode(nodeId, resolvedAgent, existing.taskName(), taskStatus, existing.parentId(), existing.createdAt(), now);
        store.put(nodeId, updated);
        return Optional.of(updated);
    }

    public List<TaskNode> listAll() {
        return store.values().stream()
                .sorted(Comparator.comparingLong(TaskNode::createdAt))
                .toList();
    }

    public void clear() {
        store.clear();
    }
}
