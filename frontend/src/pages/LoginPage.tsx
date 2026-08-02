import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { useAuth } from '../stores/auth'

export function LoginPage() {
  const navigate = useNavigate(), setTokens = useAuth((state) => state.setTokens)
  const [error, setError] = useState(''), [loading, setLoading] = useState(false)
  const submit = async (values: {username: string; password: string}) => {
    setLoading(true); setError('')
    try { const {data} = await api.post('/auth/login', values); setTokens(data.access_token, data.refresh_token); navigate('/') }
    catch (reason) { setError(errorMessage(reason)) } finally { setLoading(false) }
  }
  return <main className="login-page"><Card className="login-card"><div className="login-title"><span className="brand-mark large">K</span><Typography.Title level={2}>知识库平台</Typography.Title><Typography.Text type="secondary">登录后管理企业知识与 RAG 服务</Typography.Text></div>{error && <Alert type="error" showIcon message={error}/>}<Form layout="vertical" onFinish={submit} initialValues={{username: 'admin', password: 'admin123456'}}><Form.Item name="username" label="用户名" rules={[{required:true}]}><Input prefix={<UserOutlined/>} size="large"/></Form.Item><Form.Item name="password" label="密码" rules={[{required:true}]}><Input.Password prefix={<LockOutlined/>} size="large"/></Form.Item><Button htmlType="submit" type="primary" size="large" block loading={loading}>登录</Button></Form><Typography.Text className="dev-hint" type="secondary">开发默认：admin / admin123456</Typography.Text></Card></main>
}
