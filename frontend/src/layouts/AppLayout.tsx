import { DatabaseOutlined, DashboardOutlined, LogoutOutlined, UnorderedListOutlined } from '@ant-design/icons'
import { Button, Layout, Menu, Typography } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../stores/auth'

const { Header, Sider, Content } = Layout
export function AppLayout() {
  const navigate = useNavigate(), location = useLocation(), logout = useAuth((state) => state.logout)
  return <Layout className="app-shell">
    <Sider width={236} theme="light" className="sidebar">
      <div className="brand"><span className="brand-mark">K</span><div><b>Knowledge Base</b><small>Enterprise RAG</small></div></div>
      <Menu mode="inline" selectedKeys={[location.pathname.split('/').slice(0, 2).join('/') || '/']} onClick={({key}) => navigate(key)} items={[
        {key: '/', icon: <DashboardOutlined/>, label: '仪表盘'},
        {key: '/knowledge-bases', icon: <DatabaseOutlined/>, label: '知识库'},
        {key: '/tasks', icon: <UnorderedListOutlined/>, label: '任务中心'},
      ]}/>
      <Button className="logout" type="text" icon={<LogoutOutlined/>} onClick={() => { logout(); navigate('/login') }}>退出登录</Button>
    </Sider>
    <Layout><Header className="topbar"><Typography.Text strong>知识库管理平台</Typography.Text><Typography.Text type="secondary">安全、多租户、可观测</Typography.Text></Header><Content className="content"><Outlet/></Content></Layout>
  </Layout>
}
