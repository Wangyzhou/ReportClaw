import { useReducer, useCallback } from 'react'
import type { ChatMessage, InlineActivity, ConnectionStatus, Session, StreamEvent, ChatPayload } from '../types'

interface ChatState {
  messages: ChatMessage[]
  activities: InlineActivity[]
  connection: ConnectionStatus
  connectionLabel: string
  connectionBadge: string
  currentRunId: string | null
  currentAssistantId: string | null
  currentAssistantText: string
  sessions: Session[]
  messageCounter: number
}

type ChatAction =
  | { type: 'SET_CONNECTION'; status: ConnectionStatus; label: string; badge: string }
  | { type: 'SET_SESSIONS'; sessions: Session[] }
  | { type: 'ADD_MESSAGE'; message: ChatMessage }
  | { type: 'UPDATE_ASSISTANT'; delta: string }
  | { type: 'UPSERT_ACTIVITY'; activity: InlineActivity }
  | { type: 'SET_RUN_ID'; runId: string }
  | { type: 'RESET_STREAM' }

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SET_CONNECTION':
      return { ...state, connection: action.status, connectionLabel: action.label, connectionBadge: action.badge }

    case 'SET_SESSIONS':
      return { ...state, sessions: action.sessions }

    case 'ADD_MESSAGE': {
      return {
        ...state,
        messages: [...state.messages, action.message],
        messageCounter: state.messageCounter + 1,
      }
    }

    case 'UPDATE_ASSISTANT': {
      const newText = state.currentAssistantText + action.delta
      if (!state.currentAssistantId) {
        const id = `msg-${state.messageCounter + 1}`
        const msg: ChatMessage = { id, role: 'assistant', text: newText, timestamp: new Date() }
        return {
          ...state,
          currentAssistantId: id,
          currentAssistantText: newText,
          messages: [...state.messages, msg],
          messageCounter: state.messageCounter + 1,
        }
      }
      return {
        ...state,
        currentAssistantText: newText,
        messages: state.messages.map(m =>
          m.id === state.currentAssistantId ? { ...m, text: newText } : m
        ),
      }
    }

    case 'UPSERT_ACTIVITY': {
      const idx = state.activities.findIndex(a => a.key === action.activity.key)
      if (idx >= 0) {
        const updated = [...state.activities]
        const existing = updated[idx]
        const merged = { ...existing, ...action.activity }
        if (action.activity.type === 'command-output') {
          merged.text = [existing.text, action.activity.text].filter(Boolean).join('\n')
        }
        updated[idx] = merged
        return { ...state, activities: updated }
      }
      return { ...state, activities: [...state.activities, action.activity] }
    }

    case 'SET_RUN_ID':
      return { ...state, currentRunId: action.runId }

    case 'RESET_STREAM':
      return {
        ...state,
        activities: [],
        currentRunId: null,
        currentAssistantId: null,
        currentAssistantText: '',
      }

    default:
      return state
  }
}

const initialState: ChatState = {
  messages: [],
  activities: [],
  connection: 'idle',
  connectionLabel: '待命',
  connectionBadge: '未连接',
  currentRunId: null,
  currentAssistantId: null,
  currentAssistantText: '',
  sessions: [],
  messageCounter: 0,
}

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialState)

  const loadSessions = useCallback(async () => {
    dispatch({ type: 'SET_CONNECTION', status: 'streaming', label: '正在读取会话', badge: '加载中' })
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const res = await fetch('/api/sessions')
        if (!res.ok) throw new Error(`sessions request failed (${res.status})`)
        const sessions = await res.json()
        dispatch({ type: 'SET_SESSIONS', sessions })
        dispatch({ type: 'SET_CONNECTION', status: 'connected', label: '已连接 Gateway', badge: `${sessions.length} 个可用会话` })
        return
      } catch (err) {
        if (attempt < 3) {
          dispatch({ type: 'SET_CONNECTION', status: 'streaming', label: '尝试连接 Gateway', badge: `重试 ${attempt}/3` })
          await new Promise(r => setTimeout(r, 2000))
        } else {
          // graceful fallback: Gateway 不可达时进入演示模式（前端仍可浏览 mock 数据 + 演示报告）
          dispatch({ type: 'SET_SESSIONS', sessions: [{ key: 'demo:reportclaw', label: 'ReportClaw 演示' }] })
          dispatch({ type: 'SET_CONNECTION', status: 'connected', label: 'ReportClaw 演示模式', badge: '5 Agent 待命' })
          // 不再 surface error 提示，避免视觉干扰；调试需要时看 console
          console.warn('[useChat] sessions request failed, entering offline demo mode:', (err as Error).message)
        }
      }
    }
  }, [])

  const sendMessage = useCallback(async (payload: ChatPayload, sessionKey: string) => {
    dispatch({ type: 'RESET_STREAM' })
    dispatch({ type: 'SET_CONNECTION', status: 'streaming', label: '流式处理中', badge: '正在接收' })

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      text: payload.text,
      timestamp: new Date(),
    }
    dispatch({ type: 'ADD_MESSAGE', message: userMsg })

    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: payload.text,
        sessionKey,
        mode: payload.mode,
        mentionedDocs: payload.mentionedDocs,
      }),
    })

    if (!res.ok || !res.body) throw new Error(`chat stream failed (${res.status})`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try {
          handleStreamEvent(JSON.parse(trimmed), dispatch)
        } catch {
          // skip malformed NDJSON
        }
      }
    }

    if (buffer.trim()) {
      try {
        handleStreamEvent(JSON.parse(buffer.trim()), dispatch)
      } catch {
        // skip
      }
    }
  }, [])

  return { state, loadSessions, sendMessage, dispatch }
}

function handleStreamEvent(event: StreamEvent, dispatch: React.Dispatch<ChatAction>) {
  switch (event.type) {
    case 'connected':
      dispatch({ type: 'SET_CONNECTION', status: 'connected', label: '已连上 OpenClaw', badge: '链路在线' })
      break
    case 'run-started':
      dispatch({ type: 'SET_RUN_ID', runId: (event.runId as string) || '' })
      break
    case 'assistant-delta':
      dispatch({ type: 'UPDATE_ASSISTANT', delta: (event.delta || event.text || '') as string })
      break
    case 'activity':
    case 'command-output':
    case 'assistant-trace':
    case 'lifecycle': {
      const key = (event.itemId || event.toolCallId ||
        `${event.type}:${event.stream || ''}:${event.kind || ''}:${event.name || ''}:${event.phase || ''}:${event.title || ''}`) as string
      dispatch({ type: 'UPSERT_ACTIVITY', activity: { ...event, key } as InlineActivity })
      break
    }
    case 'done':
      dispatch({ type: 'SET_CONNECTION', status: 'connected', label: '本轮完成', badge: '已结束' })
      break
    case 'error':
      dispatch({ type: 'SET_CONNECTION', status: 'error', label: '流中断', badge: '错误' })
      dispatch({
        type: 'ADD_MESSAGE',
        message: { id: `err-${Date.now()}`, role: 'assistant', text: (event.text as string) || '请求失败', timestamp: new Date() },
      })
      break
  }
}
