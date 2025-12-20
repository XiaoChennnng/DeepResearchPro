/**
 * 图表导出工具
 */

import jsPDF from 'jspdf'
// @ts-ignore
import html2canvas from 'html2canvas'
import { Document, Packer, Paragraph, PageBreak, TextRun } from 'docx'

/** 将图表容器转换为Canvas */
export async function chartToCanvas(element: HTMLElement): Promise<HTMLCanvasElement> {
  const canvas = await html2canvas(element, {
    logging: false,
    scale: 2,
    backgroundColor: '#ffffff',
  } as any)
  return canvas
}

/** 导出单个图表为PDF */
export async function exportChartToPDF(
  chartElement: HTMLElement,
  fileName: string = 'chart.pdf'
): Promise<void> {
  try {
    const canvas = await chartToCanvas(chartElement)
    const imgData = canvas.toDataURL('image/png')

    const pdf = new jsPDF({
      orientation: canvas.width > canvas.height ? 'landscape' : 'portrait',
      unit: 'mm',
      format: 'a4',
    })

    const width = pdf.internal.pageSize.getWidth()
    const height = pdf.internal.pageSize.getHeight()

    // 计算图片缩放比例以适应页面
    const imgWidth = canvas.width
    const imgHeight = canvas.height
    const ratio = imgWidth / imgHeight

    let finalWidth = width - 10
    let finalHeight = finalWidth / ratio

    if (finalHeight > height - 10) {
      finalHeight = height - 10
      finalWidth = finalHeight * ratio
    }

    const x = (width - finalWidth) / 2
    const y = (height - finalHeight) / 2

    pdf.addImage(imgData, 'PNG', x, y, finalWidth, finalHeight)
    pdf.save(fileName)
  } catch (error) {
    console.error('导出 PDF 失败:', error)
    throw new Error('导出 PDF 失败')
  }
}

/**
 * 导出多个图表为 PDF
 */
export async function exportChartsToPDF(
  chartElements: HTMLElement[],
  fileName: string = 'charts.pdf'
): Promise<void> {
  try {
    if (chartElements.length === 0) {
      throw new Error('没有图表可导出')
    }

    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    })

    const width = pdf.internal.pageSize.getWidth()
    const height = pdf.internal.pageSize.getHeight()

    for (let i = 0; i < chartElements.length; i++) {
      if (i > 0) {
        pdf.addPage()
      }

      const canvas = await chartToCanvas(chartElements[i])
      const imgData = canvas.toDataURL('image/png')

      const imgWidth = canvas.width
      const imgHeight = canvas.height
      const ratio = imgWidth / imgHeight

      let finalWidth = width - 10
      let finalHeight = finalWidth / ratio

      if (finalHeight > height - 10) {
        finalHeight = height - 10
        finalWidth = finalHeight * ratio
      }

      const x = (width - finalWidth) / 2
      const y = (height - finalHeight) / 2

      pdf.addImage(imgData, 'PNG', x, y, finalWidth, finalHeight)
    }

    pdf.save(fileName)
  } catch (error) {
    console.error('导出 PDF 失败:', error)
    throw new Error('导出 PDF 失败')
  }
}

/**
 * 导出图表为 WORD 文档
 */
export async function exportChartToWord(
  chartElement: HTMLElement,
  chartTitle: string = '图表',
  fileName: string = 'chart.docx'
): Promise<void> {
  try {
    await chartToCanvas(chartElement)

    const doc = new Document({
      sections: [
        {
          children: [
            new Paragraph({
              text: chartTitle,
              spacing: {
                after: 200,
              },
            }),
            new Paragraph({
              children: [
                new TextRun({
                  text: '', // 占位符
                }),
              ],
            }),
          ],
        },
      ],
    })

    await Packer.toBlob(doc).then((blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName
      link.click()
      URL.revokeObjectURL(url)
    })
  } catch (error) {
    console.error('导出 WORD 失败:', error)
    throw new Error('导出 WORD 失败')
  }
}

/**
 * 导出多个图表为 WORD 文档
 */
export async function exportChartsToWord(
  chartsData: Array<{ element: HTMLElement; title?: string }>,
  fileName: string = 'charts.docx'
): Promise<void> {
  try {
    if (chartsData.length === 0) {
      throw new Error('没有图表可导出')
    }

    const children: any[] = []

    for (let i = 0; i < chartsData.length; i++) {
      const { element, title } = chartsData[i]

      if (title) {
        children.push(
          new Paragraph({
            text: title,
            spacing: {
              before: i > 0 ? 400 : 0,
              after: 200,
            },
          })
        )
      }

      const canvas = await chartToCanvas(element)
      // 为了使用 canvas 定义，虽然在此处暂不使用
      void canvas

      // 创建图表占位符（Word 中需要特殊处理图片）
      children.push(
        new Paragraph({
          text: '[图表]',
          spacing: {
            after: 200,
          },
        })
      )

      if (i < chartsData.length - 1) {
        children.push(new PageBreak())
      }
    }

    const doc = new Document({
      sections: [
        {
          children,
        },
      ],
    })

    await Packer.toBlob(doc).then((blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName
      link.click()
      URL.revokeObjectURL(url)
    })
  } catch (error) {
    console.error('导出 WORD 失败:', error)
    throw new Error('导出 WORD 失败')
  }
}

/**
 * 导出完整报告（包含文本和图表）为 PDF
 */
export async function exportReportToPDF(
  title: string,
  content: string,
  chartElements: HTMLElement[] = [],
  fileName: string = 'report.pdf'
): Promise<void> {
  try {
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    })

    const width = pdf.internal.pageSize.getWidth()
    const height = pdf.internal.pageSize.getHeight()
    const margin = 10
    const contentWidth = width - 2 * margin

    // 添加标题
    pdf.setFontSize(16)
    pdf.text(title, margin, margin + 10)

    // 添加内容
    pdf.setFontSize(10)
    const splitContent = pdf.splitTextToSize(content, contentWidth)
    let currentY = margin + 30

    for (const line of splitContent) {
      if (currentY > height - margin - 20) {
        pdf.addPage()
        currentY = margin
      }
      pdf.text(line, margin, currentY)
      currentY += 5
    }

    // 添加图表
    for (let i = 0; i < chartElements.length; i++) {
      pdf.addPage()
      const canvas = await chartToCanvas(chartElements[i])
      const imgData = canvas.toDataURL('image/png')

      const imgWidth = canvas.width
      const imgHeight = canvas.height
      const ratio = imgWidth / imgHeight

      let finalWidth = width - 2 * margin
      let finalHeight = finalWidth / ratio

      if (finalHeight > height - 2 * margin) {
        finalHeight = height - 2 * margin
        finalWidth = finalHeight * ratio
      }

      const x = (width - finalWidth) / 2
      const y = margin

      pdf.addImage(imgData, 'PNG', x, y, finalWidth, finalHeight)
    }

    pdf.save(fileName)
  } catch (error) {
    console.error('导出报告 PDF 失败:', error)
    throw new Error('导出报告 PDF 失败')
  }
}
