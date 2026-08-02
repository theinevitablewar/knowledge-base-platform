import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Col, Form, Input, Modal, Row, Select, Tag, Typography, message } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { resources } from '../api/resources'

export function KnowledgeBasesPage() {
  const navigate = useNavigate(), client = useQueryClient(), [open,setOpen] = useState(false)
  const query = useQuery({queryKey:['knowledge-bases'], queryFn:resources.knowledgeBases})
  const workspaces = useQuery({queryKey:['workspaces'], queryFn:resources.workspaces})
  const create = useMutation({mutationFn:(body:object)=>api.post('/knowledge-bases',body), onSuccess:()=>{void client.invalidateQueries({queryKey:['knowledge-bases']});setOpen(false);message.success('知识库已创建')},onError:(e)=>message.error(errorMessage(e))})
  return <><div className="page-heading"><div><Typography.Title level={2}>知识库</Typography.Title><Typography.Text type="secondary">按工作空间组织文档、权限与检索策略</Typography.Text></div><Button type="primary" icon={<PlusOutlined/>} onClick={()=>setOpen(true)}>新建知识库</Button></div><Row gutter={[16,16]}>{query.data?.map((item)=><Col xs={24} md={12} xl={8} key={item.id}><Card hoverable onClick={()=>navigate(`/knowledge-bases/${item.id}`)} title={item.name} extra={<Tag color={item.status==='active'?'green':'default'}>{item.status}</Tag>}><Typography.Paragraph ellipsis={{rows:2}}>{item.description || '暂无描述'}</Typography.Paragraph><div className="kb-meta"><span>{item.visibility}</span><span>{item.chunk_size} / {item.chunk_overlap}</span></div></Card></Col>)}</Row><Modal title="创建知识库" open={open} footer={null} onCancel={()=>setOpen(false)}><Form layout="vertical" onFinish={(v)=>create.mutate(v)} initialValues={{visibility:'members',chunk_size:800,chunk_overlap:120}}><Form.Item name="workspace_id" label="工作空间" rules={[{required:true}]}><Select options={workspaces.data?.map((w)=>({value:w.id,label:w.name}))}/></Form.Item><Form.Item name="name" label="名称" rules={[{required:true}]}><Input/></Form.Item><Form.Item name="description" label="描述"><Input.TextArea/></Form.Item><Form.Item name="visibility" label="可见范围"><Select options={['private','members','workspace','tenant'].map(v=>({value:v,label:v}))}/></Form.Item><Button type="primary" htmlType="submit" loading={create.isPending}>创建</Button></Form></Modal></>
}
