import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth-store'

type Mode = 'signIn' | 'signUp'

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const redirect = useMemo(() => {
    const value = searchParams.get('redirect')
    return value && value.startsWith('/') ? value : '/'
  }, [searchParams])

  const user = useAuthStore((s) => s.user)
  const isLoading = useAuthStore((s) => s.isLoading)
  const error = useAuthStore((s) => s.error)
  const signInWithPassword = useAuthStore((s) => s.signInWithPassword)
  const signUpWithPassword = useAuthStore((s) => s.signUpWithPassword)

  const [mode, setMode] = useState<Mode>('signIn')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (user) navigate(redirect, { replace: true })
  }, [navigate, redirect, user])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError(null)

    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      setFormError('请输入邮箱')
      return
    }

    if (!password) {
      setFormError('请输入密码')
      return
    }

    try {
      if (mode === 'signIn') {
        await signInWithPassword({ email: trimmedEmail, password })
      } else {
        await signUpWithPassword({ email: trimmedEmail, password })
      }

      navigate(redirect, { replace: true })
    } catch {
      // 错误信息由 store 统一管理
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="text-2xl font-semibold tracking-tight">DeepResearch Pro</div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{mode === 'signIn' ? '登录' : '注册'}</CardTitle>
            <CardDescription>
              {mode === 'signIn'
                ? '使用邮箱与密码登录到你的账户'
                : '创建新账户（可能需要邮箱验证）'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <div className="text-sm font-medium">邮箱</div>
              <Input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">密码</div>
              <Input
                type="password"
                autoComplete={mode === 'signIn' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {(formError || error) && (
              <div className="text-sm text-destructive">{formError ?? error}</div>
            )}

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === 'signIn' ? '登录' : '注册'}
            </Button>

            <div className="text-sm text-muted-foreground">
              {mode === 'signIn' ? '还没有账户？' : '已经有账户？'}{' '}
              <button
                type="button"
                className="text-foreground underline underline-offset-4"
                onClick={() => {
                  setFormError(null)
                  setMode((m) => (m === 'signIn' ? 'signUp' : 'signIn'))
                }}
              >
                {mode === 'signIn' ? '注册' : '登录'}
              </button>
            </div>
          </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
