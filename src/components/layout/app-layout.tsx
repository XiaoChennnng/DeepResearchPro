import { Outlet } from 'react-router-dom'
import { Navbar } from './navbar'
import { ThemeProvider } from './theme-provider'
import { TooltipProvider } from '@/components/ui/tooltip'

export function AppLayout() {
  return (
    <ThemeProvider>
      <TooltipProvider>
        <div className="relative min-h-screen flex flex-col bg-background">
          {/* 顶部导航栏 */}
          <Navbar />
          {/* 主要内容区域 */}
          <main className="flex-1">
            <Outlet />
          </main>
        </div>
      </TooltipProvider>
    </ThemeProvider>
  )
}
