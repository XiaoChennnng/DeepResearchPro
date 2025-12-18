import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ScatterChart,
  Scatter,
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import React from 'react'

export interface ChartData {
  id?: number
  chart_type: string
  title: string
  description?: string | null
  data: any
  config?: any
  section: string
  order: number
  created_by_agent?: string
  created_at?: string
}

interface ChartComponentProps {
  chart: ChartData
  className?: string
  onExport?: (format: 'pdf' | 'docx') => void
}

// Professional color palette for academic charts
const ACADEMIC_COLORS = [
  '#2563eb', // Primary blue
  '#059669', // Emerald green
  '#d97706', // Amber
  '#dc2626', // Red
  '#7c3aed', // Purple
  '#0891b2', // Cyan
  '#4f46e5', // Indigo
  '#be185d', // Pink
]

// Custom tooltip style for better readability
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-3 text-sm">
        <p className="font-medium text-foreground mb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ color: entry.color }} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span>{entry.name}:</span>
            <span className="font-semibold">{typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}</span>
          </p>
        ))}
      </div>
    )
  }
  return null
}

export function ChartComponent({ chart, className = '', onExport }: ChartComponentProps) {
  const chartContainerRef = React.useRef<HTMLDivElement>(null)

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!chartContainerRef.current) return

    try {
      const { exportChartToPDF, exportChartToWord } = await import('@/services/chartExporter')

      if (format === 'pdf') {
        await exportChartToPDF(chartContainerRef.current, `${chart.title}.pdf`)
      } else {
        await exportChartToWord(chartContainerRef.current, chart.title, `${chart.title}.docx`)
      }

      onExport?.(format)
    } catch (error) {
      console.error('导出失败:', error)
    }
  }

  const renderChart = () => {
    const { chart_type, data, config } = chart
    const colors = config?.colors || ACADEMIC_COLORS

    switch (chart_type) {
      case 'bar':
        // 柱状图数据验证和转换
        const barData = data.series ? transformBarData(data) : data

        if (!barData || (Array.isArray(barData) && barData.length === 0)) {
          return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              柱状图数据为空
            </div>
          )
        }

        return (
          <BarChart data={barData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              angle={-45}
              textAnchor="end"
              height={60}
              interval={0}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={{ stroke: '#d1d5db' }}
              tickLine={{ stroke: '#d1d5db' }}
              domain={['dataMin - 5%', 'dataMax + 5%']}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
            />
            {data.series ? (
              data.series.map((series: any, index: number) => (
                <Bar
                  key={index}
                  dataKey={series.dataKey || series.name}
                  name={series.name}
                  fill={colors[index % colors.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))
            ) : (
              <Bar dataKey="value" fill={colors[0]} radius={[4, 4, 0, 0]} />
            )}
          </BarChart>
        )

      case 'line':
        // 折线图数据验证和转换
        const lineData = data.series ? transformBarData(data) : data

        if (!lineData || (Array.isArray(lineData) && lineData.length === 0)) {
          return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              折线图数据为空
            </div>
          )
        }

        return (
          <LineChart data={lineData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              angle={-45}
              textAnchor="end"
              height={60}
              interval={0}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={{ stroke: '#d1d5db' }}
              tickLine={{ stroke: '#d1d5db' }}
              domain={['dataMin - 5%', 'dataMax + 5%']}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
            />
            {data.series ? (
              data.series.map((series: any, index: number) => (
                <Line
                  key={index}
                  type="monotone"
                  dataKey={series.dataKey || series.name}
                  name={series.name}
                  stroke={colors[index % colors.length]}
                  strokeWidth={2.5}
                  dot={config?.show_markers !== false ? { r: 5, fill: colors[index % colors.length], strokeWidth: 2, stroke: '#fff' } : false}
                  activeDot={{ r: 7, fill: colors[index % colors.length], strokeWidth: 2, stroke: '#fff' }}
                />
              ))
            ) : (
              <Line
                type="monotone"
                dataKey="value"
                stroke={colors[0]}
                strokeWidth={2.5}
                dot={{ r: 5, fill: colors[0], strokeWidth: 2, stroke: '#fff' }}
                activeDot={{ r: 7 }}
              />
            )}
          </LineChart>
        )

      case 'pie':
        // 饼图数据处理：支持多种格式
        let pieData: Array<{ name: string; value: number }> = []

        // 格式1: { labels: [...], series: [...] }
        if (data.labels && Array.isArray(data.labels) && Array.isArray(data.series)) {
          pieData = data.labels.map((label: string, index: number) => ({
            name: label,
            value: typeof data.series[index] === 'number' ? data.series[index] : 0,
          }))
        }
        // 格式2: { series: [{ name: '...', value: ... }, ...] }
        else if (Array.isArray(data.series) && data.series.length > 0 && typeof data.series[0] === 'object') {
          pieData = data.series.map((item: any, index: number) => ({
            name: item.name || item.label || `数据${index + 1}`,
            value: typeof item.value === 'number' ? item.value : (typeof item.data === 'number' ? item.data : 0),
          }))
        }
        // 格式3: { series: [10, 20, 30, ...] } 纯数值数组
        else if (Array.isArray(data.series) && data.series.length > 0 && typeof data.series[0] === 'number') {
          pieData = data.series.map((value: number, index: number) => ({
            name: `数据${index + 1}`,
            value: value,
          }))
        }
        // 格式4: 直接是数组
        else if (Array.isArray(data) && data.length > 0) {
          pieData = data.map((item: any, index: number) => {
            if (typeof item === 'object') {
              return {
                name: item.name || item.label || `数据${index + 1}`,
                value: typeof item.value === 'number' ? item.value : 0,
              }
            }
            return { name: `数据${index + 1}`, value: typeof item === 'number' ? item : 0 }
          })
        }

        // 过滤掉值为 0 或负数的数据
        pieData = pieData.filter(item => item.value > 0)

        // 数据验证
        if (!pieData || pieData.length === 0) {
          return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              饼图数据为空或格式错误
            </div>
          )
        }

        return (
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              labelLine={{ stroke: '#9ca3af', strokeWidth: 1 }}
              label={({ name, percent, x, y, midAngle }) => {
                const RADIAN = Math.PI / 180
                const cos = Math.cos(-RADIAN * midAngle)
                const textAnchor = cos >= 0 ? 'start' : 'end'

                return (
                  <text
                    x={x}
                    y={y}
                    textAnchor={textAnchor}
                    fill="#374151"
                    fontSize={11}
                    fontWeight={500}
                  >
                    {`${name} (${(percent * 100).toFixed(1)}%)`}
                  </text>
                )
              }}
              outerRadius={85}
              innerRadius={40}
              paddingAngle={2}
              dataKey="value"
            >
              {pieData.map((_entry: any, index: number) => (
                <Cell
                  key={`cell-${index}`}
                  fill={colors[index % colors.length]}
                  stroke="#fff"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              layout="horizontal"
              align="center"
              verticalAlign="bottom"
              formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
            />
          </PieChart>
        )

      case 'radar':
        // 雷达图数据转换：确保有 indicators 和 series 数据
        const radarData = data.indicators?.map((indicator: any, index: number) => ({
          subject: indicator.name || `指标${index + 1}`,
          A: data.series?.[0]?.data?.[index] || 0,
          fullMark: indicator.max || 100,
        })) || (Array.isArray(data.series?.[0]?.data) ? data.series[0].data.map((value: any, index: number) => ({
          subject: `指标${index + 1}`,
          A: value,
          fullMark: 100,
        })) : [])

        // 如果没有有效数据，返回空图表提示
        if (!radarData || radarData.length === 0) {
          return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              雷达图数据格式错误或数据为空
            </div>
          )
        }

        return (
          <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis
              dataKey="subject"
              tick={{ fontSize: 11, fill: '#6b7280' }}
            />
            <PolarRadiusAxis
              angle={30}
              domain={[0, getRadarMaxValue(radarData)]}
              tick={{ fontSize: 10, fill: '#9ca3af' }}
              axisLine={false}
            />
            <Radar
              name={data.series?.[0]?.name || '评分'}
              dataKey="A"
              stroke={colors[0]}
              fill={colors[0]}
              fillOpacity={0.25}
              strokeWidth={2}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
            />
          </RadarChart>
        )

      case 'scatter':
        // 散点图：用于展示两个变量之间的相关性
        // 支持两种数据格式：
        // 1. 直接数据数组: [{x: 1, y: 2}, {x: 3, y: 4}, ...]
        // 2. Series 格式: {series: [{name: 'A', data: [{x: 1, y: 2}, ...]}, ...]}

        let scatterData: any = []
        let useSeriesFormat = false

        if (Array.isArray(data)) {
          // 格式1：直接数据数组
          scatterData = data
        } else if (data.series && Array.isArray(data.series)) {
          // 格式2：Series 格式
          useSeriesFormat = true
        } else if (data.data && Array.isArray(data.data)) {
          // 格式3：data 字段
          scatterData = data.data
        }

        // 验证数据有效性
        if ((!useSeriesFormat && (!scatterData || scatterData.length === 0))) {
          return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              散点图数据为空
            </div>
          )
        }

        return (
          <ScatterChart
            data={useSeriesFormat ? [] : scatterData}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey={data.xKey || 'x'}
              type="number"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              name={data.xLabel || 'X轴'}
              domain={['dataMin - 5%', 'dataMax + 5%']}
            />
            <YAxis
              dataKey={data.yKey || 'y'}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              name={data.yLabel || 'Y轴'}
              domain={['dataMin - 5%', 'dataMax + 5%']}
            />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              content={<CustomTooltip />}
            />
            <Legend
              formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
            />
            {useSeriesFormat && data.series ? (
              data.series.map((series: any, index: number) => (
                <Scatter
                  key={index}
                  name={series.name || `数据系列${index + 1}`}
                  dataKey={series.dataKey || `y${index}`}
                  data={series.data || []}
                  fill={colors[index % colors.length]}
                />
              ))
            ) : (
              <Scatter
                name="数据点"
                dataKey="value"
                fill={colors[0]}
              />
            )}
          </ScatterChart>
        )

      case 'area':
        // 面积图：用于展示时间序列数据和累积趋势
        // 面积图需要标准的柱状/折线格式数据（带 name 和数值字段）
        const areaData = Array.isArray(data) ? data : (data.categories ? transformBarData(data) : data)

        // 验证数据有效性
        if (!areaData || areaData.length === 0) {
          return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              面积图数据为空
            </div>
          )
        }

        return (
          <AreaChart
            data={areaData}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
          >
            <defs>
              {colors.map((color: string, index: number) => (
                <linearGradient id={`colorArea${index}`} x1="0" y1="0" x2="0" y2="1" key={index}>
                  <stop offset="5%" stopColor={color} stopOpacity={0.7}/>
                  <stop offset="95%" stopColor={color} stopOpacity={0}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              angle={-45}
              textAnchor="end"
              height={60}
              interval={0}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={{ stroke: '#d1d5db' }}
              tickLine={{ stroke: '#d1d5db' }}
              domain={['dataMin - 5%', 'dataMax + 5%']}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
            />
            {data.series ? (
              data.series.map((series: any, index: number) => (
                <Area
                  key={index}
                  type="monotone"
                  dataKey={series.dataKey || series.name}
                  name={series.name}
                  stackId="stack"
                  stroke={colors[index % colors.length]}
                  fill={`url(#colorArea${index % colors.length})`}
                  strokeWidth={2}
                />
              ))
            ) : (
              <Area
                type="monotone"
                dataKey="value"
                stackId="stack"
                stroke={colors[0]}
                fill={`url(#colorArea0)`}
                strokeWidth={2}
              />
            )}
          </AreaChart>
        )

      default:
        return (
          <div className="flex items-center justify-center h-64 text-muted-foreground">
            不支持的图表类型: {chart_type}
          </div>
        )

    }
  }

  return (
    <div ref={chartContainerRef} className={`bg-card rounded-lg border shadow-sm ${className}`}>
      {/* Chart Header */}
      <div className="p-4 border-b">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h3 className="text-base font-semibold text-foreground">{chart.title}</h3>
            {chart.description && (
              <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{chart.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2 ml-4">
            <button
              onClick={() => handleExport('pdf')}
              title="导出为 PDF"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            >
              PDF
            </button>
            <button
              onClick={() => handleExport('docx')}
              title="导出为 WORD"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            >
              WORD
            </button>
            <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded ml-2">
              {chart.section}
            </span>
          </div>
        </div>
      </div>

      {/* Chart Body */}
      <div className="p-4">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            {renderChart()}
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart Footer */}
      <div className="px-4 pb-3 pt-2 border-t bg-muted/30">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            数据来源：DeepResearch Pro 分析引擎
          </span>
          {chart.created_at && (
            <span>
              生成于 {new Date(chart.created_at).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
              })}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// 数据转换函数：将 { categories, series } 转换为 Recharts 格式
function transformBarData(data: any): any[] {
  const { categories = [], series = [] } = data

  if (!Array.isArray(categories) || categories.length === 0) {
    return []
  }

  return categories.map((category: string, index: number) => {
    const item: any = { name: category }

    series.forEach((s: any) => {
      const dataKey = s.dataKey || s.name
      item[dataKey] = s.data?.[index] || 0
    })

    return item
  })
}

// Helper functions for automatic scale adjustment
function getRadarMaxValue(radarData: any) {
  if (!Array.isArray(radarData) || radarData.length === 0) {
    return 100
  }

  let maxValue = 0
  radarData.forEach((item: any) => {
    if (item.A && typeof item.A === 'number') {
      maxValue = Math.max(maxValue, item.A)
    }
  })

  // 向上舍入到最近的合适值
  if (maxValue <= 50) return 50
  if (maxValue <= 100) return Math.ceil(maxValue / 10) * 10
  if (maxValue <= 500) return Math.ceil(maxValue / 50) * 50
  return Math.ceil(maxValue / 100) * 100
}