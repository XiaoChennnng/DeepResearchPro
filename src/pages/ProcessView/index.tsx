import { useState, useEffect, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import {
  Play,
  Pause,
  Settings,
  X,
  CheckCircle2,
  Circle,
  Loader2,
  Globe,
  FileText,
  Brain,
  Search,
  BookOpen,
  Database,
  Sparkles,
  AlertCircle,
  Bot,
  PenTool,
  Shield,
  MessageSquare,
  Clock,
  ArrowRight,
  Timer,
  Link2,
  ChevronDown,
  ChevronRight,
  Zap
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  getResearchTask,
  getAgentActivity,
  pauseResearchTask,
  resumeResearchTask,
  createWebSocket,
  type PlanItem as ApiPlanItem,
  type Source as ApiSource,
  type AgentLog as ApiAgentLog,
  type AgentActivity as BackendAgentActivity,
  type TaskStatus,
} from '@/services/api'

// Research stages - user-friendly descriptions
const stages = [
  { id: 'planning', name: '分析问题', icon: Brain, description: '正在理解研究问题并制定计划...' },
  { id: 'searching', name: '搜索资料', icon: Search, description: '正在从多个来源搜索相关信息...' },
  { id: 'curating', name: '筛选信息', icon: Sparkles, description: '正在筛选和评估信息质量...' },
  { id: 'analyzing', name: '深度分析', icon: Database, description: '正在对数据进行深入分析...' },
  { id: 'writing', name: '撰写报告', icon: FileText, description: '正在撰写研究报告...' },
  { id: 'citing', name: '整理引用', icon: Link2, description: '正在整理参考文献和引用...' },
  { id: 'reviewing', name: '质量审核', icon: CheckCircle2, description: '正在进行报告质量审核...' },
]

// Agent types with their properties - user-friendly names
const agentTypes = {
  planner: { name: '研究规划', icon: Brain, color: 'text-purple-500', bgColor: 'bg-purple-500/10', borderColor: 'border-purple-500/30' },
  searcher: { name: '资料搜索', icon: Globe, color: 'text-blue-500', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500/30' },
  curator: { name: '信息筛选', icon: Sparkles, color: 'text-teal-500', bgColor: 'bg-teal-500/10', borderColor: 'border-teal-500/30' },
  analyzer: { name: '深度分析', icon: Database, color: 'text-green-500', bgColor: 'bg-green-500/10', borderColor: 'border-green-500/30' },
  writer: { name: '报告撰写', icon: PenTool, color: 'text-orange-500', bgColor: 'bg-orange-500/10', borderColor: 'border-orange-500/30' },
  citer: { name: '引用整理', icon: Link2, color: 'text-amber-500', bgColor: 'bg-amber-500/10', borderColor: 'border-amber-500/30' },
  reviewer: { name: '质量审核', icon: Shield, color: 'text-red-500', bgColor: 'bg-red-500/10', borderColor: 'border-red-500/30' },
}

// Sub-task type for detailed agent execution
type SubTask = {
  id: string
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startTime?: string
  endTime?: string
  result?: string
  detail?: string
}

// Agent activity with detailed execution info
type AgentActivity = {
  id: string
  agent: keyof typeof agentTypes
  status: 'pending' | 'running' | 'active' | 'idle' | 'completed' | 'failed'
  currentTask: string
  output?: string
  progress?: number
  subTasks: SubTask[]
  metrics: {
    tokensUsed: number
    apiCalls: number
    duration: string
    sourcesFound?: number
    dataPoints?: number
    chaptersWritten?: number
    issuesFound?: number
  }
  dependencies: string[]
  outputs: string[]
  currentAction?: string
  lastUpdate?: string
}

type LogItem = {
  time: string
  agent: string
  content: string
}

type DataItem = {
  source: string
  info: string
  confidence: string
  time: string
}

type PlanNode = {
  id: string
  title: string
  status: 'pending' | 'in_progress' | 'completed'
  children: PlanNode[]
}

const formatAgentLog = (params: {
  agentType?: string
  action?: string
  content?: string
  status?: string
  tokensUsed?: number
  durationMs?: number
}): string => {
  const {
    agentType,
    action,
    content,
    status,
  } = params

  const key = (agentType || '').toLowerCase()
  const agentInfo = agentTypes[key as keyof typeof agentTypes]
  const agentLabel = agentInfo ? agentInfo.name : agentType || ''

  // 如果有具体的内容（如当前操作），优先显示内容
  if (content && content.trim()) {
    // 移除包含进度信息的笼统描述
    let cleanContent = content
      .replace(/整体进度:\s*\d+\.\d+%/g, '')  // 移除整体进度
      .replace(/执行中/g, '')  // 移除执行中
      .replace(/\|\s*\|+/g, '|')  // 清理多余的分隔符
      .replace(/^\|\s*/, '')  // 移除开头的分隔符
      .replace(/\s*\|\s*$/, '')  // 移除结尾的分隔符
      .trim()

    // 如果清理后还有内容，进行进一步处理
    if (cleanContent) {
      // 如果内容以Agent名称开头，移除它
      if (agentLabel && cleanContent.startsWith(agentLabel)) {
        cleanContent = cleanContent.replace(new RegExp(`^${agentLabel}\\s*[|]\\s*`), '')
      }

      cleanContent = cleanContent.trim()

      // 直接返回清理后的内容，不加emoji
      return cleanContent
    }
  }

  // 如果有action，构建详细描述
  if (action && action.trim()) {
    // 根据Agent类型和action生成具体的操作描述
    const actionLower = action.toLowerCase()

    if (key === 'searcher') {
      if (actionLower.includes('search') || actionLower.includes('搜索') || actionLower.includes('query')) {
        const query = action.replace(/^(search|搜索|query)/i, '').trim()
        return `正在搜索: ${query || '相关信息'}`
      } else if (actionLower.includes('extract') || actionLower.includes('提取')) {
        return `正在提取关键词和术语...`
      } else if (actionLower.includes('reflect') || actionLower.includes('反思')) {
        return `正在评估搜索完整性...`
      } else if (actionLower.includes('evaluate') || actionLower.includes('评估')) {
        return `正在评估来源相关性...`
      }
    } else if (key === 'analyzer') {
      if (actionLower.includes('analyze') || actionLower.includes('分析')) {
        return `正在分析数据和内容...`
      } else if (actionLower.includes('synthesize') || actionLower.includes('综合')) {
        return `正在综合分析结果...`
      }
    } else if (key === 'writer') {
      if (actionLower.includes('write') || actionLower.includes('writing') || actionLower.includes('写作') || actionLower.includes('撰写')) {
        return `正在撰写研究报告...`
      } else if (actionLower.includes('humanize') || actionLower.includes('人性化')) {
        return `正在优化报告文风...`
      } else if (actionLower.includes('refine') || actionLower.includes('精化')) {
        return `正在精化报告内容...`
      }
    } else if (key === 'reviewer') {
      if (actionLower.includes('review') || actionLower.includes('审核')) {
        return `正在审核报告质量...`
      } else if (actionLower.includes('peer') || actionLower.includes('同行')) {
        return `正在执行同行评审...`
      }
    } else if (key === 'citer') {
      if (actionLower.includes('cite') || actionLower.includes('引用')) {
        return `正在添加引用标注...`
      } else if (actionLower.includes('reference') || actionLower.includes('参考文献')) {
        return `正在整理参考文献...`
      }
    } else if (key === 'curator') {
      if (actionLower.includes('curate') || actionLower.includes('筛选') || actionLower.includes('filter')) {
        return `正在筛选和评估信息...`
      }
    } else if (key === 'planner') {
      if (actionLower.includes('plan') || actionLower.includes('规划')) {
        return `正在制定研究计划...`
      } else if (actionLower.includes('refine') || actionLower.includes('细化')) {
        return `正在细化研究计划...`
      }
    }

    return `${agentLabel}正在${action}`
  }

  // 如果没有具体内容，使用简洁的状态描述
  if (status && status !== 'info') {
    if (agentLabel) {
      const statusText = status === 'completed' ? '已完成' : status === 'running' ? '进行中' : '工作中'
      return `${agentLabel}${statusText}`
    }
    return status === 'completed' ? '已完成' : status === 'running' ? '进行中' : status
  }

  return agentLabel ? `${agentLabel}工作中` : '工作中'
}



// Agent detail card component - shows detailed execution info
function AgentDetailCard({ activity, isExpanded, onToggle }: {
  activity: AgentActivity
  isExpanded: boolean
  onToggle: () => void
}) {
  const agentInfo = agentTypes[activity.agent]
  const Icon = agentInfo.icon

  // 只有运行中的Agent才显示当前任务信息
  const isRunning = activity.status === 'active'
  const runningTasks = activity.subTasks.filter(t => t.status === 'running')

  // 获取当前运行中的子任务标题
  const runningTaskTitle = runningTasks.length > 0
    ? runningTasks[0].title
    : (activity.currentAction || activity.currentTask || '')

  // 过滤掉JSON格式的内容
  const cleanTaskTitle = (title: string) => {
    if (!title) return ''
    // 如果看起来像JSON，返回空
    if (title.trim().startsWith('{') || title.trim().startsWith('[')) return ''
    // 如果包含大量的引号和冒号，可能是JSON
    if ((title.match(/"/g) || []).length > 4 && title.includes(':')) return ''
    return title
  }

  const displayTask = cleanTaskTitle(runningTaskTitle)

  return (
    <div className={`rounded-lg border transition-all ${
      activity.status === 'active'
        ? `${agentInfo.borderColor} bg-gradient-to-r from-background to-${agentInfo.bgColor}`
        : activity.status === 'completed'
        ? 'border-green-500/30 bg-green-500/5'
        : 'border-border bg-muted/30'
    }`}>
      {/* Header - always visible */}
      <div
        className="p-4 cursor-pointer hover:bg-accent/30 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-start gap-3">
          <div className={`p-2.5 rounded-lg ${agentInfo.bgColor}`}>
            <Icon className={`h-5 w-5 ${agentInfo.color}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-semibold text-sm">{agentInfo.name}</h4>
              {activity.status === 'active' && (
                <span className="flex items-center gap-1 text-xs text-primary">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  运行中
                </span>
              )}
              {activity.status === 'completed' && (
                <span className="flex items-center gap-1 text-xs text-green-600">
                  <CheckCircle2 className="h-3 w-3" />
                  已完成
                </span>
              )}
              {activity.status === 'idle' && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  等待中
                </span>
              )}
              <div className="ml-auto">
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
            </div>

            {/* Metrics summary - 简洁的指标行 */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Timer className="h-3 w-3" />
                {activity.metrics.duration}
              </span>
              <span className="flex items-center gap-1">
                <Zap className="h-3 w-3" />
                {activity.metrics.tokensUsed.toLocaleString()} tokens
              </span>
              {/* 只有运行中的Agent才显示当前任务 */}
              {isRunning && displayTask && (
                <span className="flex items-center gap-1 text-primary font-medium">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span className="truncate max-w-60">{displayTask}</span>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-border/50">
          {/* Metrics grid */}
          <div className="grid grid-cols-4 gap-3 py-3 border-b border-border/50">
            <div className="text-center">
              <p className="text-lg font-semibold text-primary">{activity.metrics.tokensUsed.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Tokens</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-primary">{activity.metrics.apiCalls}</p>
              <p className="text-xs text-muted-foreground">API调用</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-primary">{activity.metrics.duration}</p>
              <p className="text-xs text-muted-foreground">耗时</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-primary">
                {activity.metrics.sourcesFound ?? activity.metrics.dataPoints ?? activity.metrics.chaptersWritten ?? activity.metrics.issuesFound ?? '-'}
              </p>
              <p className="text-xs text-muted-foreground">
                {activity.agent === 'searcher' ? '来源数' :
                 activity.agent === 'analyzer' ? '数据点' :
                 activity.agent === 'writer' ? '章节数' :
                 activity.agent === 'reviewer' ? '问题数' : '输出'}
              </p>
            </div>
          </div>

          {/* Dependencies */}
          {(activity.dependencies.length > 0 || activity.outputs.length > 0) && (
            <div className="py-3 border-b border-border/50 flex items-center gap-4 text-xs">
              {activity.dependencies.length > 0 && (
                <div className="flex items-center gap-2">
                  <Link2 className="h-3 w-3 text-muted-foreground" />
                  <span className="text-muted-foreground">依赖:</span>
                  {activity.dependencies.map(depId => {
                    const depInfo = agentTypes[depId as keyof typeof agentTypes]
                    if (!depInfo) return null
                    return (
                      <span key={depId} className={`px-1.5 py-0.5 rounded ${depInfo.bgColor} ${depInfo.color}`}>
                        {depInfo.name}
                      </span>
                    )
                  })}
                </div>
              )}
              {activity.outputs.length > 0 && (
                <div className="flex items-center gap-2">
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  <span className="text-muted-foreground">输出至:</span>
                  {activity.outputs.map(outId => {
                    const outInfo = agentTypes[outId as keyof typeof agentTypes]
                    if (!outInfo) return null
                    return (
                      <span key={outId} className={`px-1.5 py-0.5 rounded ${outInfo.bgColor} ${outInfo.color}`}>
                        {outInfo.name}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          )}


        </div>
      )}
    </div>
  )
}

export default function ProcessView() {
  const { taskId } = useParams<{ taskId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const numericTaskId = taskId ? Number(taskId) : NaN
  const [currentStage, setCurrentStage] = useState(0)
  const [progress, setProgress] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [logs, setLogs] = useState<LogItem[]>([])
  const [agentActivities, setAgentActivities] = useState<AgentActivity[]>([])
  const [plan, setPlan] = useState<PlanNode[]>([])
  const [dataItems, setDataItems] = useState<DataItem[]>([])
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(
    () => new Set(Object.keys(agentTypes))
  )
  const logsEndRef = useRef<HTMLDivElement>(null)
  const wsConnectedRef = useRef(false)

  // 保存plan到localStorage，防止刷新丢失
  useEffect(() => {
    if (plan.length > 0 && taskId) {
      try {
        localStorage.setItem(`research_plan_${taskId}`, JSON.stringify(plan))
      } catch (e) {
        console.warn('Failed to save plan to localStorage:', e)
      }
    }
  }, [plan, taskId])

  // 保存dataItems到localStorage
  useEffect(() => {
    if (dataItems.length > 0 && taskId) {
      try {
        localStorage.setItem(`research_data_${taskId}`, JSON.stringify(dataItems))
      } catch (e) {
        console.warn('Failed to save data items to localStorage:', e)
      }
    }
  }, [dataItems, taskId])

  const totalPlanTasks = plan.reduce((sum, item) => sum + 1 + item.children.length, 0)

  const [query, setQuery] = useState(
    (location.state as { query?: string } | null)?.query || ''
  )

  // 当开始新任务时，清空旧的localStorage数据和state，防止显示过期的示例数据
  useEffect(() => {
    if (taskId && !Number.isNaN(numericTaskId)) {
      // 清空该任务的所有localStorage数据，从API加载全新的数据
      localStorage.removeItem(`research_plan_${numericTaskId}`)
      localStorage.removeItem(`research_data_${numericTaskId}`)

      // 重置所有state，等待API加载真实数据
      setPlan([])
      setDataItems([])
      setAgentActivities([])
      setQuery('')
      setLogs([])
      setCurrentStage(0)
      setProgress(0)
    }
  }, [taskId, numericTaskId])

  // Toggle agent expansion
  const toggleAgentExpanded = (agentId: string) => {
    setExpandedAgents(prev => {
      const next = new Set(prev)
      if (next.has(agentId)) {
        next.delete(agentId)
      } else {
        next.add(agentId)
      }
      return next
    })
  }

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])
  const mapStatusToStage = (status: TaskStatus): number => {
    switch (status) {
      case 'planning':
        return 0
      case 'searching':
        return 1
      case 'curating':
        return 2
      case 'analyzing':
        return 3
      case 'writing':
        return 4
      case 'citing':
        return 5
      case 'reviewing':
      case 'completed':
        return 6
      default:
        return 0
    }
  }

  const normalizePlanStatus = (status: string): PlanNode['status'] => {
    if (status === 'completed') return 'completed'
    if (status === 'in_progress') return 'in_progress'
    return 'pending'
  }

  const computePlanStatus = (
    index: number,
    total: number,
    globalProgress: number,
    agentActivities?: AgentActivity[]
  ): PlanNode['status'] => {
    // 如果有Agent活动信息，优先使用Agent状态来确定计划状态
    if (agentActivities && agentActivities.length > 0) {
      // 根据Agent类型映射到计划阶段
      const agentToPlanMap = {
        'planner': 0,    // 规划阶段
        'searcher': 1,   // 搜索阶段
        'curator': 2,    // 筛选阶段
        'analyzer': 3,   // 分析阶段
        'writer': 4,     // 写作阶段
        'citer': 5,      // 引用阶段
        'reviewer': 6,   // 审核阶段
      }

      // 找到活跃的Agent
      const activeAgent = agentActivities.find(a => a.status === 'running' || a.status === 'active')
      if (activeAgent) {
        const agentIndex = agentToPlanMap[activeAgent.agent as keyof typeof agentToPlanMap]
        if (agentIndex !== undefined) {
          if (index < agentIndex) return 'completed'
          if (index === agentIndex) return 'in_progress'
          return 'pending'
        }
      }

      // 如果有已完成的Agent，相应阶段也完成
      for (const activity of agentActivities) {
        if (activity.status === 'completed') {
          const agentIndex = agentToPlanMap[activity.agent as keyof typeof agentToPlanMap]
          if (agentIndex !== undefined && index <= agentIndex) {
            return 'completed'
          }
        }
      }
    }

    // 回退到基于全局进度的计算
    if (total <= 0) return 'pending'
    const stepSize = 100 / total
    const completedSteps = Math.floor(globalProgress / stepSize)

    if (index < completedSteps) return 'completed'
    if (index === completedSteps && globalProgress < 100) return 'in_progress'
    if (globalProgress >= 100) return 'completed'
    return 'pending'
  }

  const buildPlanFromApi = (items: ApiPlanItem[]): PlanNode[] => {
    if (!items || items.length === 0) return []

    const roots = items
      .filter((item) => item.parent_id === null)
      .sort((a, b) => a.order - b.order)

    return roots.map((root) => ({
      id: String(root.id),
      title: root.title,
      status: normalizePlanStatus(root.status),
      children: (root.children || [])
        .slice()
        .sort((a, b) => a.order - b.order)
        .map((child) => ({
          id: String(child.id),
          title: child.title,
          status: normalizePlanStatus(child.status),
          children: [],
        })),
    }))
  }

  const buildSourcesFromApi = (sources: ApiSource[]): DataItem[] => {
    if (!sources || sources.length === 0) return []

    return sources.map((src) => ({
      source: src.title,
      info: src.content || src.url || '',
      confidence: src.confidence || 'medium',
      time: new Date(src.created_at).toLocaleTimeString('zh-CN', { hour12: false }),
    }))
  }

  const buildLogsFromApi = (apiLogs: ApiAgentLog[]): LogItem[] => {
    if (!apiLogs || apiLogs.length === 0) return []

    return apiLogs
      .slice()
      .reverse()
      .map((log) => ({
        time: new Date(log.created_at).toLocaleTimeString('zh-CN', { hour12: false }),
        agent: log.agent_type.toLowerCase(),
        content: formatAgentLog({
          agentType: log.agent_type,
          action: log.action,
          content: log.content,
          status: log.status,
          tokensUsed: log.tokens_used,
          durationMs: log.duration_ms,
        }),
      }))
  }

  const getAgentDependencies = (agent: keyof typeof agentTypes): string[] => {
    switch (agent) {
      case 'planner':
        return []
      case 'searcher':
        return ['planner']
      case 'curator':
        return ['searcher']
      case 'analyzer':
        return ['curator']
      case 'writer':
        return ['analyzer']
      case 'citer':
        return ['writer']
      case 'reviewer':
        return ['citer']
      default:
        return []
    }
  }

  const getAgentOutputs = (agent: keyof typeof agentTypes): string[] => {
    switch (agent) {
      case 'planner':
        return ['searcher']
      case 'searcher':
        return ['curator']
      case 'curator':
        return ['analyzer']
      case 'analyzer':
        return ['writer']
      case 'writer':
        return ['citer']
      case 'citer':
        return ['reviewer']
      default:
        return []
    }
  }

  const normalizeSubTaskStatus = (status: string): SubTask['status'] => {
    const value = status.toLowerCase()
    if (value === 'completed' || value === 'done' || value === 'success') return 'completed'
    if (value === 'failed' || value === 'error') return 'failed'
    if (value === 'running' || value === 'in_progress' || value === 'active') return 'running'
    return 'pending'
  }

  const mapAgentActivityStatus = (status: string): AgentActivity['status'] => {
    const value = status.toLowerCase()
    if (value === 'active' || value === 'running' || value === 'working') return 'active'
    if (value === 'completed' || value === 'done' || value === 'success') return 'completed'
    return 'idle'
  }

  const buildAgentsFromApi = (agents: BackendAgentActivity[]): AgentActivity[] => {
    // 如果API没有返回agents，返回空数组而不是示例数据
    // 等待WebSocket发送实时更新
    if (!agents || agents.length === 0) return []

    const agentActivitiesMap = new Map<string, AgentActivity>()

    agents.forEach((agent) => {
        const key = agent.agent_type as keyof typeof agentTypes
        if (!agentTypes[key]) return

        const metrics = agent.metrics || {}
        const tokensUsed = Number(
          (metrics as any).tokensUsed ?? (metrics as any).tokens_used ?? 0
        )
        const apiCalls = Number(
          (metrics as any).apiCalls ?? (metrics as any).api_calls ?? 0
        )

        let duration = '-'
        if (typeof (metrics as any).duration === 'string') {
          duration = (metrics as any).duration
        } else if (typeof (metrics as any).duration_ms === 'number') {
          duration = `${((metrics as any).duration_ms / 1000).toFixed(1)}s`
        }

        let status: AgentActivity['status'] = 'idle'
        if (agent.status === 'active') status = 'active'
        else if (agent.status === 'completed') status = 'completed'

        const activity: AgentActivity = {
          id: key,
          agent: key,
          status,
          currentTask: agent.current_task || '',
          output: undefined,
          progress: agent.progress ?? 0,
          subTasks: [],
          metrics: {
            tokensUsed,
            apiCalls,
            duration,
          },
          dependencies: getAgentDependencies(key),
          outputs: getAgentOutputs(key),
          currentAction: undefined,
          lastUpdate: undefined,
        }

        agentActivitiesMap.set(key, activity)
      })

    return Array.from(agentActivitiesMap.values())
  }

  useEffect(() => {
    if (!taskId || Number.isNaN(numericTaskId)) return

    let cancelled = false

    const load = async () => {
      try {
        setIsLoading(true)

        const [taskDetail, agentActivity] = await Promise.all([
          getResearchTask(numericTaskId),
          getAgentActivity(numericTaskId),
        ])

        if (cancelled) return

        setQuery(taskDetail.query)
        setProgress(taskDetail.progress || 0)
        setCurrentStage(mapStatusToStage(taskDetail.status))
        setIsPaused(taskDetail.status === 'paused')

        const builtPlan = buildPlanFromApi(taskDetail.plan_items as unknown as ApiPlanItem[])
        if (builtPlan.length > 0) {
          setPlan(builtPlan)
        } else {
          // API返回空数据时，尝试从localStorage恢复
          // 如果localStorage也是空，则保持现有状态等待WebSocket发送plan_snapshot
          try {
            const savedPlan = localStorage.getItem(`research_plan_${numericTaskId}`)
            if (savedPlan) {
              const parsedPlan = JSON.parse(savedPlan)
              if (Array.isArray(parsedPlan) && parsedPlan.length > 0) {
                setPlan(parsedPlan)
              }
            }
          } catch (e) {
            console.warn('Failed to restore plan from localStorage:', e)
          }
        }

        // 合并sources数据，而不是覆盖（保留WebSocket实时添加的数据）
        const apiSources = buildSourcesFromApi(taskDetail.sources as unknown as ApiSource[])
        setDataItems((prev) => {
          if (apiSources.length === 0) {
            // API没有数据时，尝试从localStorage恢复
            if (prev.length === 0) {
              try {
                const savedData = localStorage.getItem(`research_data_${numericTaskId}`)
                if (savedData) {
                  const parsedData = JSON.parse(savedData)
                  if (Array.isArray(parsedData) && parsedData.length > 0) {
                    return parsedData
                  }
                }
              } catch (e) {
                console.warn('Failed to restore data items from localStorage:', e)
              }
            }
            return prev  // API没有数据时保留现有数据
          }
          // 如果API有数据，使用API数据但保留WebSocket新增的（通过source标题去重）
          const apiSourceTitles = new Set(apiSources.map(s => s.source))
          const newFromWs = prev.filter(item => !apiSourceTitles.has(item.source))
          return [...apiSources, ...newFromWs]
        })

        setLogs(buildLogsFromApi(taskDetail.recent_logs as unknown as ApiAgentLog[]))

        // 合并Agent活动状态，保留WebSocket更新的实时数据（tokens, apiCalls, currentAction等）
        const apiAgents = buildAgentsFromApi(agentActivity.agents)
        setAgentActivities((prev) => {
          // 如果之前没有数据，直接使用API数据
          if (prev.length === 0) return apiAgents

          // 合并：保留WebSocket更新的实时指标
          return apiAgents.map((apiAgent) => {
            const existing = prev.find(p => p.agent === apiAgent.agent)
            if (!existing) return apiAgent

            // 保留较大的tokens和apiCalls值（WebSocket更新的实时数据通常更准确）
            const mergedTokens = Math.max(existing.metrics.tokensUsed, apiAgent.metrics.tokensUsed)
            const mergedApiCalls = Math.max(existing.metrics.apiCalls, apiAgent.metrics.apiCalls)
            const mergedDuration = existing.metrics.duration !== '-' ? existing.metrics.duration : apiAgent.metrics.duration

            return {
              ...apiAgent,
              // 保留WebSocket更新的实时状态
              currentAction: existing.currentAction || apiAgent.currentAction,
              currentTask: existing.currentTask || apiAgent.currentTask,
              subTasks: existing.subTasks.length > 0 ? existing.subTasks : apiAgent.subTasks,
              output: existing.output || apiAgent.output,
              metrics: {
                ...apiAgent.metrics,
                tokensUsed: mergedTokens,
                apiCalls: mergedApiCalls,
                duration: mergedDuration,
              },
            }
          })
        })
      } catch (error) {
        console.error('加载研究任务失败:', error)
        setError('加载研究任务失败，请稍后重试')
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    load()

    // 当WebSocket连接正常时，降低轮询频率（30秒），因为实时数据通过WebSocket更新
    // 当WebSocket断开时，增加轮询频率（5秒）作为备用
    const getPollingInterval = () => wsConnectedRef.current ? 30000 : 5000
    let intervalId = setInterval(load, getPollingInterval())

    // 定期检查并调整轮询频率
    const adjustInterval = setInterval(() => {
      clearInterval(intervalId)
      intervalId = setInterval(load, getPollingInterval())
    }, 10000)

    return () => {
      cancelled = true
      clearInterval(intervalId)
      clearInterval(adjustInterval)
    }
  }, [taskId, numericTaskId])

  // 当Agent活动状态变化时，同步更新研究计划状态
  useEffect(() => {
    if (plan.length === 0 || agentActivities.length === 0) return

    // 根据Agent状态更新研究计划状态
    setPlan((prevPlan) => {
      return prevPlan.map((node, index) => {
        const newStatus = computePlanStatus(index, prevPlan.length, progress, agentActivities)
        if (node.status === newStatus) return node
        return {
          ...node,
          status: newStatus,
          children: node.children.map((child) => ({
            ...child,
            status: newStatus === 'completed' ? 'completed' : child.status,
          })),
        }
      })
    })
  }, [agentActivities, progress])

  useEffect(() => {
    if (!taskId || Number.isNaN(numericTaskId)) return

    const ws = createWebSocket(numericTaskId)

    wsConnectedRef.current = false

    ws.onopen = () => {
      wsConnectedRef.current = true
      setError(null)
      setIsPaused(false)
    }

        ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        // 调试日志 - 只在开发环境显示
        if (process.env.NODE_ENV === 'development' && msg.type === 'agent_log') {
          console.log('WebSocket agent_log message:', msg)
        }

        if (msg.type === 'connected') {
          wsConnectedRef.current = true
          setError(null)
          setIsPaused(false)
        } else if (msg.type === 'agent_log') {
          const agentType = (msg.agent_type || '').toLowerCase()
          const logTime = msg.timestamp
            ? new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour12: false })
            : new Date().toLocaleTimeString('zh-CN', { hour12: false })

          setLogs((prev) => [
            ...prev.slice(-25),
            {
              time: logTime,
              agent: agentType,
              content: formatAgentLog({
                agentType,
                action: msg.action,
                content: msg.content,
                status: msg.status,
                tokensUsed: msg.tokens_used,
                durationMs: msg.duration_ms,
              }),
            },
          ])

           const tokensUsedFromLog = Number(msg.tokens_used ?? 0)
           const apiCallsFromLog = Number(msg.api_calls ?? 0)
           const durationMsFromLog = Number(msg.duration_ms ?? 0)

           if (agentType) {
             setAgentActivities((prev) =>
               prev.map((a) => {
                 if (a.agent !== agentType) return a

                 const durationLabel =
                   durationMsFromLog > 0
                     ? `${(durationMsFromLog / 1000).toFixed(1)}s`
                     : a.metrics.duration

                 // 累加tokens和apiCalls，而不是替换（如果新值大于0）
                 const newTokens = tokensUsedFromLog > 0
                   ? Math.max(tokensUsedFromLog, a.metrics.tokensUsed)
                   : a.metrics.tokensUsed
                 const newApiCalls = apiCallsFromLog > 0
                   ? Math.max(apiCallsFromLog, a.metrics.apiCalls)
                   : a.metrics.apiCalls

                 return {
                   ...a,
                    metrics: {
                      ...a.metrics,
                      tokensUsed: newTokens,
                      apiCalls: newApiCalls,
                      duration: durationLabel,
                    },
                   lastUpdate: logTime,
                 }
               })
             )
           }
        } else if (msg.type === 'progress') {
          const p = typeof msg.progress === 'number' ? msg.progress : Number(msg.progress) || 0
          setProgress(p)

          const stage = msg.stage as string | undefined

          if (stage && stage !== 'paused') {
            setCurrentStage(mapStatusToStage(stage as TaskStatus))

            const ranges: Record<string, [number, number]> = {
              planning: [0.0, 10.0],
              searching: [10.0, 25.0],
              curating: [25.0, 40.0],
              analyzing: [40.0, 55.0],
              writing: [55.0, 70.0],
              citing: [70.0, 85.0],
              reviewing: [85.0, 95.0],
            }

            const stageKey = stage.toLowerCase()
            const agentMap: Record<string, keyof typeof agentTypes> = {
              planning: 'planner',
              searching: 'searcher',
              curating: 'curator',
              analyzing: 'analyzer',
              writing: 'writer',
              citing: 'citer',
              reviewing: 'reviewer',
            }

            const activeAgent = agentMap[stageKey]
            const span = ranges[stageKey]

            if (activeAgent && span) {
              const clamped = Math.min(100, Math.max(0, Number(p) || 0))
              const [start, end] = span
              let localProgress = clamped
              if (clamped <= start) {
                localProgress = 0
              } else if (clamped >= end) {
                localProgress = 100
              } else {
                localProgress = ((clamped - start) / (end - start)) * 100
              }

              // Agent执行顺序
              const agentOrder = ['planner', 'searcher', 'curator', 'analyzer', 'writer', 'citer', 'reviewer']
              const currentAgentIndex = agentOrder.indexOf(activeAgent)

              setAgentActivities((prev) =>
                prev.map((a) => {
                  const thisAgentIndex = agentOrder.indexOf(a.agent)

                  // 如果是当前活跃的Agent
                  if (a.agent === activeAgent) {
                    return {
                      ...a,
                      status: localProgress >= 100 ? 'completed' : 'active',
                      progress: localProgress,
                    }
                  }

                  // 如果是前面的Agent，应该标记为completed
                  if (thisAgentIndex >= 0 && currentAgentIndex >= 0 && thisAgentIndex < currentAgentIndex) {
                    if (a.status === 'active' || a.status === 'idle') {
                      return {
                        ...a,
                        status: 'completed',
                        currentAction: undefined,
                      }
                    }
                  }

                  return a
                })
              )
            }
          }

          if (stage === 'paused') {
            setIsPaused(true)
          }
        } else if (msg.type === 'plan_update') {
          getResearchTask(numericTaskId)
            .then((taskDetail) => {
              const builtPlan = buildPlanFromApi(taskDetail.plan_items as unknown as ApiPlanItem[])
              if (builtPlan.length > 0) {
                setPlan(builtPlan)
                // 保存到localStorage
                if (numericTaskId) {
                  try {
                    localStorage.setItem(`research_plan_${numericTaskId}`, JSON.stringify(builtPlan))
                  } catch (e) {
                    console.warn('Failed to save plan to localStorage:', e)
                  }
                }
              }
              // 合并sources数据，只有API有数据时才更新
              const apiSources = buildSourcesFromApi(taskDetail.sources as unknown as ApiSource[])
              if (apiSources.length > 0) {
                setDataItems((prev) => {
                  // 合并：API数据优先，但保留WebSocket新增的
                  const apiSourceTitles = new Set(apiSources.map(s => s.source))
                  const newFromWs = prev.filter(item => !apiSourceTitles.has(item.source))
                  const updated = [...apiSources, ...newFromWs]
                  // 保存到localStorage
                  if (numericTaskId) {
                    try {
                      localStorage.setItem(`research_data_${numericTaskId}`, JSON.stringify(updated))
                    } catch (e) {
                      console.warn('Failed to save data items to localStorage:', e)
                    }
                  }
                  return updated
                })
              }
              setLogs(
                buildLogsFromApi(taskDetail.recent_logs as unknown as ApiAgentLog[])
              )
            })
            .catch((error) => {
              console.error('通过WebSocket刷新研究计划失败:', error)
            })
        } else if (msg.type === 'plan_snapshot') {
          // 实时接收研究计划快照
          const steps =
            msg.plan || msg.research_plan || msg.steps || msg.plan_steps || []

          if (process.env.NODE_ENV === 'development') {
            console.log('WebSocket plan_snapshot message:', msg, 'steps:', steps)
          }

          if (Array.isArray(steps) && steps.length > 0) {
            const nodes: PlanNode[] = steps.map((step: any, index: number) => ({
              id: String(step.step ?? step.id ?? index + 1),
              title: step.title || step.name || `步骤 ${step.step ?? index + 1}`,
              status: 'pending',
              children: Array.isArray(step.sub_steps || step.children)
                ? (step.sub_steps || step.children).map((sub: any, subIndex: number) => ({
                    id: String(sub.step ?? sub.id ?? `${index + 1}-${subIndex + 1}`),
                    title: sub.title || sub.name || `子步骤 ${subIndex + 1}`,
                    status: 'pending',
                    children: [],
                  }))
                : [],
            }))

            setPlan(nodes)

            // 保存到localStorage
            if (numericTaskId) {
              try {
                localStorage.setItem(`research_plan_${numericTaskId}`, JSON.stringify(nodes))
              } catch (e) {
                console.warn('Failed to save plan snapshot to localStorage:', e)
              }
            }

            if (process.env.NODE_ENV === 'development') {
              console.log('Plan updated from plan_snapshot:', nodes)
            }
          }
        } else if (msg.type === 'source_added') {
          const src = msg.source
          if (src) {
            setDataItems((prev) => {
              const newItems = [
                ...prev,
                {
                  source: src.title,
                  info: src.content || src.url || '',
                  confidence: src.confidence || 'medium',
                  time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
                },
              ]
              // 保存到localStorage
              if (numericTaskId) {
                try {
                  localStorage.setItem(`research_data_${numericTaskId}`, JSON.stringify(newItems))
                } catch (e) {
                  console.warn('Failed to save data items to localStorage:', e)
                }
              }
              return newItems
            })
          }
        } else if (msg.type === 'error') {
          const message =
            typeof msg.message === 'string' && msg.message.trim().length > 0
              ? msg.message
              : '研究任务执行过程中发生错误，请检查后重试'

          setError(message)
          setIsPaused(true)
         } else if (msg.type === 'data_refresh') {
           // 刷新数据，特别是在筛选Agent完成后
           // 只有当API返回有数据时才更新，避免清空WebSocket实时添加的数据
           getResearchTask(numericTaskId).then((taskDetail) => {
             const apiSources = buildSourcesFromApi(taskDetail.sources as unknown as ApiSource[])
             if (apiSources.length > 0) {
               setDataItems((prev) => {
                 // 合并：API数据优先，但保留WebSocket新增的
                 const apiSourceTitles = new Set(apiSources.map(s => s.source))
                 const newFromWs = prev.filter(item => !apiSourceTitles.has(item.source))
                 const updated = [...apiSources, ...newFromWs]
                 // 保存到localStorage
                 if (numericTaskId) {
                   try {
                     localStorage.setItem(`research_data_${numericTaskId}`, JSON.stringify(updated))
                   } catch (e) {
                     console.warn('Failed to save data items to localStorage:', e)
                   }
                 }
                 return updated
               })
             }
           }).catch((error) => {
             console.error('刷新数据失败:', error)
           })
         } else if (msg.type === 'completed') {
           setProgress(100)
           setCurrentStage(mapStatusToStage('completed'))

           // 研究任务完成后跳转到报告页，展示真实报告内容
           if (!Number.isNaN(numericTaskId)) {
             navigate(`/report/${numericTaskId}`)
           }
          } else if (msg.type === 'agent_status_update') {
            // 处理Agent实时状态更新 - 这是最关键的实时数据来源
            const agentType = (msg.agent_type || '').toLowerCase()
            const apiCalls = Number(msg.api_calls ?? 0)
            const tokensUsed = Number(msg.tokens_used ?? 0)
            const duration = msg.duration || '-'
            const currentSubtask = msg.current_subtask || ''
            const outputContent = msg.output_content || ''

            // 调试日志 - 开发环境显示
            if (process.env.NODE_ENV === 'development') {
              console.log('WebSocket agent_status_update:', {
                agentType,
                tokensUsed,
                apiCalls,
                duration,
                currentSubtask,
              })
            }

            if (agentType) {
              setAgentActivities((prev) => {
                // Agent执行顺序
                const agentOrder = ['planner', 'searcher', 'curator', 'analyzer', 'writer', 'citer', 'reviewer']
                const currentAgentIndex = agentOrder.indexOf(agentType)

                return prev.map((a) => {
                  const thisAgentIndex = agentOrder.indexOf(a.agent)

                  // 如果是当前活跃的Agent
                  if (a.agent === agentType) {
                    // 更新metrics，使用最大值来避免数据丢失
                    const newTokens = tokensUsed > 0
                      ? Math.max(tokensUsed, a.metrics.tokensUsed)
                      : a.metrics.tokensUsed
                    const newApiCalls = apiCalls > 0
                      ? Math.max(apiCalls, a.metrics.apiCalls)
                      : a.metrics.apiCalls

                    // 创建或更新当前子任务
                    let updatedSubTasks = [...a.subTasks]
                    if (currentSubtask) {
                      const currentSubtaskId = `current_${agentType}`
                      const existingIndex = updatedSubTasks.findIndex(t => t.id === currentSubtaskId)
                      const newSubTask: SubTask = {
                        id: currentSubtaskId,
                        title: currentSubtask,
                        status: 'running',
                        startTime: new Date().toISOString(),
                      }

                      if (existingIndex >= 0) {
                        updatedSubTasks[existingIndex] = {
                          ...updatedSubTasks[existingIndex],
                          ...newSubTask,
                        }
                      } else {
                        updatedSubTasks.push(newSubTask)
                      }
                    }

                    return {
                      ...a,
                      status: 'active',
                      currentTask: currentSubtask || a.currentTask,
                      currentAction: currentSubtask || a.currentAction,
                      output: outputContent || a.output,
                      subTasks: updatedSubTasks,
                      metrics: {
                        ...a.metrics,
                        tokensUsed: newTokens,
                        apiCalls: newApiCalls,
                        duration: duration !== '-' ? duration : a.metrics.duration,
                      },
                      lastUpdate: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
                    }
                  }

                  // 如果是前面的Agent，且当前Agent正在运行，则前面的应该是completed
                  if (thisAgentIndex >= 0 && currentAgentIndex >= 0 && thisAgentIndex < currentAgentIndex) {
                    if (a.status === 'active' || a.status === 'idle') {
                      // 清理子任务状态
                      const completedSubTasks = a.subTasks.map(t => ({
                        ...t,
                        status: 'completed' as const,
                      }))
                      return {
                        ...a,
                        status: 'completed',
                        currentAction: undefined,
                        subTasks: completedSubTasks,
                      }
                    }
                  }

                  return a
                })
              })
            }

            // 如果是筛选Agent，实时更新筛选后的数据（只有API有数据时才更新）
            if (agentType === 'curator') {
              getResearchTask(numericTaskId).then((taskDetail) => {
                const apiSources = buildSourcesFromApi(taskDetail.sources as unknown as ApiSource[])
                if (apiSources.length > 0) {
                  setDataItems((prev) => {
                    // 合并：API数据（筛选后的）优先，但保留WebSocket新增的
                    const apiSourceTitles = new Set(apiSources.map(s => s.source))
                    const newFromWs = prev.filter(item => !apiSourceTitles.has(item.source))
                    const updated = [...apiSources, ...newFromWs]
                    // 保存到localStorage
                    if (numericTaskId) {
                      try {
                        localStorage.setItem(`research_data_${numericTaskId}`, JSON.stringify(updated))
                      } catch (e) {
                        console.warn('Failed to save data items to localStorage:', e)
                      }
                    }
                    return updated
                  })
                }
                // 如果API没有数据，保留现有的WebSocket数据不变
              }).catch((error) => {
                console.error('重新获取任务详情失败:', error)
              })
            }
         } else if (msg.type === 'review_failed') {
           // 处理审核失败，进度条回滚
           const rollbackProgress = msg.rollback_progress || 70.0
           setProgress(rollbackProgress)
           setCurrentStage(mapStatusToStage('writing')) // 回滚到写作阶段

           // 更新Agent状态
           setAgentActivities((prev) => {
             return prev.map((a) => {
               if (a.agent === 'reviewer') {
                 return {
                   ...a,
                   status: 'failed',
                   currentTask: '审核未通过，正在重写',
                 }
               } else if (a.agent === 'writer') {
                 return {
                   ...a,
                   status: 'active',
                   currentTask: '根据审核意见重写报告',
                 }
               }
               return a
             })
           })

           console.log('报告审核未通过，进度回滚到写作阶段:', msg.message)
         } else if (msg.type === 'agent_activity') {
          const rawType = (msg.agent_type || msg.agentType || '').toLowerCase()
          if (!rawType || !agentTypes[rawType as keyof typeof agentTypes]) return

          const key = rawType as keyof typeof agentTypes
          const metrics = msg.metrics || {}
          const tokensUsed = Number(
            metrics.tokensUsed ?? metrics.tokens_used ?? 0
          )
          const apiCalls = Number(
            metrics.apiCalls ?? metrics.api_calls ?? 0
          )

          let duration = '-'
          if (typeof metrics.duration === 'string') {
            duration = metrics.duration
          } else if (typeof metrics.duration_ms === 'number') {
            duration = `${(metrics.duration_ms / 1000).toFixed(1)}s`
          }

          const status = mapAgentActivityStatus(
            msg.status || msg.agent_status || ''
          )
          const currentTask = msg.current_task || msg.currentTask || ''
          const currentAction = msg.current_action || msg.currentAction || currentTask
          const lastUpdate = msg.timestamp
            ? new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour12: false })
            : undefined
          const progressValue =
            typeof msg.progress === 'number'
              ? msg.progress
              : Number(msg.progress ?? 0)

          setAgentActivities((prev) => {
            // Agent执行顺序
            const agentOrder = ['planner', 'searcher', 'curator', 'analyzer', 'writer', 'citer', 'reviewer']
            const currentAgentIndex = agentOrder.indexOf(key)

            const existing = prev.find((a) => a.agent === key)
            if (!existing) {
              // 创建新的子任务用于显示当前操作
              const initialSubTasks: SubTask[] = currentTask ? [{
                id: `current_${key}`,
                title: currentTask,
                status: status === 'active' ? 'running' : 'completed',
                startTime: new Date().toISOString(),
              }] : []

              const activity: AgentActivity = {
                id: key,
                agent: key,
                status,
                currentTask,
                output: undefined,
                progress: progressValue,
                subTasks: initialSubTasks,
                metrics: {
                  tokensUsed,
                  apiCalls,
                  duration,
                },
                dependencies: getAgentDependencies(key),
                outputs: getAgentOutputs(key),
                currentAction: currentAction || undefined,
                lastUpdate,
              }
              return [...prev, activity]
            }

            return prev.map((a) => {
              const thisAgentIndex = agentOrder.indexOf(a.agent)

              // 如果是当前Agent
              if (a.agent === key) {
                const normalizedProgress =
                  typeof progressValue === 'number' && !Number.isNaN(progressValue)
                    ? progressValue
                    : a.progress

                // 更新或创建当前子任务
                let updatedSubTasks = [...a.subTasks]
                if (currentTask && status === 'active') {
                  const currentSubtaskId = `current_${key}`
                  const existingIndex = updatedSubTasks.findIndex(t => t.id === currentSubtaskId)
                  const newSubTask: SubTask = {
                    id: currentSubtaskId,
                    title: currentTask,
                    status: 'running',
                    startTime: new Date().toISOString(),
                  }

                  if (existingIndex >= 0) {
                    updatedSubTasks[existingIndex] = {
                      ...updatedSubTasks[existingIndex],
                      ...newSubTask,
                    }
                  } else {
                    updatedSubTasks.push(newSubTask)
                  }
                } else if (status === 'completed') {
                  // Agent完成时，清理子任务状态
                  updatedSubTasks = updatedSubTasks.map(t => ({
                    ...t,
                    status: 'completed' as const,
                  }))
                }

                // 使用最大值更新metrics，避免数据丢失
                const newTokens = tokensUsed > 0
                  ? Math.max(tokensUsed, a.metrics.tokensUsed)
                  : a.metrics.tokensUsed
                const newApiCalls = apiCalls > 0
                  ? Math.max(apiCalls, a.metrics.apiCalls)
                  : a.metrics.apiCalls

                return {
                  ...a,
                  status,
                  currentTask: currentTask || a.currentTask,
                  progress: normalizedProgress,
                  subTasks: updatedSubTasks,
                  metrics: {
                    ...a.metrics,
                    tokensUsed: newTokens,
                    apiCalls: newApiCalls,
                    duration: duration !== '-' ? duration : a.metrics.duration,
                  },
                  currentAction: status === 'completed' ? undefined : (currentAction || a.currentAction),
                  lastUpdate: lastUpdate ?? a.lastUpdate,
                }
              }

              // 如果当前Agent是active，前面的Agent应该是completed
              if (status === 'active' && thisAgentIndex >= 0 && currentAgentIndex >= 0 && thisAgentIndex < currentAgentIndex) {
                if (a.status === 'active' || a.status === 'idle') {
                  const completedSubTasks = a.subTasks.map(t => ({
                    ...t,
                    status: 'completed' as const,
                  }))
                  return {
                    ...a,
                    status: 'completed',
                    currentAction: undefined,
                    subTasks: completedSubTasks,
                  }
                }
              }

              return a
            })
          })

           // 如果是筛选Agent且状态为完成，实时更新筛选后的数据（只有API有数据时才更新）
           if (key === 'curator' && status === 'completed') {
             getResearchTask(numericTaskId).then((taskDetail) => {
               const apiSources = buildSourcesFromApi(taskDetail.sources as unknown as ApiSource[])
               if (apiSources.length > 0) {
                 setDataItems((prev) => {
                   // 筛选完成后，使用API返回的筛选后数据，但保留WebSocket新增的
                   const apiSourceTitles = new Set(apiSources.map(s => s.source))
                   const newFromWs = prev.filter(item => !apiSourceTitles.has(item.source))
                   return [...apiSources, ...newFromWs]
                 })
               }
               // 如果API没有数据，保留现有数据不变
             }).catch((error) => {
               console.error('重新获取任务详情失败:', error)
             })
           }
          } else if (msg.type === 'agent_subtask_update') {
           const rawType = (msg.agent_type || msg.agentType || '').toLowerCase()
           if (!rawType || !agentTypes[rawType as keyof typeof agentTypes]) return

           const key = rawType as keyof typeof agentTypes
           const sub = msg.sub_task || msg.subtask || msg.subTask
           if (!sub || sub.id === undefined || sub.id === null) return

           const subId = String(sub.id)
           const status = normalizeSubTaskStatus(sub.status || '')
           const newSubTask: SubTask = {
             id: subId,
             title: sub.title || sub.name || '子任务',
             status,
             startTime: sub.start_time || sub.startTime,
             endTime: sub.end_time || sub.endTime,
             result: sub.result || sub.output,
             detail: sub.detail || sub.description,
           }

           // 从消息中获取metrics信息
           const msgTokensUsed = Number(msg.tokens_used ?? 0)
           const msgApiCalls = Number(msg.api_calls ?? 0)
           const msgDuration = msg.duration || '-'

           // 更新Agent活动状态，包括metrics信息
           setAgentActivities((prev) => {
             return prev.map((a) => {
               if (a.agent !== key) return a

               const index = a.subTasks.findIndex((t) => t.id === subId)
               let subTasks: SubTask[]
               if (index === -1) {
                 // 新增子任务
                 subTasks = [...a.subTasks, newSubTask]
               } else {
                 // 更新现有子任务
                 subTasks = [...a.subTasks]
                 subTasks[index] = {
                   ...subTasks[index],
                   ...newSubTask,
                 }
               }

               // 更新metrics信息，使用最大值避免数据丢失
               const updatedMetrics = {
                 ...a.metrics,
                 tokensUsed: msgTokensUsed > 0
                   ? Math.max(msgTokensUsed, a.metrics.tokensUsed)
                   : a.metrics.tokensUsed,
                 apiCalls: msgApiCalls > 0
                   ? Math.max(msgApiCalls, a.metrics.apiCalls)
                   : a.metrics.apiCalls,
                 duration: msgDuration !== '-' ? msgDuration : a.metrics.duration,
               }

               return {
                 ...a,
                 subTasks,
                 metrics: updatedMetrics,
                 currentTask: sub.title || a.currentTask,
                 currentAction: status === 'running' ? (sub.title || a.currentAction) : a.currentAction,
               }
             })
           })
        }
      } catch (error) {
        console.error('解析WebSocket消息失败:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket错误:', error)
      if (!wsConnectedRef.current) {
        setError('实时连接出现异常，已自动降级为轮询模式')
      }
    }

    return () => {
      ws.close()
    }
  }, [taskId, numericTaskId])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
      case 'in_progress':
        return <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
      default:
        return <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
    }
  }

  const handleTogglePause = async () => {
    if (!taskId || Number.isNaN(numericTaskId)) return

    try {
      if (isPaused) {
        await resumeResearchTask(numericTaskId)
        setIsPaused(false)
      } else {
        await pauseResearchTask(numericTaskId)
        setIsPaused(true)
      }
    } catch (error) {
      console.error('更新任务状态失败:', error)
    }
  }

  const headerProgress =
    progress >= 100
      ? 100
      : stages.length > 0
      ? ((currentStage + 0.5) / stages.length) * 100
      : 0

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Top Progress Bar */}
      <div className="border-b bg-background px-4 py-3">
        <div className="max-w-6xl mx-auto">
          {/* 主标题行：研究问题 + 进度百分比 */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 flex-1 mr-4">
              {progress < 100 ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              )}
              <h1 className="font-medium truncate">{query}</h1>
            </div>
            <span className="text-sm font-mono text-primary">
              {isLoading ? '...' : `${Math.round(headerProgress)}%`}
            </span>
          </div>

          {/* 进度条 */}
          <div className="px-1">
            <Progress value={headerProgress} className="h-2" />

            {/* 阶段指示器 - 使用友好的文案 */}
            <div className="relative mt-3 h-5">
              {stages.map((stage, index) => {
                const isActive = index === currentStage
                const isCompleted = index < currentStage
                const left = ((index + 0.5) / stages.length) * 100
                const translateClass = '-translate-x-1/2'

                return (
                  <div
                    key={stage.id}
                    className={`absolute top-0 flex items-center gap-1.5 text-xs transition-all duration-300 whitespace-nowrap ${translateClass} ${
                      isActive
                        ? 'text-primary font-semibold scale-105'
                        : isCompleted
                        ? 'text-green-600'
                        : 'text-muted-foreground'
                    }`}
                    style={{ left: `${left}%` }}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : isActive ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <stage.icon className="h-3.5 w-3.5" />
                    )}
                    <span className={isActive ? 'animate-pulse' : ''}>{stage.name}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 当前阶段描述 - 动态显示正在做什么 */}
          {!error && progress < 100 && currentStage < stages.length && (
            <div className="mt-2 flex items-center gap-2 text-sm">
              <span className="text-primary font-medium">
                {/* 优先显示当前活跃Agent的具体子任务，否则显示阶段描述 */}
                {(() => {
                  const activeAgent = agentActivities.find(a => a.status === 'active')
                  const currentSubtask = activeAgent?.currentAction || activeAgent?.currentTask
                  // 过滤掉JSON格式的内容
                  if (currentSubtask && !currentSubtask.startsWith('{') && !currentSubtask.startsWith('[')) {
                    return currentSubtask
                  }
                  return stages[currentStage]?.description || '准备中...'
                })()}
              </span>
            </div>
          )}

          {/* 研究完成提示 */}
          {progress >= 100 && (
            <div className="mt-2 flex items-center gap-2 text-sm text-green-600 font-medium">
              <CheckCircle2 className="h-4 w-4" />
              研究完成，正在跳转到报告页面...
            </div>
          )}

          {/* 错误提示 */}
          {error && (
            <div className="mt-3 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5" />
              <div className="flex-1">
                <div className="font-medium">任务执行异常</div>
                <div className="mt-0.5 break-words">{error}</div>
              </div>
            </div>
          )}

 
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden px-4 pt-4 pb-4 lg:px-8 lg:pb-6">
        <div className="h-full w-full mx-auto flex gap-4 overflow-hidden">
          {/* Left Sidebar - Research Cockpit */}
          <div className="w-[340px] flex flex-col bg-muted/30 border rounded-lg">
            {/* Research Plan Tree */}
            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="p-4 border-b flex items-center justify-between">
                <h2 className="font-semibold flex items-center gap-2">
                  <BookOpen className="h-4 w-4" />
                  研究计划
                </h2>
                <span className="text-xs text-muted-foreground">
                  {plan.length > 0 ? `${totalPlanTasks}个任务` : '暂无任务'}
                </span>
              </div>
              <ScrollArea className="flex-1 p-3">
                <div className="space-y-1">
                  {plan.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin mb-2" />
                      <p className="text-sm">正在生成研究计划...</p>
                    </div>
                  ) : (
                    (() => {
                      let taskIndex = 0
                      return plan.map((item) => {
                        const itemIndex = taskIndex
                        const topStatus = computePlanStatus(itemIndex, totalPlanTasks, progress, agentActivities)
                        taskIndex += 1

                        return (
                          <div key={item.id} className="mb-2">
                            <div
                              className={`flex items-start gap-2 p-2 rounded-lg transition-colors ${
                                topStatus === 'in_progress'
                                  ? 'bg-primary/10 border border-primary/20'
                                  : topStatus === 'completed'
                                  ? 'bg-emerald-500/5 border border-emerald-500/40'
                                  : 'hover:bg-accent/50'
                              }`}
                            >
                              {getStatusIcon(topStatus)}
                              <span
                                className={`text-sm ${
                                  topStatus === 'in_progress'
                                    ? 'font-medium text-primary'
                                    : topStatus === 'completed'
                                    ? 'text-emerald-600'
                                    : ''
                                }`}
                              >
                                {item.title}
                              </span>
                            </div>
                            {item.children.length > 0 && (
                              <div className="ml-6 pl-3 border-l border-border/50 mt-1 space-y-0.5">
                                {item.children.map((child) => {
                                  const childIndex = taskIndex
                                    const childStatus = computePlanStatus(
                                      childIndex, totalPlanTasks, progress, agentActivities
                                    )
                                  taskIndex += 1

                                  return (
                                    <div
                                      key={child.id}
                                      className={`flex items-center gap-2 p-1.5 rounded text-sm ${
                                        childStatus === 'in_progress'
                                          ? 'text-primary font-medium'
                                          : childStatus === 'completed'
                                          ? 'text-emerald-600'
                                          : 'text-muted-foreground'
                                      }`}
                                    >
                                      {getStatusIcon(childStatus)}
                                      <span>{child.title}</span>
                                    </div>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        )
                      })
                    })()
                  )}
                </div>
              </ScrollArea>
            </div>

            <Separator />

            {/* Thinking Logs */}
            <div className="h-[220px] flex flex-col">
              <div className="p-3 border-b flex items-center justify-between">
                <h2 className="font-semibold text-sm flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" />
                  执行日志
                </h2>
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-xs text-muted-foreground">实时更新</span>
                </div>
              </div>
              <ScrollArea className="flex-1 p-3">
                <div className="space-y-1.5 font-mono text-xs">
                  {logs.map((log, index) => (
                    <div
                      key={index}
                      className={`flex gap-3 p-1.5 rounded transition-colors ${
                        index === logs.length - 1 ? 'bg-primary/5 border border-primary/20' : ''
                      }`}
                    >
                      <span className="text-muted-foreground shrink-0">[{log.time}]</span>
                      <span
                        className="flex-1 truncate"
                        title={log.content}
                      >
                        {log.content}
                      </span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              </ScrollArea>
            </div>

            <Separator />

            {/* Control Buttons */}
            <div className="p-3 flex gap-2">
              <Button
                variant={isPaused ? 'default' : 'outline'}
                className="flex-1 gap-2"
                onClick={handleTogglePause}
              >
                {isPaused ? (
                  <>
                    <Play className="h-4 w-4" /> 继续研究
                  </>
                ) : (
                  <>
                    <Pause className="h-4 w-4" /> 暂停
                  </>
                )}
              </Button>
              <Button variant="outline" size="icon">
                <Settings className="h-4 w-4" />
              </Button>
              <Button
                variant="destructive"
                size="icon"
                onClick={() => navigate('/')}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Right Main Area - Split View: Agent Workspace | Data Preview */}
          <div className="flex-1 flex overflow-hidden rounded-lg border bg-background">
            {/* Left Half - Agent Workspace */}
            <div className="flex-1 flex flex-col overflow-hidden border-r bg-muted/20">
              {/* Agent Status Summary Bar */}
              <div className="p-3 border-b bg-background flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bot className="h-4 w-4" />
                  <h2 className="font-semibold text-sm">智能助手状态</h2>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1">
                    <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                    {agentActivities.filter(a => a.status === 'active').length} 执行中
                  </span>
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    {agentActivities.filter(a => a.status === 'completed').length} 已完成
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    {agentActivities.filter(a => a.status === 'idle').length} 待执行
                  </span>
                </div>
              </div>

              {/* Agent Cards with Detailed Execution */}
              <ScrollArea className="flex-1 p-3">
                <div className="space-y-2">
                  {agentActivities.map((activity) => (
                    <AgentDetailCard
                      key={activity.id}
                      activity={activity}
                      isExpanded={expandedAgents.has(activity.id)}
                      onToggle={() => toggleAgentExpanded(activity.id)}
                    />
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Right Half - Data Preview */}
            <div className="flex-1 flex flex-col overflow-hidden bg-background">
              <div className="p-3 border-b flex items-center justify-between">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  数据提取预览
                </h3>
                <span className="text-xs text-muted-foreground">
                  {dataItems.length} 条记录
                </span>
              </div>
              <ScrollArea className="flex-1">
                <table className="w-full text-sm table-fixed">
                  <thead className="bg-muted/50 sticky top-0">
                    <tr className="border-b">
                      <th className="text-left p-2 font-medium w-40">来源</th>
                      <th className="text-left p-2 font-medium w-[50%]">关键信息</th>
                      <th className="text-left p-2 font-medium w-16">可信度</th>
                      <th className="text-left p-2 font-medium w-16">时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataItems.map((item, index) => (
                      <tr
                        key={index}
                        className="border-b last:border-0 hover:bg-muted/30"
                      >
                        <td className="p-2 font-medium text-xs whitespace-nowrap max-w-[10rem] overflow-hidden text-ellipsis">
                          {item.source}
                        </td>
                        <td className="p-2 text-muted-foreground text-xs align-top max-w-[32rem] break-words">
                          {item.info}
                        </td>
                        <td className="p-2">
                          <span
                            className={`inline-flex items-center gap-1 text-xs ${
                              item.confidence === 'high'
                                ? 'text-green-600'
                                : 'text-yellow-600'
                            }`}
                          >
                            {item.confidence === 'high' ? (
                              <CheckCircle2 className="h-3 w-3" />
                            ) : (
                              <AlertCircle className="h-3 w-3" />
                            )}
                            {item.confidence === 'high' ? '高' : '中'}
                          </span>
                        </td>
                        <td className="p-2 text-xs text-muted-foreground whitespace-nowrap">
                          {item.time}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollArea>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
