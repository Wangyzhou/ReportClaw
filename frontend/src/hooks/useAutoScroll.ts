import { useRef, useEffect, useCallback } from 'react'

export function useAutoScroll<T extends HTMLElement>(deps: unknown[]) {
  const ref = useRef<T>(null)
  const userScrolledRef = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const handleScroll = () => {
      const threshold = 60
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
      userScrolledRef.current = !atBottom
    }

    el.addEventListener('scroll', handleScroll)
    return () => el.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    if (!userScrolledRef.current && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  const resetScroll = useCallback(() => {
    userScrolledRef.current = false
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [])

  return { ref, resetScroll }
}
