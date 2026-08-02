import { api } from './client'
import type { Chunk, DocumentItem, KnowledgeBase, SearchResult, Task, Workspace } from '../types'

export const resources = {
  workspaces: async () => (await api.get<Workspace[]>('/workspaces')).data,
  knowledgeBases: async () => (await api.get<KnowledgeBase[]>('/knowledge-bases')).data,
  documents: async (id: string) => (await api.get<DocumentItem[]>(`/knowledge-bases/${id}/documents`)).data,
  originalFile: async (id: string) => (await api.get<Blob>(`/documents/${id}/content`, {responseType:'blob'})).data,
  chunks: async (id: string) => (await api.get<Chunk[]>(`/documents/${id}/chunks`)).data,
  tasks: async () => (await api.get<Task[]>('/tasks')).data,
  search: async (body: object) => (await api.post<SearchResult>('/retrieval/search', body)).data,
}
