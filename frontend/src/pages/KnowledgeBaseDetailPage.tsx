import { DeleteOutlined, InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Descriptions, Drawer, Form, Input, InputNumber, List, Select, Space, Switch, Table, Tabs, Tag, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useParams } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { resources } from '../api/resources'
import type { Chunk, SearchResult } from '../types'

const statusColor: Record<string,string> = {ready:'green',failed:'red',disabled:'default',queued:'blue',parsing:'gold',chunking:'gold',embedding:'purple',indexing:'purple'}

export function KnowledgeBaseDetailPage() {
  const {id = ''} = useParams(), client = useQueryClient(), [selectedDoc,setSelectedDoc] = useState('')
  const knowledge = useQuery({queryKey:['knowledge-base',id],queryFn:async()=>(await api.get(`/knowledge-bases/${id}`)).data})
  const documents = useQuery({queryKey:['documents',id],queryFn:()=>resources.documents(id),refetchInterval:4000})
  const chunks = useQuery({queryKey:['chunks',selectedDoc],queryFn:()=>resources.chunks(selectedDoc),enabled:Boolean(selectedDoc)})
  const refresh = () => void client.invalidateQueries({queryKey:['documents',id]})
  const upload: UploadProps['customRequest'] = async (option) => { const data = new FormData(); data.append('files', option.file as File); try { await api.post(`/knowledge-bases/${id}/documents`,data); option.onSuccess?.({});message.success('已上传，后台正在处理');refresh() } catch(e){option.onError?.(e as Error);message.error(errorMessage(e))} }
  const action = useMutation({mutationFn:({doc,verb}:{doc:string;verb:string})=>verb==='delete'?api.delete(`/documents/${doc}`):api.post(`/documents/${doc}/${verb}`),onSuccess:refresh,onError:(e)=>message.error(errorMessage(e))})
  const items = [
    {key:'overview',label:'概览',children:<Descriptions bordered column={2} items={[{key:'name',label:'名称',children:knowledge.data?.name},{key:'status',label:'状态',children:knowledge.data?.status},{key:'visibility',label:'可见范围',children:knowledge.data?.visibility},{key:'chunk',label:'分块参数',children:`${knowledge.data?.chunk_size} / ${knowledge.data?.chunk_overlap}`}]}/>},
    {key:'documents',label:'文档',children:<><Upload.Dragger multiple accept=".pdf,.docx,.txt,.md,.markdown" customRequest={upload} showUploadList={false}><p className="ant-upload-drag-icon"><InboxOutlined/></p><p>拖拽或点击上传 PDF、DOCX、TXT、Markdown</p><p className="ant-upload-hint">上传后由 Celery 异步解析和索引</p></Upload.Dragger><Table className="section-card" rowKey="id" dataSource={documents.data} loading={documents.isLoading} columns={[{title:'文件',dataIndex:'original_name'},{title:'状态',dataIndex:'status',render:(v:string)=><Tag color={statusColor[v]}>{v}</Tag>},{title:'页/Chunk',render:(_,r)=>`${r.page_count} / ${r.chunk_count}`},{title:'启用',render:(_,r)=><Switch checked={r.enabled} onChange={(on)=>action.mutate({doc:r.id,verb:on?'enable':'disable'})}/>},{title:'操作',render:(_,r)=><Space><Button icon={<ReloadOutlined/>} onClick={()=>action.mutate({doc:r.id,verb:'reindex'})}/><Button danger icon={<DeleteOutlined/>} onClick={()=>action.mutate({doc:r.id,verb:'delete'})}/></Space>}]}/></>},
    {key:'chunks',label:'Chunk',children:<ChunkPanel documents={documents.data ?? []} selected={selectedDoc} onSelect={setSelectedDoc} chunks={chunks.data ?? []}/>},
    {key:'retrieval',label:'检索测试',children:<RetrievalPanel knowledgeBaseId={id}/>},
    {key:'answer',label:'问答测试',children:<AnswerPanel knowledgeBaseId={id}/>},
    {key:'members',label:'成员权限',children:<MembersPanel knowledgeBaseId={id}/>},
    {key:'settings',label:'检索配置与设置',children:<SettingsPanel knowledgeBaseId={id} initial={knowledge.data} onSaved={()=>void client.invalidateQueries({queryKey:['knowledge-base',id]})}/>},
  ]
  return <><div className="page-heading"><div><Typography.Title level={2}>{knowledge.data?.name ?? '知识库'}</Typography.Title><Typography.Text type="secondary">{knowledge.data?.description}</Typography.Text></div></div><Card><Tabs items={items}/></Card></>
}

