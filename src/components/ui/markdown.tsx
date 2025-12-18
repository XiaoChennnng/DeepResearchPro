import * as React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import { cn } from '@/lib/utils'
import { ChartComponent } from './chart'

interface MarkdownProps {
  content: string
  className?: string
}

interface ContentBlock {
  type: 'markdown' | 'chart'
  content: string
  chart?: any
}

/**
 * Parse Markdown content with embedded chart definitions
 * Extracts chart definitions like <!--CHART:type {...} CHART:type-->
 */
function parseContentWithCharts(content: string): ContentBlock[] {
  const chartRegex = /<!--CHART:(\w+)\s*([\s\S]*?)\s*CHART:\1-->/g
  const blocks: ContentBlock[] = []
  let lastIndex = 0
  let match

  while ((match = chartRegex.exec(content)) !== null) {
    // Add markdown block before this chart
    if (match.index > lastIndex) {
      blocks.push({
        type: 'markdown',
        content: content.substring(lastIndex, match.index),
      })
    }

    // Parse and add chart block
    const chartType = match[1]
    const jsonStr = match[2]
    try {
      const chartData = JSON.parse(jsonStr)
      blocks.push({
        type: 'chart',
        content: '',
        chart: {
          chart_type: chartType,
          title: chartData.title || '图表',
          description: chartData.description,
          data: chartData,
          section: 'embedded',
          order: blocks.length,
        },
      })
    } catch (e) {
      console.error('Failed to parse chart definition:', e)
    }

    lastIndex = match.index + match[0].length
  }

  // Add remaining markdown
  if (lastIndex < content.length) {
    blocks.push({
      type: 'markdown',
      content: content.substring(lastIndex),
    })
  }

  return blocks.length > 0 ? blocks : [{ type: 'markdown', content }]
}

/**
 * Process citation markers [1], [2], etc. and convert them to styled spans
 * that can link to the references section
 */
function processCitations(content: string): string {
  // Match citation patterns like [1], [2], [1-3], [1][2], etc.
  // Convert them to HTML spans with special styling
  return content.replace(
    /\[(\d+(?:-\d+)?)\]/g,
    '<sup class="citation-ref"><a href="#ref-$1" class="citation-link">[$1]</a></sup>'
  )
}

/**
 * Professional Markdown renderer with full GFM support
 * Supports: tables, task lists, strikethrough, code highlighting, citations, embedded charts, etc.
 */
export function Markdown({ content, className }: MarkdownProps) {
  // Parse content to separate markdown and chart blocks
  const contentBlocks = parseContentWithCharts(content)

  const slugify = (value: string) =>
    value
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fa5\s-]/g, '')
      .replace(/\s+/g, '-')

  const getTextFromChildren = (children: React.ReactNode): string => {
    const nodes = React.Children.toArray(children)
    return nodes
      .map((child) => {
        if (typeof child === 'string') return child
        if (React.isValidElement(child)) {
          const inner = (child.props as any).children
          if (typeof inner === 'string') return inner
          if (Array.isArray(inner)) {
            return inner
              .map((v: unknown) => (typeof v === 'string' ? v : ''))
              .join('')
          }
        }
        return ''
      })
      .join(' ')
      .trim()
  }

  return (
    <div className={cn('markdown-body', className)}>
      {contentBlocks.map((block, index) => {
        if (block.type === 'markdown') {
          // Process citations in markdown blocks
          const processedContent = processCitations(block.content)

          return (
            <React.Fragment key={index}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight, rehypeRaw]}
                components={{
                  // Custom heading styles with anchor ids
                  h1: ({ children }) => {
                    const text = getTextFromChildren(children)
                    const id = text ? slugify(text) : undefined
                    return (
                      <h1 id={id} className="text-3xl font-bold mt-8 mb-4 pb-2 border-b">
                        {children}
                      </h1>
                    )
                  },
                  h2: ({ children }) => {
                    const text = getTextFromChildren(children)
                    const id = text ? slugify(text) : undefined
                    return (
                      <h2 id={id} className="text-2xl font-semibold mt-6 mb-3">
                        {children}
                      </h2>
                    )
                  },
                  h3: ({ children }) => {
                    const text = getTextFromChildren(children)
                    const id = text ? slugify(text) : undefined
                    return (
                      <h3 id={id} className="text-xl font-medium mt-4 mb-2">
                        {children}
                      </h3>
                    )
                  },
                  h4: ({ children }) => {
                    const text = getTextFromChildren(children)
                    const id = text ? slugify(text) : undefined
                    return (
                      <h4 id={id} className="text-lg font-medium mt-3 mb-2">
                        {children}
                      </h4>
                    )
                  },
                  // Paragraph
                  p: ({ children }) => (
                    <p className="my-3 leading-7">{children}</p>
                  ),
                  // Lists
                  ul: ({ children }) => (
                    <ul className="my-3 ml-6 list-disc space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="my-3 ml-6 list-decimal space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => (
                    <li className="leading-7">{children}</li>
                  ),
                  // Blockquote
                  blockquote: ({ children }) => (
                    <blockquote className="my-4 pl-4 border-l-4 border-primary/50 italic text-muted-foreground">
                      {children}
                    </blockquote>
                  ),
                  // Code blocks
                  pre: ({ children }) => (
                    <pre className="my-4 p-4 rounded-lg bg-muted overflow-x-auto text-sm">
                      {children}
                    </pre>
                  ),
                  code: ({ className, children, ...props }) => {
                    const isInline = !className
                    if (isInline) {
                      return (
                        <code className="px-1.5 py-0.5 rounded bg-muted text-sm font-mono" {...props}>
                          {children}
                        </code>
                      )
                    }
                    return (
                      <code className={cn('font-mono', className)} {...props}>
                        {children}
                      </code>
                    )
                  },
                  // Tables
                  table: ({ children }) => (
                    <div className="my-4 overflow-x-auto">
                      <table className="w-full border-collapse border border-border rounded-lg">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-muted/50">{children}</thead>
                  ),
                  tbody: ({ children }) => (
                    <tbody className="divide-y divide-border">{children}</tbody>
                  ),
                  tr: ({ children }) => (
                    <tr className="border-b border-border">{children}</tr>
                  ),
                  th: ({ children }) => (
                    <th className="px-4 py-2 text-left font-semibold border-r border-border last:border-r-0">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="px-4 py-2 border-r border-border last:border-r-0">
                      {children}
                    </td>
                  ),
                  // Links
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {children}
                    </a>
                  ),
                  // Horizontal rule
                  hr: () => <hr className="my-6 border-border" />,
                  // Strong and emphasis
                  strong: ({ children }) => (
                    <strong className="font-semibold">{children}</strong>
                  ),
                  em: ({ children }) => (
                    <em className="italic">{children}</em>
                  ),
                  // Images
                  img: ({ src, alt }) => (
                    <img
                      src={src}
                      alt={alt}
                      className="my-4 rounded-lg max-w-full h-auto"
                    />
                  ),
                }}
              >
                {processedContent}
              </ReactMarkdown>
            </React.Fragment>
          )
        } else if (block.type === 'chart' && block.chart) {
          // Render chart block
          return (
            <div key={index} className="my-6">
              <ChartComponent chart={block.chart} />
            </div>
          )
        }

        return null
      })}
    </div>
  )
}
