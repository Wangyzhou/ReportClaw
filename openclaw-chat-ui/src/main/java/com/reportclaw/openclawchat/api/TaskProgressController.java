package com.reportclaw.openclawchat.api;

import com.reportclaw.openclawchat.api.dto.CreateTaskRequest;
import com.reportclaw.openclawchat.api.dto.TaskNode;
import com.reportclaw.openclawchat.api.dto.UpdateTaskStatusRequest;
import com.reportclaw.openclawchat.service.TaskProgressService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/tasks")
public class TaskProgressController {

    private final TaskProgressService taskProgressService;

    public TaskProgressController(TaskProgressService taskProgressService) {
        this.taskProgressService = taskProgressService;
    }

    /** MCP tool: create-task */
    @PostMapping
    public TaskNode create(@RequestBody CreateTaskRequest req) {
        return taskProgressService.create(req);
    }

    /** MCP tool: update-task-status */
    @PatchMapping("/{nodeId}")
    public ResponseEntity<TaskNode> update(
            @PathVariable String nodeId,
            @RequestBody UpdateTaskStatusRequest req) {
        return taskProgressService.updateStatus(nodeId, req.agentId(), req.taskStatus())
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /** Frontend polling: list all tasks for task-tree display */
    @GetMapping
    public List<TaskNode> listAll() {
        return taskProgressService.listAll();
    }

    /** Reset task tree at session start */
    @DeleteMapping
    public ResponseEntity<Void> clear() {
        taskProgressService.clear();
        return ResponseEntity.noContent().build();
    }
}
