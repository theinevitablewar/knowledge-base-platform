export interface User { id: string; tenant_id: string; username: string; display_name: string; email: string; is_tenant_admin: boolean }
export interface Workspace { id: string; name: string; description: string }
export interface KnowledgeBase { id: string; workspace_id: string; name: string; description: string; status: string; visibility: string; chunk_strategy: string; chunk_size: number; chunk_overlap: number; top_k: number; score_threshold: number | null; created_at: string; updated_at: string }
export interface DocumentItem { id: string; knowledge_base_id: string; original_name: string; mime_type: string; file_size: number; page_count: number; chunk_count: number; status: string; enabled: boolean; error_message: string | null; created_at: string }
export interface Chunk { id: string; document_id: string; chunk_index: number; content: string; page_number: number | null; token_count: number; metadata: Record<string, unknown>; enabled: boolean }
export interface SearchItem { chunk_id: string; document_id: string; document_name: string; content: string; page_number: number | null; score: number; metadata: Record<string, unknown> }
export interface SearchResult { query: string; items: SearchItem[]; duration_ms: number; trace_id: string }
export interface Task { id: string; document_id: string; task_type: string; status: string; progress: number; current_stage: string; retry_count: number; error_message: string | null; created_at: string }
