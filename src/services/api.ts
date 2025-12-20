/**
 * API服务层
 */
const API_BASE_URL = ''

/**
 * HTTP请求封装
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const defaultHeaders = {
    'Content-Type': 'application/json',
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `请求失败: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('API请求错误:', error)
    throw error
  }
}

// 研究任务接口

export type TaskStatus =
  | 'pending'
  | 'planning'
  | 'searching'
  | 'curating'
  | 'analyzing'
  | 'writing'
  | 'citing'
  | 'reviewing'
  | 'completed'
  | 'failed'
  | 'paused'

export interface ResearchTask {
  id: number
  query: string
  status: TaskStatus
  progress: number
  config?: Record<string, any> | null
  report_content?: string | null
  summary?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
}

export interface ResearchTaskCreate {
  query: string
  config?: Record<string, any>
}

export interface ResearchTaskListResponse {
  total: number
  items: ResearchTask[]
}

export interface PlanItem {
  id: number
  title: string
  description?: string | null
  status: string
  order: number
  parent_id: number | null
  children?: PlanItem[] | null
}

export interface Source {
  id: number
  title: string
  url?: string | null
  source_type: string
  content?: string | null
  confidence: string
  relevance_score: number
  created_at: string
}

export interface AgentLog {
  id: number
  agent_type: string
  action: string
  content: string
  status: string
  tokens_used: number
  duration_ms: number
  created_at: string
}

export interface Chart {
  id: number
  chart_type: string
  title: string
  description?: string | null
  data: any
  config?: any | null
  section: string
  order: number
  created_by_agent: string
  created_at: string
}

export interface ResearchTaskDetail extends ResearchTask {
  plan_items: PlanItem[]
  sources: Source[]
  recent_logs: AgentLog[]
  charts: Chart[]
}

export interface AgentActivityMetrics {
  tokensUsed?: number
  apiCalls?: number
  duration?: string
  [key: string]: any
}

export interface AgentActivity {
  agent_type: string
  status: string
  current_task: string | null
  progress: number
  metrics?: AgentActivityMetrics
  sub_tasks?: any[]
}

export interface AgentActivityResponse {
  task_id: number
  agents: AgentActivity[]
  overall_progress: number
}

export type ReportQARole = 'user' | 'assistant'

export interface ReportQAHistoryItem {
  role: ReportQARole
  content: string
}

export interface ReportQAResponse {
  answer: string
}

/** 获取研究任务列表 */
export async function getResearchTasks(params?: {
  skip?: number
  limit?: number
  status?: string
}): Promise<ResearchTaskListResponse> {
  const queryParams = new URLSearchParams()
  if (params?.skip !== undefined) queryParams.set('skip', String(params.skip))
  if (params?.limit !== undefined) queryParams.set('limit', String(params.limit))
  if (params?.status) queryParams.set('status', params.status)

  const endpoint = `/api/research/tasks${queryParams.toString() ? `?${queryParams}` : ''}`
  return request<ResearchTaskListResponse>(endpoint)
}

/** 创建研究任务 */
export async function createResearchTask(
  data: ResearchTaskCreate
): Promise<ResearchTask> {
  return request<ResearchTask>('/api/research/tasks', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/** 获取研究任务详情 */
export async function getResearchTask(taskId: number): Promise<ResearchTaskDetail> {
  return request<ResearchTaskDetail>(`/api/research/tasks/${taskId}`)
}

/** 暂停研究任务 */
export async function pauseResearchTask(taskId: number): Promise<void> {
  await request(`/api/research/tasks/${taskId}/pause`, {
    method: 'POST',
  })
}

/** 继续研究任务 */
export async function resumeResearchTask(taskId: number): Promise<void> {
  await request(`/api/research/tasks/${taskId}/resume`, {
    method: 'POST',
  })
}

/** 删除研究任务 */
export async function deleteResearchTask(taskId: number): Promise<void> {
  await request(`/api/research/tasks/${taskId}`, {
    method: 'DELETE',
    body: undefined,
  })
}

export async function getAgentActivity(taskId: number): Promise<AgentActivityResponse> {
  return request<AgentActivityResponse>(`/api/research/tasks/${taskId}/agents`)
}

export async function askReportQuestion(
  taskId: number,
  question: string,
  history?: ReportQAHistoryItem[]
): Promise<ReportQAResponse> {
  return request<ReportQAResponse>(`/api/research/tasks/${taskId}/qa`, {
    method: 'POST',
    body: JSON.stringify({ question, history }),
  })
}

// LLM配置

export type LLMProviderId =
  | 'openai'
  | 'anthropic'
  | 'google'
  | 'qwen'
  | 'wenxin'
  | 'zhipu'
  | 'moonshot'
  | 'spark'
  | 'yi'
  | 'deepseek'
  | 'baichuan'
  | 'minimax'
  | 'custom'

export interface LLMProviderInfo {
  id: LLMProviderId
  name: string
  base_url: string
  default_model: string
  models: string[]
  note?: string
}

export interface LLMConfigPublic {
  provider: LLMProviderId
  base_url?: string | null
  model?: string | null
  api_key_set: boolean
  api_key_last4?: string | null
}

export interface LLMConfigUpdate {
  provider: LLMProviderId
  api_key?: string
  base_url?: string
  model?: string
}

export async function getLLMProviders(): Promise<LLMProviderInfo[]> {
  return request<LLMProviderInfo[]>('/api/settings/llm/providers')
}

export async function getLLMConfig(): Promise<LLMConfigPublic> {
  return request<LLMConfigPublic>('/api/settings/llm')
}

export async function updateLLMConfig(data: LLMConfigUpdate): Promise<LLMConfigPublic> {
  return request<LLMConfigPublic>('/api/settings/llm', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

/** 导出报告 */
export async function exportReport(
  taskId: number,
  format: 'pdf' | 'word' | 'markdown',
  includeCharts: boolean = true
): Promise<Blob> {
  const queryParams = new URLSearchParams({
    include_charts: String(includeCharts)
  })

  const url = `/api/export/tasks/${taskId}/export/${format}?${queryParams}`

  const response = await fetch(url)
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `导出失败: ${response.status}`)
  }

  return response.blob()
}

// WebSocket连接

/** 创建WebSocket连接 */
export function createWebSocket(taskId: number): WebSocket {
	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'

	if (import.meta.env.DEV) {
		return new WebSocket(`${protocol}//127.0.0.1:8000/api/ws/research/${taskId}`)
	}

	const host = window.location.host
	return new WebSocket(`${protocol}//${host}/api/ws/research/${taskId}`)
}
