import { useEffect, useMemo, useState } from 'react'
import { Loader2, LogOut, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth-store'
import {
  getLLMConfig,
  getLLMProviders,
  updateLLMConfig,
  type LLMConfigPublic,
  type LLMProviderId,
  type LLMProviderInfo,
} from '@/services/api'

export default function AccountPage() {
  const user = useAuthStore((s) => s.user)
  const isLoading = useAuthStore((s) => s.isLoading)
  const error = useAuthStore((s) => s.error)
  const signOut = useAuthStore((s) => s.signOut)

  const [providers, setProviders] = useState<LLMProviderInfo[]>([])
  const [remoteConfig, setRemoteConfig] = useState<LLMConfigPublic | null>(null)
  const [configLoading, setConfigLoading] = useState(true)
  const [configSaving, setConfigSaving] = useState(false)
  const [configError, setConfigError] = useState<string | null>(null)
  const [configSavedAt, setConfigSavedAt] = useState<string | null>(null)

  const [provider, setProvider] = useState<LLMProviderId>('openai')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')

  const providerInfo = useMemo(
    () => providers.find((p) => p.id === provider) ?? null,
    [providers, provider]
  )

  useEffect(() => {
    let cancelled = false

    async function load() {
      setConfigLoading(true)
      setConfigError(null)
      try {
        const [providersData, configData] = await Promise.all([
          getLLMProviders(),
          getLLMConfig(),
        ])

        if (cancelled) return

        setProviders(providersData)
        setRemoteConfig(configData)
        setProvider(configData.provider)
        setBaseUrl(configData.base_url ?? '')
        setModel(configData.model ?? '')
      } catch (e) {
        const message = e instanceof Error ? e.message : '加载 LLM 配置失败'
        if (!cancelled) setConfigError(message)
      } finally {
        if (!cancelled) setConfigLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  async function saveConfig() {
    setConfigSaving(true)
    setConfigError(null)
    setConfigSavedAt(null)
    try {
      const updated = await updateLLMConfig({
        provider,
        base_url: baseUrl,
        model,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
      })
      setRemoteConfig(updated)
      setApiKey('')
      setConfigSavedAt(new Date().toLocaleString())
    } catch (e) {
      const message = e instanceof Error ? e.message : '保存 LLM 配置失败'
      setConfigError(message)
    } finally {
      setConfigSaving(false)
    }
  }

  return (
    <div className="container py-8">
      <div className="max-w-2xl">
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>账户</CardTitle>
            <CardDescription>查看账号信息并管理登录状态</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">邮箱</div>
              <div className="font-medium break-all">{user?.email ?? '-'}</div>
            </div>

            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">用户 ID</div>
              <div className="font-mono text-sm break-all">{user?.id ?? '-'}</div>
            </div>

            {error && <div className="text-sm text-destructive">{error}</div>}

            <div>
              <Button
                variant="destructive"
                onClick={() => void signOut()}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <LogOut className="mr-2 h-4 w-4" />
                )}
                退出登录
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>LLM 配置</CardTitle>
            <CardDescription>配置大模型 API，用于研究任务的推理与生成</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {configLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在加载配置…
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <div className="text-sm font-medium">提供商</div>
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={provider}
                    onChange={(e) => {
                      const nextProvider = e.target.value as LLMProviderId
                      setProvider(nextProvider)
                      const p = providers.find((x) => x.id === nextProvider)
                      if (p) {
                        if (!baseUrl.trim()) setBaseUrl(p.base_url)
                        if (!model.trim()) setModel(p.default_model)
                      }
                    }}
                  >
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  {providerInfo?.note ? (
                    <div className="text-xs text-muted-foreground">{providerInfo.note}</div>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">Base URL</div>
                  <Input
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder={providerInfo?.base_url || 'https://.../v1'}
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">模型</div>
                  <Input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder={providerInfo?.default_model || 'gpt-4o-mini'}
                    list="llm-models"
                  />
                  <datalist id="llm-models">
                    {providerInfo?.models?.map((m) => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">API Key</div>
                    <div className="text-xs text-muted-foreground">
                      {remoteConfig?.api_key_set
                        ? `已设置${remoteConfig.api_key_last4 ? `（****${remoteConfig.api_key_last4}）` : ''}`
                        : '未设置'}
                    </div>
                  </div>
                  <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="输入后保存，将写入本地研究服务配置"
                    autoComplete="off"
                  />
                </div>

                {configError && <div className="text-sm text-destructive">{configError}</div>}
                {configSavedAt && (
                  <div className="text-sm text-muted-foreground">已保存：{configSavedAt}</div>
                )}

                <div>
                  <Button onClick={() => void saveConfig()} disabled={configSaving}>
                    {configSaving ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    保存配置
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
