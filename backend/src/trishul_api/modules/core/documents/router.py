"""Common document management: one set of endpoints for every module's records."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile

from trishul_api.auth import SIGNED_IN_USERS, CurrentUserDep, DbSession
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, ApiError
from trishul_api.modules.core.documents import storage
from trishul_api.modules.core.documents.schemas import DocumentCategory, DocumentOut, DocumentUpdate
from trishul_api.modules.core.documents.service import DocumentService

router = APIRouter(prefix="/core/documents", tags=["Documents"])

# Any signed-in user; what they may do with a given record is decided by that record's module.
_ANY = {"openapi_extra": SIGNED_IN_USERS}

DocumentId = Annotated[int, Path(alias="documentId", gt=0)]


def get_document_service(db: DbSession) -> DocumentService:
    return DocumentService(db)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


@router.get(
    "",
    summary="Documents attached to a record",
    description="The record is named by its table (entityType) and id (entityId). Access follows the record.",
    responses=NOT_FOUND_RESPONSE,
    **_ANY,
)
def list_documents(
    entity_type: Annotated[str, Query(alias="entityType", max_length=50)],
    entity_id: Annotated[int, Query(alias="entityId", gt=0)],
    user: CurrentUserDep,
    service: DocumentServiceDep,
) -> list[DocumentOut]:
    return service.list(user, entity_type, entity_id)


@router.post(
    "",
    summary="Upload a document (PDF, JPG, JPEG or PNG, up to 10 MB) to a record",
    status_code=201,
    responses=NOT_FOUND_RESPONSE,
    **_ANY,
)
async def upload_document(
    entity_type: Annotated[str, Form(alias="entityType", max_length=50)],
    entity_id: Annotated[int, Form(alias="entityId", gt=0)],
    file: Annotated[UploadFile, File()],
    user: CurrentUserDep,
    service: DocumentServiceDep,
    category: Annotated[DocumentCategory, Form()] = "Document",
) -> DocumentOut:
    # Read one byte past the limit so an oversized upload is refused without loading all of it.
    raw = await file.read(storage.MAX_BYTES + 1)
    if file.filename is None:
        raise ApiError("The file needs a name.")
    return service.upload(user, entity_type, entity_id, category, file.filename, raw)


@router.get(
    "/{documentId}/content",
    summary="Download (or show inline) a document's file",
    responses={**NOT_FOUND_RESPONSE, 200: {"content": {"application/octet-stream": {}}}},
    response_class=Response,
    **_ANY,
)
def get_document_content(
    document_id: DocumentId,
    user: CurrentUserDep,
    service: DocumentServiceDep,
    inline: Annotated[bool, Query()] = False,
) -> Response:
    row, raw = service.download(user, document_id)
    disposition = "inline" if inline else "attachment"
    quoted = row.file_name.replace('"', "'")
    return Response(
        content=raw,
        media_type=row.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'{disposition}; filename="{quoted}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.patch(
    "/{documentId}",
    summary="Rename a document or change its type",
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
    **_ANY,
)
def update_document(
    document_id: DocumentId,
    data: DocumentUpdate,
    user: CurrentUserDep,
    service: DocumentServiceDep,
    if_match: Annotated[bytes, Depends(if_match_row_version)],
) -> DocumentOut:
    return service.update(user, document_id, if_match, data)


@router.delete(
    "/{documentId}",
    summary="Remove a document",
    status_code=204,
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
    **_ANY,
)
def delete_document(
    document_id: DocumentId,
    user: CurrentUserDep,
    service: DocumentServiceDep,
    if_match: Annotated[bytes, Depends(if_match_row_version)],
) -> Response:
    service.delete(user, document_id, if_match)
    return Response(status_code=204)
