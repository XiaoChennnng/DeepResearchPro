import { Outlet } from 'react-router-dom'
import { Navbar } from './navbar'
import { ThemeProvider } from './theme-provider'
import { TooltipProvider } from '@/components/ui/tooltip'

export function AppLayout() {
  return (
    <ThemeProvider>
      <TooltipProvider>
        <div className="relative min-h-screen flex flex-col bg-background">
          <Navbar />
          <main className="flex-1">
            <Outlet />
          </main>
        </div>
      </TooltipProvider>
    </ThemeProvider>
  )
}
