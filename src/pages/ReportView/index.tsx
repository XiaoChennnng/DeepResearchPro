import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Download,
  Share2,
  RefreshCw,
  ExternalLink,
  MessageSquare,
  Loader2,
  Send,
  FileText,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Markdown } from '@/components/ui/markdown'
import { ChartComponent } from '@/components/ui/chart'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu'
import {
  getResearchTask,
  exportReport,
  askReportQuestion,
  type ResearchTaskDetail,
  type ReportQAHistoryItem,
} from '@/services/api'

// Floating Q&A input component
function FloatingQuestionInput({
  isHidden,
  question,
  onQuestionChange,
  onSubmit
}: {
  isHidden: boolean
  question: string
  onQuestionChange: (value: string) => void
  onSubmit: () => void
}) {
  return (
    <div
      className={`absolute bottom-6 left-1/2 -translate-x-1/2 z-10 transition-all duration-300 ease-in-out ${
        isHidden
          ? 'opacity-0 translate-y-4 pointer-events-none'
          : 'opacity-100 translate-y-0'
      }`}
    >
      <div className="flex items-center gap-2 bg-background/95 backdrop-blur-sm border shadow-lg rounded-full px-4 py-2 min-w-[400px]">
        <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
        <Input
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          placeholder="对报告有疑问？在这里追问..."
          className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 px-0"
          onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
        />
        <Button
          size="sm"
          className="rounded-full shrink-0 h-8 w-8 p-0"
          onClick={onSubmit}
          disabled={!question.trim()}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

type TocItem = {
  id: string
  title: string
  level: number
}

function buildTocFromMarkdown(content: string): TocItem[] {
  const lines = content.split('\n')
  const toc: TocItem[] = []

  for (const line of lines) {
    const match = /^(#{1,6})\s+(.+)$/.exec(line.trim())
    if (!match) continue

    const level = match[1].length
    const title = match[2].trim()
    const id = title
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fa5\s-]/g, '')
      .replace(/\s+/g, '-')

    toc.push({ id, title, level })
  }

  return toc
}

export default function ReportView() {
  const navigate = useNavigate()
  const { reportId } = useParams<{ reportId: string }>()
  const [question, setQuestion] = useState('')
  const [qaOpen, setQaOpen] = useState(false)
  const [qaMessages, setQaMessages] = useState<
    { id: string; role: 'user' | 'assistant'; content: string }[]
  >([])
  const [qaLoading, setQaLoading] = useState(false)
  const [qaError, setQaError] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState('summary')
  const [isAtBottom, setIsAtBottom] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [task, setTask] = useState<ResearchTaskDetail | null>(null)
  const [toc, setToc] = useState<TocItem[]>([])
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const ask = async (rawQuestion: string) => {
    if (!task) return
    const q = rawQuestion.trim()
    if (!q) return

    const userMessage = {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      role: 'user' as const,
      content: q,
    }

    setQaOpen(true)
    setQaError(null)
    setQaMessages((prev) => [...prev, userMessage])
    setQuestion('')
    setQaLoading(true)

    try {
      const history: ReportQAHistoryItem[] = [...qaMessages, userMessage]
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }))

      const resp = await askReportQuestion(task.id, q, history)

      const assistantMessage = {
        id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
        role: 'assistant' as const,
        content: resp.answer,
      }

      setQaMessages((prev) => [...prev, assistantMessage])
    } catch (e) {
      const message = e instanceof Error ? e.message : '生成回答失败，请稍后重试'
      setQaError(message)
    } finally {
      setQaLoading(false)
    }
  }

  const handleAskQuestion = () => {
    void ask(question)
  }

  const handleExport = async (format: 'pdf' | 'word' | 'markdown') => {
    if (!task) return

    try {
      const blob = await exportReport(task.id, format, true)

      // 创建下载链接
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url

      const extension = format === 'markdown' ? 'md' : format === 'word' ? 'docx' : 'pdf'
      a.download = `research_report_${task.id}.${extension}`

      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('导出失败:', error)
      alert('导出失败，请稍后重试')
    }
  }

  // Check if scrolled to bottom
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return

    const scrollTop = container.scrollTop
    const scrollHeight = container.scrollHeight
    const clientHeight = container.clientHeight

    // Consider "at bottom" when within 50px of the bottom
    const atBottom = scrollHeight - scrollTop - clientHeight < 50
    setIsAtBottom(atBottom)
  }, [])

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    container.addEventListener('scroll', handleScroll)
    // Initial check
    handleScroll()

    return () => container.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  useEffect(() => {
    const id = reportId ? Number(reportId) : NaN
    if (!reportId || Number.isNaN(id)) return

    let cancelled = false

    const load = async () => {
      try {
        setIsLoading(true)
        setError(null)
        const detail = await getResearchTask(id)
        if (cancelled) return

        setTask(detail)

        if (detail.report_content) {
          const generatedToc = buildTocFromMarkdown(detail.report_content)
          setToc(generatedToc)
          if (generatedToc.length > 0) {
            setActiveSection(generatedToc[0].id)
          }
        }
      } catch (e) {
        if (cancelled) return
        setError('加载报告失败，请稍后重试')
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [reportId])

  const handleTocClick = (item: TocItem) => {
    setActiveSection(item.id)

    const container = scrollContainerRef.current
    if (!container) return

    const target = document.getElementById(item.id)
    if (!target) return

    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()

    const offset = targetRect.top - containerRect.top + container.scrollTop - 16

    container.scrollTo({
      top: offset,
      behavior: 'smooth',
    })
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] flex">
      {/* Left Sidebar - TOC */}
      <div className="w-[240px] border-r flex flex-col bg-muted/30">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm">目录</h2>
        </div>
        <ScrollArea className="flex-1 p-2">
          <div className="space-y-1">
            {toc.length === 0 && (
              <div className="px-3 py-2 text-xs text-muted-foreground">
                暂无结构化目录
              </div>
            )}
            {toc.map((item) => (
              <button
                key={item.id}
                onClick={() => handleTocClick(item)}
                className={`w-full text-left px-3 py-1.5 rounded text-sm transition-colors ${
                  item.level >= 2 ? 'pl-6' : ''
                } ${
                  activeSection === item.id
                    ? 'bg-primary/10 text-primary font-medium'
                    : 'hover:bg-accent text-muted-foreground hover:text-foreground'
                }`}
              >
                {item.title}
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Top Action Bar */}
        <div className="border-b px-6 py-3 flex items-center justify-between bg-background">
          <h1 className="font-semibold truncate flex-1 mr-4">
            {task?.query || '研究报告'}
          </h1>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <Download className="h-4 w-4" />
                  导出
                </Button>
              </DropdownMenuTrigger>
               <DropdownMenuContent>
                 <DropdownMenuItem onClick={() => handleExport('markdown')}>
                   <FileText className="h-4 w-4 mr-2" /> Markdown
                 </DropdownMenuItem>
                 <DropdownMenuItem onClick={() => handleExport('pdf')}>
                   <FileText className="h-4 w-4 mr-2" /> PDF
                 </DropdownMenuItem>
                 <DropdownMenuItem onClick={() => handleExport('word')}>
                   <FileText className="h-4 w-4 mr-2" /> Word
                 </DropdownMenuItem>
               </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="outline" className="gap-2">
              <Share2 className="h-4 w-4" />
              分享
            </Button>
            <Button variant="outline" className="gap-2" onClick={() => navigate('/')}>
              <RefreshCw className="h-4 w-4" />
              重新研究
            </Button>
          </div>
        </div>

        {/* Report Content with scroll detection */}
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto"
        >
          <div className="max-w-3xl mx-auto py-8 px-6">
            {isLoading && (
              <div className="py-12 text-center text-muted-foreground">
                报告加载中...
              </div>
            )}

            {!isLoading && error && (
              <div className="py-12 text-center text-red-500 text-sm">
                {error}
              </div>
            )}

            {!isLoading && !error && task && (
              <>
                {/* 图表展示区域 */}
                {task.charts && task.charts.length > 0 && (
                  <div className="mb-8">
                    <h2 className="text-xl font-semibold mb-4">数据图表</h2>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {task.charts
                        .sort((a, b) => a.order - b.order)
                        .map((chart) => (
                          <ChartComponent key={chart.id} chart={chart} />
                        ))}
                    </div>
                  </div>
                )}

                {task.report_content && (
                  <Markdown content={task.report_content} />
                )}

                <div className="mt-12 mb-20">
                  <h2 className="text-xl font-semibold mb-4">参考来源</h2>
                  {task.sources.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      暂无结构化来源记录。
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {task.sources.map((src, index) => (
                        <div key={src.id} className="flex items-start gap-2 text-sm">
                          <span className="text-muted-foreground">[{index + 1}]</span>
                          <div>
                            <div className="flex items-center gap-1">
                              <span className="font-medium line-clamp-2">{src.title}</span>
                              {src.url && (
                                <a
                                  href={src.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary hover:underline flex items-center gap-1 text-xs"
                                >
                                  打开
                                  <ExternalLink className="h-3 w-3" />
                                </a>
                              )}
                            </div>
                            {src.content && (
                              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                {src.content}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {qaOpen && (
          <div className="absolute inset-0 z-20 flex items-end justify-center pointer-events-none">
            <div className="pointer-events-auto w-[min(820px,calc(100%-2rem))] mb-6">
              <Card className="bg-background/95 backdrop-blur-sm border shadow-xl">
                <CardContent className="p-0">
                  <div className="flex items-center justify-between px-4 py-3 border-b">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <MessageSquare className="h-4 w-4 text-muted-foreground" />
                      追问报告
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => setQaOpen(false)}
                      disabled={qaLoading}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  <div className="h-[320px]">
                    <ScrollArea className="h-full">
                      <div className="p-4 space-y-3">
                        {qaMessages.length === 0 && (
                          <div className="text-sm text-muted-foreground">
                            输入你的问题，我会结合本报告内容进行回答。
                          </div>
                        )}

                        {qaMessages.map((m) => (
                          <div
                            key={m.id}
                            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                                m.role === 'user'
                                  ? 'bg-primary text-primary-foreground'
                                  : 'bg-muted text-foreground'
                              }`}
                            >
                              {m.content}
                            </div>
                          </div>
                        ))}

                        {qaLoading && (
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            正在生成回答...
                          </div>
                        )}

                        {qaError && (
                          <div className="text-xs text-destructive">{qaError}</div>
                        )}
                      </div>
                    </ScrollArea>
                  </div>

                  <div className="px-4 py-3 border-t">
                    <div className="flex items-center gap-2">
                      <Input
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        placeholder="对报告有疑问？在这里追问..."
                        className="bg-transparent"
                        onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                        disabled={qaLoading}
                      />
                      <Button
                        className="rounded-full shrink-0 h-9 w-9 p-0"
                        onClick={handleAskQuestion}
                        disabled={qaLoading || !question.trim()}
                      >
                        {qaLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Send className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Floating Q&A Input - hides when at bottom */}
        {!qaOpen && (
          <FloatingQuestionInput
            isHidden={isAtBottom}
            question={question}
            onQuestionChange={setQuestion}
            onSubmit={handleAskQuestion}
          />
        )}
      </div>

      {/* Right Sidebar - Sources only */}
      <div className="w-[280px] border-l flex flex-col bg-muted/30">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm">来源引用</h2>
        </div>
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-3">
            {task && task.sources.length > 0 ? (
              task.sources.map((src, index) => (
                <Card key={src.id} className="cursor-pointer hover:bg-accent/50">
                  <CardContent className="p-3">
                    <div className="flex items-start gap-2">
                      <span className="text-xs text-muted-foreground shrink-0">[{index + 1}]</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium break-words">{src.title}</p>
                        {src.url && (
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-primary hover:underline mt-1 break-all block"
                          >
                            {src.url}
                          </a>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <div className="text-xs text-muted-foreground">
                暂无来源记录
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
