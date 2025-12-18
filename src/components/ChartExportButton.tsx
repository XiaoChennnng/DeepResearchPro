/**
 * 图表导出按钮组件
 * 提供 PDF/WORD 导出功能
 */

import { useRef, useState } from 'react'
import { Download, FileText, File } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  exportChartToPDF,
  exportChartToWord,
  exportChartsToPDF,
  exportChartsToWord,
} from '@/services/chartExporter'

interface ChartExportButtonProps {
  chartElement?: HTMLElement | null
  chartTitle?: string
  fileName?: string
  mode?: 'single' | 'batch'
  onBeforeExport?: () => void
  onAfterExport?: () => void
  onError?: (error: Error) => void
}

/**
 * 单个图表导出按钮
 */
export function ChartExportButton({
  chartElement,
  chartTitle = '图表',
  fileName = 'chart',
  onBeforeExport,
  onAfterExport,
  onError,
}: ChartExportButtonProps) {
  const [isLoading, setIsLoading] = useState(false)

  const handleExportPDF = async () => {
    if (!chartElement) {
      onError?.(new Error('没有图表可导出'))
      return
    }

    try {
      setIsLoading(true)
      onBeforeExport?.()
      await exportChartToPDF(chartElement, `${fileName}.pdf`)
      onAfterExport?.()
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('导出失败'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleExportWord = async () => {
    if (!chartElement) {
      onError?.(new Error('没有图表可导出'))
      return
    }

    try {
      setIsLoading(true)
      onBeforeExport?.()
      await exportChartToWord(chartElement, chartTitle, `${fileName}.docx`)
      onAfterExport?.()
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('导出失败'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={isLoading || !chartElement}
          className="gap-2"
        >
          <Download className="h-4 w-4" />
          {isLoading ? '导出中...' : '导出'}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handleExportPDF} disabled={isLoading}>
          <FileText className="h-4 w-4 mr-2" />
          导出为 PDF
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleExportWord} disabled={isLoading}>
          <File className="h-4 w-4 mr-2" />
          导出为 WORD
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * 批量图表导出按钮
 */
export function ChartsBatchExportButton({
  chartElements,
  fileName = 'charts',
  onBeforeExport,
  onAfterExport,
  onError,
}: {
  chartElements: HTMLElement[]
  fileName?: string
  onBeforeExport?: () => void
  onAfterExport?: () => void
  onError?: (error: Error) => void
}) {
  const [isLoading, setIsLoading] = useState(false)

  const handleExportPDF = async () => {
    if (chartElements.length === 0) {
      onError?.(new Error('没有图表可导出'))
      return
    }

    try {
      setIsLoading(true)
      onBeforeExport?.()
      await exportChartsToPDF(chartElements, `${fileName}.pdf`)
      onAfterExport?.()
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('导出失败'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleExportWord = async () => {
    if (chartElements.length === 0) {
      onError?.(new Error('没有图表可导出'))
      return
    }

    try {
      setIsLoading(true)
      onBeforeExport?.()
      const chartsData = chartElements.map((element, index) => ({
        element,
        title: `图表 ${index + 1}`,
      }))
      await exportChartsToWord(chartsData, `${fileName}.docx`)
      onAfterExport?.()
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('导出失败'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={isLoading || chartElements.length === 0}
          className="gap-2"
        >
          <Download className="h-4 w-4" />
          {isLoading ? '导出中...' : `导出 (${chartElements.length})`}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handleExportPDF} disabled={isLoading}>
          <FileText className="h-4 w-4 mr-2" />
          导出为 PDF
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleExportWord} disabled={isLoading}>
          <File className="h-4 w-4 mr-2" />
          导出为 WORD
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * 高级导出按钮（可配置的导出选项）
 */
export function AdvancedChartExportButton({
  chartElement,
  chartTitle = '图表',
  fileName = 'chart',
  onBeforeExport,
  onAfterExport,
  onError,
}: ChartExportButtonProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleExport = async (format: 'pdf' | 'docx') => {
    const element = chartElement || chartRef.current
    if (!element) {
      onError?.(new Error('没有图表可导出'))
      return
    }

    try {
      setIsLoading(true)
      onBeforeExport?.()

      if (format === 'pdf') {
        await exportChartToPDF(element, `${fileName}.pdf`)
      } else {
        await exportChartToWord(element, chartTitle, `${fileName}.docx`)
      }

      onAfterExport?.()
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('导出失败'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div ref={chartRef} className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => handleExport('pdf')}
        disabled={isLoading}
        className="gap-2"
      >
        <FileText className="h-4 w-4" />
        PDF
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => handleExport('docx')}
        disabled={isLoading}
        className="gap-2"
      >
        <File className="h-4 w-4" />
        WORD
      </Button>
    </div>
  )
}
