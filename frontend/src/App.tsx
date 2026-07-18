import { createBrowserRouter } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [],
  },
])

export default router
