import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Mic,
  Upload,
  FileText,
  Clock,
  ChevronRight,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { getResearchTasks, createResearchTask, type ResearchTask } from '@/services/api'

// 仪表板页面组件
export default function Dashboard() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [recentResearch, setRecentResearch] = useState<ResearchTask[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isCreating, setIsCreating] = useState(false)

  // 初始化时加载最近的研究任务
  useEffect(() => {
    loadRecentResearch()
  }, [])

  // 加载最近的研究任务
  const loadRecentResearch = async () => {
    try {
      setIsLoading(true)
      const response = await getResearchTasks({ limit: 3 })
      setRecentResearch(response.items)
    } catch (error) {
      console.error('加载研究任务失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  // 开始新的研究任务
  const handleStartResearch = async () => {
    if (!query.trim()) return

    try {
      setIsCreating(true)
      const task = await createResearchTask({ query: query.trim() })
      navigate(`/process/${task.id}`)
    } catch (error) {
      console.error('创建研究任务失败:', error)
      alert('创建研究任务失败，请重试')
    } finally {
      setIsCreating(false)
    }
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    console.log('Dropped files:', files)
  }, [])

  const formatStatus = (status: string) => {
    const statusMap: Record<string, string> = {
      completed: '已完成',
      pending: '等待中',
      planning: '规划中',
      researching: '研究中',
      analyzing: '分析中',
      writing: '写作中',
      failed: '失败',
      paused: '已暂停',
    }
    return statusMap[status] || status
  }

  const formatTime = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="container max-w-4xl py-8 px-4">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-4">
          开始一次<span className="text-primary">深度研究</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          告诉我你想研究什么，我会自主规划研究路径、搜索信息、验证数据，并生成深度研究报告
        </p>
      </div>

      <div className="max-w-3xl mx-auto mb-12">
        <div className="relative">
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="例如：分析电动汽车电池技术2024年的降本路径，包括技术突破、供应链优化和规模效应..."
            className="min-h-[120px] pr-4 text-base resize-none"
            disabled={isCreating}
          />
          <div className="absolute bottom-3 right-3 flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="h-3 w-3" />
            <span>支持复杂研究问题</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 mt-4">
          <Button
            size="lg"
            onClick={handleStartResearch}
            disabled={!query.trim() || isCreating}
            className="gap-2"
          >
            <Search className="h-4 w-4" />
            {isCreating ? '创建中...' : '开始研究'}
          </Button>
          <Button variant="outline" size="lg" className="gap-2" disabled>
            <Mic className="h-4 w-4" />
            语音输入
          </Button>
          <Button variant="outline" size="lg" className="gap-2" disabled>
            <Upload className="h-4 w-4" />
            上传文件
          </Button>
        </div>

        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`mt-4 border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
            isDragging
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-muted-foreground/50'
          }`}
        >
          <FileText className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            拖拽文件到此处，支持 PDF、Word、Excel、图片等格式
          </p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">最近研究</h2>
          <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/history')}>
            查看全部
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            加载中...
          </div>
        ) : recentResearch.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            还没有研究任务，开始第一次研究吧！
          </div>
        ) : (
          <div className="space-y-3">
            {recentResearch.map((research) => (
              <Card
                key={research.id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => {
                  if (research.status === 'completed') {
                    navigate(`/report/${research.id}`)
                  } else {
                    navigate(`/process/${research.id}`)
                  }
                }}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium truncate">{research.query}</h3>
                      <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span>{formatTime(research.created_at)}</span>
                        {research.progress > 0 && (
                          <span className="ml-2">进度: {research.progress}%</span>
                        )}
                      </div>
                    </div>
                    <div
                      className={`shrink-0 px-2 py-1 rounded-full text-xs font-medium ${
                        research.status === 'completed'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : research.status === 'failed'
                          ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                      }`}
                    >
                      {formatStatus(research.status)}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
