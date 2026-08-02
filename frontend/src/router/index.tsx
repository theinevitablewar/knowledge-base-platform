import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import { DashboardPage } from '../pages/DashboardPage'
import { KnowledgeBaseDetailPage } from '../pages/KnowledgeBaseDetailPage'
import { KnowledgeBasesPage } from '../pages/KnowledgeBasesPage'
import { LoginPage } from '../pages/LoginPage'
import { TasksPage } from '../pages/TasksPage'
import { useAuth } from '../stores/auth'

function Guard() { return useAuth.getState().accessToken ? <AppLayout/> : <Navigate to="/login" replace/> }
export const router = createBrowserRouter([
  {path:'/login',element:<LoginPage/>},
  {path:'/',element:<Guard/>,children:[
    {index:true,element:<DashboardPage/>},
    {path:'knowledge-bases',element:<KnowledgeBasesPage/>},
    {path:'knowledge-bases/:id',element:<KnowledgeBaseDetailPage/>},
    {path:'tasks',element:<TasksPage/>},
  ]},
])
