import { useQuery } from '@tanstack/react-query'
import { Progress, Table, Tag, Typography } from 'antd'
import { resources } from '../api/resources'

export function TasksPage() {
  const query = useQuery({queryKey:['tasks'],queryFn:resources.tasks,refetchInterval:3000})
  return <><div className="page-heading"><div><Typography.Title level={2}>任务中心</Typography.Title><Typography.Text type="secondary">跟踪解析、分块、向量化和删除任务</Typography.Text></div></div><Table rowKey="id" loading={query.isLoading} dataSource={query.data} columns={[{title:'类型',dataIndex:'task_type'},{title:'阶段',dataIndex:'current_stage'},{title:'进度',dataIndex:'progress',render:(v:number)=><Progress percent={v} size="small"/>},{title:'状态',dataIndex:'status',render:(v:string)=><Tag color={v==='completed'?'green':v==='failed'?'red':'blue'}>{v}</Tag>},{title:'错误',dataIndex:'error_message'}]}/></>
}
