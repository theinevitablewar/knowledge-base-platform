import { useQuery } from '@tanstack/react-query'
import { Card, Col, Row, Statistic, Table, Typography } from 'antd'
import { resources } from '../api/resources'

export function DashboardPage() {
  const knowledge = useQuery({queryKey:['knowledge-bases'], queryFn:resources.knowledgeBases})
  const tasks = useQuery({queryKey:['tasks'], queryFn:resources.tasks, refetchInterval:5000})
  const failed = tasks.data?.filter((item) => item.status === 'failed').length ?? 0
  const pending = tasks.data?.filter((item) => ['queued','processing'].includes(item.status)).length ?? 0
  return <><div className="page-heading"><div><Typography.Title level={2}>仪表盘</Typography.Title><Typography.Text type="secondary">查看知识资产和处理任务的实时状态</Typography.Text></div></div><Row gutter={[16,16]}><Col xs={24} md={8}><Card><Statistic title="知识库" value={knowledge.data?.length ?? 0}/></Card></Col><Col xs={24} md={8}><Card><Statistic title="处理中任务" value={pending}/></Card></Col><Col xs={24} md={8}><Card><Statistic title="失败任务" value={failed} valueStyle={{color:failed?'#dc2626':undefined}}/></Card></Col></Row><Card className="section-card" title="最近任务"><Table rowKey="id" loading={tasks.isLoading} dataSource={tasks.data?.slice(0,8)} pagination={false} columns={[{title:'类型',dataIndex:'task_type'},{title:'阶段',dataIndex:'current_stage'},{title:'进度',dataIndex:'progress',render:(v:number)=>`${v}%`},{title:'状态',dataIndex:'status'}]}/></Card></>
}
