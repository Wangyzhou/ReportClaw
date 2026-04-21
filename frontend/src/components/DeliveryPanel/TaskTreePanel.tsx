import { useState, useEffect, useRef } from 'react'
import { fetchTasks } from '../../services/api'
import type { TaskNode } from '../../types'
import styles from './TaskTreePanel.module.css'

const STATUS_ICON: Record<string, string> = {
  pending: '⏳',
  running: '🔄',
  completed: '✅',
  failed: '❌',
}

function buildTree(nodes: TaskNode[]): { root: TaskNode; children: TaskNode[] }[] {
  const childMap = new Map<string, TaskNode[]>()
  const roots: TaskNode[] = []

  for (const node of nodes) {
    if (node.parentId) {
      const siblings = childMap.get(node.parentId) ?? []
      siblings.push(node)
      childMap.set(node.parentId, siblings)
    } else {
      roots.push(node)
    }
  }

  return roots.map(root => ({ root, children: childMap.get(root.nodeId) ?? [] }))
}

export function TaskTreePanel() {
  const [nodes, setNodes] = useState<TaskNode[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval>>()

  const load = async () => {
    try {
      const data = await fetchTasks()
      setNodes(data)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    const hasActive = nodes.some(n => n.taskStatus === 'pending' || n.taskStatus === 'running')
    if (hasActive) {
      timerRef.current = setInterval(load, 2000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [nodes])

  const tree = buildTree(nodes)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>Agent 任务树</span>
        {nodes.some(n => n.taskStatus === 'running') && (
          <span className={styles.activePulse} />
        )}
      </div>

      {tree.length === 0 ? (
        <p className={styles.empty}>等待任务开始...</p>
      ) : (
        <ul className={styles.tree}>
          {tree.map(({ root, children }) => (
            <li key={root.nodeId} className={styles.rootNode}>
              <div className={styles.nodeRow}>
                <span className={styles.icon}>{STATUS_ICON[root.taskStatus] ?? '⏳'}</span>
                <span className={styles.name}>{root.taskName}</span>
                <span className={styles.nodeId}>{root.nodeId}</span>
              </div>
              {children.length > 0 && (
                <ul className={styles.children}>
                  {children.map(child => (
                    <li key={child.nodeId} className={styles.childNode}>
                      <div className={styles.nodeRow}>
                        <span className={styles.icon}>{STATUS_ICON[child.taskStatus] ?? '⏳'}</span>
                        <span className={styles.name}>{child.taskName}</span>
                        <span className={styles.nodeId}>{child.nodeId}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
