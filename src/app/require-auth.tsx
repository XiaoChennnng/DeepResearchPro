import { useMemo, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const isLoading = useAuthStore((s) => s.isLoading)
  const initialized = useAuthStore((s) => s.initialized)

  const redirectTo = useMemo(() => {
    const path = `${location.pathname}${location.search}`
    return `/login?redirect=${encodeURIComponent(path)}`
  }, [location.pathname, location.search])

  if (!initialized || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (!user) return <Navigate to={redirectTo} replace />

  return children
}