function ChunkPanel({documents,selected,onSelect,chunks}:{documents:{id:string;original_name:string}[];selected:string;onSelect:(id:string)=>void;chunks:Chunk[]}) {
  const [active,setActive] = useState<Chunk|null>(null)
  return <><Select className="wide-select" placeholder="选择文档" value={selected || undefined} onChange={onSelect} options={documents.map(d=>({value:d.id,label:d.original_name}))}/><Table rowKey="id" dataSource={chunks} columns={[{title:'Index',dataIndex:'chunk_index',width:90},{title:'页码',dataIndex:'page_number',width:90},{title:'Tokens',dataIndex:'token_count',width:100},{title:'内容',dataIndex:'content',ellipsis:true},{title:'操作',render:(_,r)=><Button type="link" onClick={()=>setActive(r)}>查看</Button>}]}/><Drawer open={Boolean(active)} onClose={()=>setActive(null)} width={620} title={`Chunk #${active?.chunk_index}`}><Typography.Paragraph style={{whiteSpace:'pre-wrap'}}>{active?.content}</Typography.Paragraph><pre>{JSON.stringify(active?.metadata,null,2)}</pre></Drawer></>
}

function RetrievalPanel({knowledgeBaseId}:{knowledgeBaseId:string}) {
  const [result,setResult] = useState<SearchResult|null>(null), [error,setError] = useState('')
  const mutation = useMutation({mutationFn:(v:{query:string;top_k:number;score_threshold:number})=>resources.search({...v,knowledge_base_ids:[knowledgeBaseId]}),onSuccess:setResult,onError:(e)=>setError(errorMessage(e))})
  return <div className="test-grid"><Form layout="vertical" onFinish={(v)=>mutation.mutate(v)} initialValues={{top_k:8,score_threshold:0.2}}><Form.Item name="query" label="Query" rules={[{required:true}]}><Input.TextArea rows={5}/></Form.Item><Space><Form.Item name="top_k" label="Top K"><InputNumber min={1} max={50}/></Form.Item><Form.Item name="score_threshold" label="Score Threshold"><InputNumber min={0} max={1} step={0.05}/></Form.Item></Space><Button type="primary" htmlType="submit" loading={mutation.isPending}>执行检索</Button>{error&&<Alert type="error" message={error}/>}</Form><div>{result&&<><Typography.Text type="secondary">耗时 {result.duration_ms} ms · Trace {result.trace_id}</Typography.Text><List dataSource={result.items} renderItem={(item)=><List.Item><Card size="small" title={`${item.document_name} · P${item.page_number ?? '-'}`} extra={<Tag color="blue">{item.score.toFixed(3)}</Tag>}><Typography.Paragraph>{item.content}</Typography.Paragraph></Card></List.Item>}/></>}</div></div>
}

