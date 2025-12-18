import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Trash2,
  Search,
  Clock,
  CheckCircle,
  XCircle,
  PauseCircle,
  ChevronLeft,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  getResearchTasks,
  deleteResearchTask,
  type ResearchTask,
  type TaskStatus,
} from '@/services/api'

interface ExtendedResearchTask extends ResearchTask {
  checked?: boolean
}

export default function HistoryView() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<ExtendedResearchTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStatus, setSelectedStatus] = useState<TaskStatus | 'all'>('all')
  const [selectedTasks, setSelectedTasks] = useState<number[]>([])
  const [isDeleting, setIsDeleting] = useState(false)
  const [totalCount, setTotalCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(0)
  const [pageSize] = useState(20)

  // 这个SB函数初始化时加载任务列表
  useEffect(() => {
    loadTasks()
  }, [currentPage])

  // 这个臭小子函数负责加载任务列表
  const loadTasks = async () => {
    try {
      setIsLoading(true)
      const response = await getResearchTasks({
        skip: currentPage * pageSize,
        limit: pageSize,
        status: selectedStatus === 'all' ? undefined : selectedStatus,
      })
      // 给任务加上checked字段，用于批量选择
      const extendedTasks = response.items.map((task) => ({
        ...task,
        checked: selectedTasks.includes(task.id),
      }))
      setTasks(extendedTasks)
      setTotalCount(response.total)
    } catch (error) {
      console.error('艹，加载任务列表出错了:', error)
      alert('加载任务列表失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }

  // 这个流程实现搜索功能，在本地过滤任务列表
  const handleSearch = async () => {
    try {
      // 如果搜索框为空，就重新加载任务
      if (!searchQuery.trim()) {
        setCurrentPage(0)
        await loadTasks()
        return
      }

      // 艹！搜索时先加载所有任务，然后在本地过滤
      setIsLoading(true)
      const response = await getResearchTasks({
        skip: 0,
        limit: 1000, // 一次加载最多1000条，基本够用了
        status: selectedStatus === 'all' ? undefined : selectedStatus,
      })
      const filteredTasks = response.items
        .filter((task) =>
          task.query.toLowerCase().includes(searchQuery.toLowerCase())
        )
        .map((task) => ({
          ...task,
          checked: selectedTasks.includes(task.id),
        }))
      setTasks(filteredTasks)
      setTotalCount(filteredTasks.length)
      setCurrentPage(0)
    } catch (error) {
      console.error('搜索任务出错:', error)
      alert('搜索任务失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }

  // 这个憨批函数处理单个删除
  const handleDelete = async (taskId: number) => {
    if (!confirm('你真要删除这条历史记录？删除后不可恢复啊老兄！')) {
      return
    }

    try {
      setIsDeleting(true)
      await deleteResearchTask(taskId)
      // 刷新列表
      setSelectedTasks(selectedTasks.filter((id) => id !== taskId))
      await loadTasks()
    } catch (error) {
      console.error('删除任务出错:', error)
      alert('删除任务失败，请重试')
    } finally {
      setIsDeleting(false)
    }
  }

  // 这个臭玩意儿处理批量删除
  const handleBatchDelete = async () => {
    if (selectedTasks.length === 0) {
      alert('没选中任何记录，怎么删呢？')
      return
    }

    if (
      !confirm(
        `你真要批量删除 ${selectedTasks.length} 条历史记录？我警告你，删除后不可恢复啊！`
      )
    ) {
      return
    }

    try {
      setIsDeleting(true)
      // 并发删除所有选中的任务
      await Promise.all(
        selectedTasks.map((taskId) => deleteResearchTask(taskId))
      )
      // 清空选择
      setSelectedTasks([])
      // 刷新列表
      await loadTasks()
    } catch (error) {
      console.error('批量删除任务出错:', error)
      alert('批量删除任务失败，请重试')
    } finally {
      setIsDeleting(false)
    }
  }

  // 这个函数切换单个选择
  const toggleTaskSelection = (taskId: number) => {
    setSelectedTasks((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    )
  }

  // 这个憨批函数切换全选
  const toggleSelectAll = () => {
    if (selectedTasks.length === tasks.length) {
      // 如果全选了，就全部取消
      setSelectedTasks([])
    } else {
      // 否则全选当前页的任务
      setSelectedTasks(tasks.map((task) => task.id))
    }
  }

  // 这个SB函数用于格式化状态显示
  const formatStatus = (status: TaskStatus) => {
    const statusMap: Record<TaskStatus, string> = {
      completed: '已完成',
      pending: '等待中',
      planning: '规划中',
      searching: '搜索中',
      curating: '筛选中',
      analyzing: '分析中',
      writing: '写作中',
      citing: '引用中',
      reviewing: '审核中',
      failed: '失败',
      paused: '已暂停',
    }
    return statusMap[status] || status
  }

  // 这个流程获取状态的样式类
  const getStatusColor = (status: TaskStatus) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
      case 'failed':
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
      case 'paused':
        return 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
      default:
        return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
    }
  }

  // 这个臭函数获取状态图标
  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4" />
      case 'failed':
        return <XCircle className="h-4 w-4" />
      case 'paused':
        return <PauseCircle className="h-4 w-4" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  // 这个函数格式化时间，别tm来问老子为什么这样写
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

  // 这个憨批函数计算总页数
  const totalPages = Math.ceil(totalCount / pageSize)

  return (
    <div className="container max-w-6xl py-8 px-4">
      {/* 返回按钮和标题 */}
      <div className="flex items-center gap-3 mb-6">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(-1)}
          className="h-8 w-8"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-3xl font-bold">研究历史</h1>
      </div>

      {/* 搜索和筛选栏 */}
      <div className="flex gap-4 mb-6 flex-wrap">
        <div className="flex-1 min-w-64">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Input
                type="text"
                placeholder="搜索研究题目..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pr-10"
              />
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            </div>
            <Button onClick={handleSearch} disabled={isLoading} size="sm">
              搜索
            </Button>
          </div>
        </div>

        {/* 状态筛选 */}
        <div className="flex gap-2">
          {['all', 'completed', 'failed', 'paused', 'planning'].map(
            (status) => (
              <Button
                key={status}
                variant={selectedStatus === status ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setSelectedStatus(status as TaskStatus | 'all')
                  setCurrentPage(0)
                }}
              >
                {status === 'all'
                  ? '全部'
                  : formatStatus(status as TaskStatus)}
              </Button>
            )
          )}
        </div>
      </div>

      {/* 批量操作栏 */}
      {selectedTasks.length > 0 && (
        <Card className="mb-6 bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">
                已选择 {selectedTasks.length} 条记录
              </div>
              <div className="flex gap-2">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleBatchDelete}
                  disabled={isDeleting}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  {isDeleting ? '删除中...' : '批量删除'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedTasks([])}
                >
                  取消选择
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 历史记录列表 */}
      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">
          加载中，老子正在摸鱼...
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          还没有研究历史，开始第一次研究吧！
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {/* 表头 */}
            <div className="grid grid-cols-12 gap-3 px-4 py-2 text-xs font-semibold text-muted-foreground">
              <div className="col-span-1 flex items-center">
                <input
                  type="checkbox"
                  checked={selectedTasks.length === tasks.length && tasks.length > 0}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-gray-300 cursor-pointer"
                />
              </div>
              <div className="col-span-6">研究题目</div>
              <div className="col-span-2">状态</div>
              <div className="col-span-2">创建时间</div>
              <div className="col-span-1 text-right">操作</div>
            </div>

            {/* 任务列表 */}
            {tasks.map((task) => (
              <Card
                key={task.id}
                className="hover:bg-accent/50 transition-colors cursor-pointer"
                onClick={() => {
                  if (task.status === 'completed') {
                    navigate(`/report/${task.id}`)
                  } else {
                    navigate(`/process/${task.id}`)
                  }
                }}
              >
                <CardContent className="p-0">
                  <div className="grid grid-cols-12 gap-3 p-4 items-center">
                    {/* 复选框 */}
                    <div
                      className="col-span-1 flex items-center"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTasks.includes(task.id)}
                        onChange={() => toggleTaskSelection(task.id)}
                        className="h-4 w-4 rounded border-gray-300 cursor-pointer"
                      />
                    </div>

                    {/* 题目 */}
                    <div className="col-span-6 min-w-0">
                      <h3 className="font-medium truncate text-sm">{task.query}</h3>
                      {task.summary && (
                        <p className="text-xs text-muted-foreground truncate mt-1">
                          {task.summary}
                        </p>
                      )}
                    </div>

                    {/* 状态 */}
                    <div className="col-span-2">
                      <div
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}
                      >
                        {getStatusIcon(task.status)}
                        <span>{formatStatus(task.status)}</span>
                      </div>
                    </div>

                    {/* 创建时间 */}
                    <div className="col-span-2 text-xs text-muted-foreground">
                      {formatTime(task.created_at)}
                    </div>

                    {/* 操作按钮 */}
                    <div
                      className="col-span-1 flex justify-end gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDelete(task.id)
                        }}
                        disabled={isDeleting}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 分页控制 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0 || isLoading}
              >
                上一页
              </Button>
              <div className="text-sm text-muted-foreground">
                第 {currentPage + 1} / {totalPages} 页
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
                disabled={currentPage >= totalPages - 1 || isLoading}
              >
                下一页
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
