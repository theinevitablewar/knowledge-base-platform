# Architecture

The platform uses a strict adapter boundary around infrastructure. FastAPI routes validate input and establish the authenticated `Principal`; domain services apply tenant and role checks; repositories are the only business-facing SQL layer. MinIO, Qdrant, Redis, embeddings, and LLMs are accessed through adapters.

## Data and ingestion flow

Uploads are validated, hashed, written to MinIO, and registered in PostgreSQL before a Celery job is queued. The worker parses the source, persists `parsed.json`, splits content with LangChain text splitters, generates embeddings, and upserts a new vector set. Database chunks switch only after vector writes succeed, then old vectors are removed. Repeated completed task execution is a no-op.

## Retrieval trust boundary

`SecureRetriever` derives tenant and user identity exclusively from JWT/API Key authentication. `PermissionService` calculates allowed knowledge bases and merges immutable tenant, knowledge-base, enabled, and deletion filters with safe user metadata. PostgreSQL performs a second authorization/status check after Qdrant recall. External agents call `/api/v1/agent/*`; they never receive database credentials.

## Security decisions

- API Keys are stored as SHA-256 hashes and scoped per operation.
- Passwords use Argon2 and tokens have explicit access/refresh types.
- Vector payloads contain tenant/workspace/KB/document scope.
- Uploaded content is never executed; supported parsers only extract text.
- User content is treated as untrusted data in the RAG system prompt.
- Audit records cover uploads, deletion requests, retrieval, and RAG calls.
- LangSmith is optional and disabled without a key; trace utility redacts credential fields.
