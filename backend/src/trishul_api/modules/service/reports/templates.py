"""Inspection checklists (svc.checklist_template): kept by administrators and team leads.

A template can be for one brand, model and/or call type, or for all (blank). The most specific active template
is copied into each new service report. Questions that are removed from a template are deactivated, not
deleted, so reports that already used them keep their link.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    LookupType,
    LookupValue,
    MachineModel,
    Principal,
)
from trishul_api.modules.service.reports.schemas import (
    ChecklistBrandOption,
    ChecklistItemOut,
    ChecklistTemplateInput,
    ChecklistTemplateOut,
    ChecklistTemplateUpdate,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ChecklistTemplateService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    def list(self, include_inactive: bool) -> list[ChecklistTemplateOut]:
        statement = select(ChecklistTemplate).order_by(ChecklistTemplate.name, ChecklistTemplate.id)
        if not include_inactive:
            statement = statement.where(ChecklistTemplate.is_active)
        return [self._out(t) for t in self._db.scalars(statement).all()]

    def brands(self) -> "list[ChecklistBrandOption]":
        rows = self._db.execute(
            select(Principal.id, Principal.name).where(Principal.is_active).order_by(Principal.name)
        )
        return [ChecklistBrandOption(id=r.id, name=r.name) for r in rows]

    def get(self, template_id: int) -> ChecklistTemplateOut:
        return self._out(self._template(template_id))

    def create(self, data: ChecklistTemplateInput) -> ChecklistTemplateOut:
        self._check_references(data)
        template = ChecklistTemplate(
            name=data.name,
            principal_id=data.principal_id,
            machine_model_id=data.machine_model_id,
            call_type_lookup_id=data.call_type_lookup_id,
            inspection_note=(data.inspection_note or "").strip() or None,
            created_by_user_id=self._actor.id,
        )
        self._db.add(template)
        self._db.flush()
        self._set_items(template, data, keep={})
        self._db.commit()
        return self._out(template)

    def update(self, template_id: int, expected: bytes, data: ChecklistTemplateUpdate) -> ChecklistTemplateOut:
        template = self._template(template_id)
        check_row_version(template.row_version, expected)
        self._check_references(data)
        template.name = data.name
        template.principal_id = data.principal_id
        template.machine_model_id = data.machine_model_id
        template.call_type_lookup_id = data.call_type_lookup_id
        template.is_active = data.is_active
        template.inspection_note = (data.inspection_note or "").strip() or None
        template.updated_at, template.updated_by_user_id = _now(), self._actor.id
        existing = {
            i.id: i
            for i in self._db.scalars(
                select(ChecklistTemplateItem).where(ChecklistTemplateItem.checklist_template_id == template.id)
            ).all()
        }
        self._set_items(template, data, keep=existing)
        self._db.commit()
        self._db.refresh(template)
        return self._out(template)

    # ------------------------------------------------------------------ helpers

    def _set_items(
        self, template: ChecklistTemplate, data: ChecklistTemplateInput, keep: dict[int, ChecklistTemplateItem]
    ) -> None:
        wanted_ids = {i.id for i in data.items if i.id is not None}
        unknown = wanted_ids - set(keep)
        if unknown:
            raise ApiError(
                "A question does not belong to this checklist.", errors={"items": [f"Unknown id {sorted(unknown)[0]}"]}
            )
        now = _now()
        for sequence, item in enumerate(data.items, start=1):
            row = keep.get(item.id) if item.id is not None else None
            if row is None:
                self._db.add(
                    ChecklistTemplateItem(
                        checklist_template_id=template.id,
                        sequence=sequence,
                        item_text=item.item_text,
                        response_type=item.response_type,
                        is_mandatory=item.is_mandatory,
                        created_by_user_id=self._actor.id,
                    )
                )
                continue
            row.sequence, row.item_text = sequence, item.item_text
            row.response_type, row.is_mandatory = item.response_type, item.is_mandatory
            row.is_active = True
            row.updated_at, row.updated_by_user_id = now, self._actor.id
        for row_id, row in keep.items():
            if row_id not in wanted_ids and row.is_active:
                row.is_active = False
                row.updated_at, row.updated_by_user_id = now, self._actor.id

    def _check_references(self, data: ChecklistTemplateInput) -> None:
        errors: dict[str, list[str]] = {}
        if data.principal_id is not None and self._db.get(Principal, data.principal_id) is None:
            errors["principalId"] = ["Unknown brand."]
        if data.machine_model_id is not None and self._db.get(MachineModel, data.machine_model_id) is None:
            errors["machineModelId"] = ["Unknown machine model."]
        if data.call_type_lookup_id is not None:
            ok = self._db.scalars(
                select(LookupValue.id)
                .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
                .where(LookupValue.id == data.call_type_lookup_id, LookupType.code == "CALL_TYPE")
                .limit(1)
            ).first()
            if ok is None:
                errors["callTypeLookupId"] = ["Not a valid call type."]
        if errors:
            raise ApiError("Some of the selected values don't exist.", errors=errors)

    def _template(self, template_id: int) -> ChecklistTemplate:
        template = self._db.get(ChecklistTemplate, template_id)
        if template is None:
            raise NotFound("Checklist not found.")
        return template

    def _out(self, template: ChecklistTemplate) -> ChecklistTemplateOut:
        items = self._db.scalars(
            select(ChecklistTemplateItem)
            .where(ChecklistTemplateItem.checklist_template_id == template.id, ChecklistTemplateItem.is_active)
            .order_by(ChecklistTemplateItem.sequence, ChecklistTemplateItem.id)
        ).all()
        principal = self._db.get(Principal, template.principal_id) if template.principal_id else None
        model = self._db.get(MachineModel, template.machine_model_id) if template.machine_model_id else None
        call_type = (
            self._db.scalar(select(LookupValue.label).where(LookupValue.id == template.call_type_lookup_id))
            if template.call_type_lookup_id
            else None
        )
        return ChecklistTemplateOut(
            id=template.id,
            name=template.name,
            principal_id=template.principal_id,
            principal_name=principal.name if principal else None,
            machine_model_id=template.machine_model_id,
            machine_model_name=model.model_name if model else None,
            call_type_lookup_id=template.call_type_lookup_id,
            call_type=call_type,
            is_active=bool(template.is_active),
            inspection_note=template.inspection_note,
            items=[
                ChecklistItemOut(
                    id=i.id,
                    sequence=i.sequence,
                    item_text=i.item_text,
                    response_type=i.response_type,
                    is_mandatory=bool(i.is_mandatory),
                )
                for i in items
            ],
            row_version=template.row_version,
        )
