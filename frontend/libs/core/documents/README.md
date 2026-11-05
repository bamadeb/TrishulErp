# core-documents

The common Document Management module (front end). Any screen can attach, view, download, rename and
remove documents of a record by dropping in the panel:

    <trishul-document-panel entityType="trk.manual_travel" [entityId]="travel.id" [readonly]="false" />

`entityType` is the record's table. The API decides who may see or change the documents of that record;
a module opts in by registering a document target on the server (backend `modules/core/documents/registry.py`).
