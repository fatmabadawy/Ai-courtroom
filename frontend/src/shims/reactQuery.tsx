import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'

interface QueryOptions<T> {
  queryKey: any[]
  queryFn: () => Promise<T>
  enabled?: boolean
  refetchInterval?: number | false | ((query: any) => number | false)
  retry?: number
}

interface QueryResult<T> {
  data: T | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => Promise<void>
  state?: { data?: T }
}

const QueryCacheContext = createContext<{
  cache: React.MutableRefObject<Map<string, any>>
  invalidateQueries: (options: { queryKey: any[] }) => void
}>({
  cache: { current: new Map() },
  invalidateQueries: () => {},
})

export class QueryClient {
  defaultOptions: any
  constructor(options: any = {}) {
    this.defaultOptions = options
  }
}

export const QueryClientProvider: React.FC<{
  client: QueryClient
  children: React.ReactNode
}> = ({ children }) => {
  const cache = useRef(new Map<string, any>())
  const listeners = useRef(new Set<() => void>())

  const invalidateQueries = useCallback(({ queryKey }: { queryKey: any[] }) => {
    const keyStr = JSON.stringify(queryKey)
    for (const k of cache.current.keys()) {
      if (k.startsWith(keyStr.slice(0, -1))) {
        cache.current.delete(k)
      }
    }
    listeners.current.forEach((fn) => fn())
  }, [])

  return (
    <QueryCacheContext.Provider value={{ cache, invalidateQueries }}>
      {children}
    </QueryCacheContext.Provider>
  )
}

export function useQueryClient() {
  const ctx = useContext(QueryCacheContext)
  return {
    invalidateQueries: ctx.invalidateQueries,
  }
}

export function useQuery<T>(options: QueryOptions<T>): QueryResult<T> {
  const { queryKey, queryFn, enabled = true, refetchInterval } = options
  const key = JSON.stringify(queryKey)
  const { cache } = useContext(QueryCacheContext)

  const [data, setData] = useState<T | undefined>(() => cache.current.get(key))
  const [isLoading, setIsLoading] = useState<boolean>(!cache.current.has(key) && enabled)
  const [error, setError] = useState<Error | null>(null)

  const execute = useCallback(async () => {
    if (!enabled) return
    try {
      const res = await queryFn()
      cache.current.set(key, res)
      setData(res)
      setError(null)
    } catch (err: any) {
      setError(err)
    } finally {
      setIsLoading(false)
    }
  }, [enabled, key, queryFn])

  useEffect(() => {
    if (enabled) {
      execute()
    }
  }, [enabled, key, execute])

  // Polling refetchInterval
  useEffect(() => {
    if (!enabled) return
    const intervalMs =
      typeof refetchInterval === 'function'
        ? refetchInterval({ state: { data } })
        : refetchInterval

    if (intervalMs && typeof intervalMs === 'number') {
      const timer = setInterval(() => {
        execute()
      }, intervalMs)
      return () => clearInterval(timer)
    }
  }, [enabled, refetchInterval, data, execute])

  return {
    data,
    isLoading,
    isError: !!error,
    error,
    refetch: execute,
    state: { data },
  }
}

export function useMutation<TData, TVariables>(options: {
  mutationFn: (variables: TVariables) => Promise<TData>
  onSuccess?: (data: TData) => void
  onError?: (error: any) => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<any>(null)

  const mutateAsync = async (variables: TVariables) => {
    setLoading(true)
    setError(null)
    try {
      const res = await options.mutationFn(variables)
      options.onSuccess?.(res)
      return res
    } catch (err) {
      setError(err)
      options.onError?.(err)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return {
    mutate: mutateAsync,
    mutateAsync,
    isLoading: loading,
    error,
  }
}