function AnswerPanel({knowledgeBaseId}:{knowledgeBaseId:string}) {
  const [answer,setAnswer] = useState(''), [trace,setTrace] = useState(''), [loading,setLoading] = useState(false)
  const ask = async ({query}:{query:string}) => { setLoading(true);setAnswer(''); try { const response=await fetch('/api/v1/rag/answer/stream',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${localStorage.getItem('access_token')}`},body:JSON.stringify({query,knowledge_base_ids:[knowledgeBaseId],top_k:8})}); if(!response.ok) throw new Error('问答请求失败'); const reader=response.body?.getReader(),decoder=new TextDecoder();let buffer=''; while(reader){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const blocks=buffer.split('\n\n');buffer=blocks.pop()??'';for(const block of blocks){const data=block.split('\n').find(line=>line.startsWith('data: '));if(!data)continue;const parsed=JSON.parse(data.slice(6));if(parsed.delta)setAnswer(v=>v+parsed.delta);if(parsed.trace_id)setTrace(parsed.trace_id)}} } catch(e){message.error(errorMessage(e))} finally{setLoading(false)} }
  return <div className="test-grid"><Form layout="vertical" onFinish={ask}><Form.Item name="query" label="问题" rules={[{required:true}]}><Input.TextArea rows={5}/></Form.Item><Button htmlType="submit" type="primary" loading={loading}>开始问答</Button></Form><Card title="回答" extra={trace&&<Typography.Text type="secondary">Trace {trace}</Typography.Text>}><ReactMarkdown>{answer||'回答将在这里流式显示。'}</ReactMarkdown></Card></div>
}

function MembersPanel({knowledgeBaseId}:{knowledgeBaseId:string}) {
  const client=useQueryClient(), query=useQuery({queryKey:['members',knowledgeBaseId],queryFn:async()=>(await api.get(`/knowledge-bases/${knowledgeBaseId}/members`)).data})
  const add=useMutation({mutationFn:(body:object)=>api.post(`/knowledge-bases/${knowledgeBaseId}/members`,body),onSuccess:()=>{void client.invalidateQueries({queryKey:['members',knowledgeBaseId]});message.success('成员权限已保存')},onError:(e)=>message.error(errorMessage(e))})
  return <><Form layout="inline" onFinish={(v)=>add.mutate(v)} style={{marginBottom:20}}><Form.Item name="user_id" rules={[{required:true}]}><Input placeholder="用户 UUID" style={{width:300}}/></Form.Item><Form.Item name="role" rules={[{required:true}]} initialValue="viewer"><Select style={{width:150}} options={['admin','editor','contributor','viewer'].map(v=>({value:v,label:v}))}/></Form.Item><Button type="primary" htmlType="submit" loading={add.isPending}>添加成员</Button></Form><Table rowKey="user_id" dataSource={query.data} columns={[{title:'用户 ID',dataIndex:'user_id'},{title:'角色',dataIndex:'role',render:(v:string)=><Tag>{v}</Tag>},{title:'加入时间',dataIndex:'created_at'}]}/></>
}

function SettingsPanel({knowledgeBaseId,initial,onSaved}:{knowledgeBaseId:string;initial?:Record<string,unknown>;onSaved:()=>void}) {
  const values=useMemo(()=>initial,[initial]), mutation=useMutation({mutationFn:(v:object)=>api.patch(`/knowledge-bases/${knowledgeBaseId}`,v),onSuccess:()=>{message.success('设置已保存');onSaved()},onError:(e)=>message.error(errorMessage(e))})
  return <Form key={JSON.stringify(values)} layout="vertical" initialValues={values} onFinish={(v)=>mutation.mutate(v)}><Form.Item name="name" label="名称"><Input/></Form.Item><Form.Item name="description" label="描述"><Input.TextArea/></Form.Item><Space><Form.Item name="chunk_strategy" label="分块策略"><Select style={{width:180}} options={['recursive','page','markdown'].map(v=>({value:v,label:v}))}/></Form.Item><Form.Item name="chunk_size" label="Chunk Size"><InputNumber min={100}/></Form.Item><Form.Item name="chunk_overlap" label="Overlap"><InputNumber min={0}/></Form.Item><Form.Item name="top_k" label="Top K"><InputNumber min={1} max={50}/></Form.Item></Space><Button type="primary" htmlType="submit" loading={mutation.isPending}>保存</Button></Form>
}
