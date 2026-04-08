# Public Document Read Boundary Governance Policy

## Overview

This document defines the public document read contract for the MuseAI system. It establishes a formal field whitelist for document responses accessible to unauthenticated users (guests) and authenticated users without elevated privileges.

## Policy Statement

Document read endpoints accessible to guests and regular users must expose only whitelisted public fields. This boundary ensures that internal operational data (such as error messages, user IDs, and other sensitive metadata) is not leaked to unauthorized parties.

## Whitelisted Public Fields

### Document Response Fields

| Field       | Type   | Description                           |
|-------------|--------|---------------------------------------|
| `id`        | string | Unique document identifier            |
| `filename`  | string | Original filename of the document     |
| `status`    | string | Processing status (pending, processing, completed, failed) |
| `created_at`| string | ISO 8601 timestamp of creation        |

### Ingestion Job Response Fields

| Field         | Type   | Description                           |
|---------------|--------|---------------------------------------|
| `id`          | string | Unique ingestion job identifier       |
| `document_id` | string | Associated document identifier        |
| `status`      | string | Processing status                     |
| `chunk_count` | int    | Number of chunks created              |
| `created_at`  | string | ISO 8601 timestamp of job creation    |
| `updated_at`  | string | ISO 8601 timestamp of last update     |

## Non-Public Fields (Excluded from Whitelist)

The following fields are **NOT** included in public responses and are only available to administrators or through internal APIs:

| Field          | Reason for Exclusion                           |
|----------------|------------------------------------------------|
| `error`        | May contain sensitive internal error details   |
| `user_id`      | User identification information                |
| `file_size`    | Internal metadata                              |

## Implementation

### Response Models

Two sets of response models are defined in `backend/app/api/documents.py`:

1. **Public Response Models** (`PublicDocumentResponse`, `PublicIngestionJobResponse`)
   - Used for endpoints accessible to guests and regular users
   - Contain only whitelisted fields

2. **Admin/Full Response Models** (`DocumentResponse`, `IngestionJobResponse`)
   - Used for admin-only operations (e.g., upload)
   - May contain additional fields like `error`

### Affected Endpoints

| Endpoint                      | Response Model               | Access Level         |
|-------------------------------|------------------------------|----------------------|
| `GET /api/v1/documents`       | `PublicDocumentListResponse` | Guest, User, Admin   |
| `GET /api/v1/documents/{id}`  | `PublicDocumentResponse`     | Guest, User, Admin   |
| `GET /api/v1/documents/{id}/status` | `PublicIngestionJobResponse` | Guest, User, Admin   |
| `POST /api/v1/documents/upload` | `DocumentResponse`         | Admin only           |
| `DELETE /api/v1/documents/{id}` | `DeleteResponse`           | Admin only           |

## Security Rationale

### Error Field Exclusion

The `error` field in document and ingestion job records may contain sensitive information:
- Internal file paths
- Database connection details
- Stack traces
- Configuration values

Exposing this field to unauthenticated users could enable:
- Information disclosure attacks
- System fingerprinting
- Targeted exploitation

### Consistent Access Model

This policy implements a consistent access model where:
1. Public read endpoints use the same response model regardless of authentication status
2. Admin operations retain full visibility for operational needs
3. The contract is enforced at the API layer through Pydantic models

## Verification

Contract tests in `backend/tests/contract/test_documents_public_contract.py` verify:
1. Guest document list responses contain only whitelisted fields
2. Guest document detail responses contain only whitelisted fields
3. Guest document status responses contain only whitelisted fields
4. Authenticated user responses follow the same whitelist
5. Admin upload responses still include operational fields (e.g., `error`)

## Change Policy

Changes to the public field whitelist require:
1. Security review and approval
2. Update to this documentation
3. Update to contract tests
4. Consideration of backward compatibility for API consumers

## References

- Issue-01: Public Document Read Boundary Governance
- `backend/app/api/documents.py` - Response model definitions
- `backend/tests/contract/test_documents_public_contract.py` - Contract tests
