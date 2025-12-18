import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppLayout } from '@/components/layout'
import Dashboard from '@/pages/Dashboard'
import ProcessView from '@/pages/ProcessView'
import ReportView from '@/pages/ReportView'
import HistoryView from '@/pages/History'
import LoginPage from '@/pages/Login'
import AccountPage from '@/pages/Account'
import { RequireAuth } from './require-auth'

// 路由配置

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: 'process/:taskId',
        element: (
          <RequireAuth>
            <ProcessView />
          </RequireAuth>
        ),
      },
      {
        path: 'report/:reportId',
        element: (
          <RequireAuth>
            <ReportView />
          </RequireAuth>
        ),
      },
      {
        path: 'history',
        element: (
          <RequireAuth>
            <HistoryView />
          </RequireAuth>
        ),
      },
      {
        path: 'account',
        element: (
          <RequireAuth>
            <AccountPage />
          </RequireAuth>
        ),
      },
      {
        path: 'settings',
        element: <div className="container py-8"><h1 className="text-2xl font-bold">设置</h1><p className="text-muted-foreground mt-2">暂未实现</p></div>,
      },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
