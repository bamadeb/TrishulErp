"""Imports the ASC register the service team keeps in Excel ("ASC DETAILS MONTH OF ...xlsx").

The first sheet whose header has a machine serial, a customer and a start date is read; columns are found
by name, so both the full register (Branch, SE, ... M/C Sl No, Start Date, Exp- Date, Visit Done ...) and
the yearly receipts sheet (Book Sl. No., Valid From, Valid upto, No. of Visits ...) work. Section rows such
as "LIVE ASC" or "ASC CLOSED RENEWAL REQUIRED" have no serial and are skipped.

A row is one ASC for one machine, identified by machine + start date: re-uploading the register updates
those contracts instead of adding them again. A machine not in Trishul is created with its customer
(matched on the OEM customer code, then on the name) and its model (matched on the model code, e.g.
"EX-210SP" = "EX-210 SUPER+"; a model not in the master is added). Preview runs the same steps without
writing anything.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from itertools import islice
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.db.models import (
    Branch,
    ContractCoverage,
    ContractPlan,
    Customer,
    Employee,
    MachineModel,
    MachineOwnership,
    MachineUnit,
    Principal,
    ServiceContract,
)
from trishul_api.modules.service.contracts.repository import ASC, plan_total
from trishul_api.modules.service.contracts.schemas import AscImportResult, AscImportRow, AscImportSummary
from trishul_api.modules.service.contracts.service import DEFAULT_PARTS_DISCOUNT_PCT, DOCUMENT_TYPE, plan_end_date
from trishul_api.modules.service.imports.service import _normalize_name

_MAX_ROWS = 10000
_HEADER_SCAN = 10
_DEFAULT_PRINCIPAL_CODE = "TATA_HITACHI"
_UNMAPPED_MODEL_CODE = "UNMAPPED"
_PLACEHOLDER_PHONE = "0000000000"
_MISSING = {"", "#N/A", "N/A", "NA", "0", "-", "NONE"}

# Column -> the header labels it goes by (lower case, single spaces).
_COLUMNS: dict[str, tuple[str, ...]] = {
    "branch": ("branch",),
    "engineer": ("se", "s/e"),
    "customer": ("customer", "customer name"),
    "customer_code": ("cust code", "customer code"),
    "phone": ("cust contact no", "contact no.", "contact no"),
    "customer_type": ("cust.type", "cust. type"),
    "model": ("model",),
    "serial": ("m/c sl no", "m/c sl. no.", "m/c sl no.", "machine sl no"),
    "commissioned": ("doc",),
    "amount": ("cont. amt.", "cont. value", "contract value"),
    "receipt": ("mr no.", "mr no.& date", "mr no"),
    "invoice": ("invoice/date", "invoice no/date"),
    "book": ("book no", "book sl. no.", "book sl no"),
    "oem_id": ("enrol id/contract id",),
    "renewal": ("renew or new",),
    "start": ("start date", "valid from"),
    "end": ("exp- date", "exp-date", "exp date", "valid upto"),
    "months": ("12month/6month", "12 months/ 6 months"),
    "visits_done": ("visit done",),
    "visits_due": ("visit due",),
    "visits": ("no. of visits",),
}
_REQUIRED = ("serial", "customer", "start")

# Model codes in the register are short forms of the master's names.
_MODEL_SUFFIXES = {"SP": "SUPER+", "S": "SUPER", "P": "PRIME"}
_MODEL_ALIASES = {"BX80": "SHINRAI BX-80", "TMX20": "TMX-20 SUPER", "TH86": "TH-86", "TH76": "TH-76"}


@dataclass(frozen=True)
class AscRow:
    row_number: int
    branch: str | None
    engineer: str | None
    customer: str | None
    customer_code: str | None
    phone: str | None
    is_key_account: bool
    model: str | None
    serial: str | None
    commissioned: dt.date | None
    amount: Decimal | None
    receipt: str | None
    invoice: str | None
    book: str | None
    oem_id: str | None
    is_renewal: bool
    start: dt.date | None
    end: dt.date | None
    months: int | None
    visits_included: int | None
    visits_used: int


def parse_asc_register(content: bytes) -> tuple[str, list[AscRow]]:
    """(sheet name, rows). Raises ApiError when no sheet looks like the ASC register."""
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a grab-bag of errors on a bad file
        raise ApiError("That file could not be read as an Excel (.xlsx) workbook.") from exc
    try:
        for sheet in workbook.worksheets:
            grid = list(islice(sheet.iter_rows(values_only=True), _MAX_ROWS + _HEADER_SCAN))
            for index, raw in enumerate(grid[:_HEADER_SCAN]):
                columns = _columns(raw)
                if all(name in columns for name in _REQUIRED):
                    rows = [
                        _build_row(cells, columns, index + 2 + offset)
                        for offset, cells in enumerate(grid[index + 1 :])
                        if cells and any(_text(cell) for cell in cells)
                    ]
                    # Section headings ("LIVE ASC", "ASC 2026-27") have no machine, customer or date.
                    return sheet.title.strip(), [
                        row for row in rows if row.serial or row.customer or row.customer_code or row.start
                    ]
    finally:
        workbook.close()
    raise ApiError(
        "This doesn't look like the ASC register. The sheet needs the columns 'M/C Sl No', 'Customer' and "
        "'Start Date' (or 'Valid From')."
    )


def _columns(raw: tuple[Any, ...] | None) -> dict[str, int]:
    if not raw:
        return {}
    labels: dict[str, int] = {}
    for index, cell in enumerate(raw):
        label = " ".join(str(cell).lower().split()) if cell not in (None, "") else ""
        if label and label not in labels:
            labels[label] = index
    found: dict[str, int] = {}
    for name, aliases in _COLUMNS.items():
        for alias in aliases:
            if alias in labels:
                found[name] = labels[alias]
                break
    return found


def _build_row(cells: tuple[Any, ...], columns: dict[str, int], row_number: int) -> AscRow:
    def cell(name: str) -> Any:
        index = columns.get(name)
        return cells[index] if index is not None and index < len(cells) else None

    done, due = _int(cell("visits_done")), _int(cell("visits_due"))
    months = _months(cell("months"))
    if done is not None and due is not None and done + due > 0:
        visits_included: int | None = done + due
    else:
        visits_included = _int(cell("visits")) or months
    return AscRow(
        row_number=row_number,
        branch=_text(cell("branch")),
        engineer=_text(cell("engineer")),
        customer=_text(cell("customer")),
        customer_code=_code(cell("customer_code")),
        phone=_phone(cell("phone")),
        is_key_account=(_text(cell("customer_type")) or "").upper().replace(" ", "") == "KA",
        model=_text(cell("model")),
        serial=_text(cell("serial")),
        commissioned=_date(cell("commissioned")),
        amount=_decimal(cell("amount")),
        receipt=_text(cell("receipt")),
        invoice=_text(cell("invoice")),
        book=_code(cell("book")),
        oem_id=_code(cell("oem_id")),
        is_renewal=(_text(cell("renewal")) or "").lower().startswith("renew"),
        start=_date(cell("start")),
        end=_date(cell("end")),
        months=months,
        visits_included=min(visits_included, 200) if visits_included is not None else None,
        visits_used=min(max(done or 0, 0), 200),
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = " ".join(str(value).split())
    return None if text.upper() in _MISSING else text


def _code(value: Any) -> str | None:
    """Codes typed as numbers come back as 88056 or 88056.0; book numbers keep their leading zeros."""
    return _text(value)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    text = _text(value)
    return int(text) if text and re.fullmatch(r"-?\d+", text) else None


def _months(value: Any) -> int | None:
    number = _int(value)
    if number is None and (text := _text(value)):
        match = re.match(r"\s*(\d+)", text)
        number = int(match.group(1)) if match else None
    return number if number is not None and 1 <= number <= 60 else None


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = _text(value)
    if not text:
        return None
    try:
        return Decimal(text.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _phone(value: Any) -> str | None:
    digits = re.sub(r"\D", "", _text(value) or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 else None


def _date(value: Any) -> dt.date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = _text(value)
    if not text:
        return None
    for pattern in ("%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _model_key(text: str) -> str:
    return re.sub(r"[^A-Z0-9+]", "", text.upper())


def _model_candidates(text: str) -> list[str]:
    upper = text.upper().strip()
    candidates = [upper]
    if alias := _MODEL_ALIASES.get(_model_key(upper)):
        candidates.append(alias)
    match = re.fullmatch(r"(EX|ZX|NX)-?(\d+)(SP|S|P)?", upper.replace(" ", ""))
    if match:
        base = f"{match.group(1)}-{match.group(2)}"
        if match.group(3):
            candidates.append(f"{base} {_MODEL_SUFFIXES[match.group(3)]}")
        candidates.append(base)
    return candidates


def _product_line(text: str) -> str:
    upper = text.upper().replace(" ", "")
    match = re.match(r"(EX|ZX|NX)-?(\d+)", upper)
    if match:
        return "Mini excavator" if int(match.group(2)) < 60 else "Excavator"
    if re.match(r"(BX|TH|TBL|TMX)", upper):
        return "Backhoe loader"
    if re.match(r"(TL|ZW|TWL)", upper):
        return "Wheel loader"
    return "Other"


def _customer_type(name: str) -> str:
    words = set(re.sub(r"[^A-Z ]", " ", name.upper()).split())
    company_words = {
        "PVT",
        "LTD",
        "LIMITED",
        "PRIVATE",
        "LLP",
        "CO",
        "COMPANY",
        "ENTERPRISE",
        "ENTERPRISES",
        "CONSTRUCTION",
        "CONSTRUCTIONS",
        "INFRA",
        "INFRASTRUCTURE",
        "ASSOCIATES",
        "INDUSTRIES",
        "MINERALS",
        "LOGISTICS",
        "BUILDERS",
        "ENGINEERING",
        "WORKS",
        "SERVICES",
        "CORPORATION",
    }
    if words & {"SAIL", "IFFCO", "NTPC", "MCL", "OMC", "IOCL", "GOVT", "GOVERNMENT"}:
        return "Government"
    return "Company" if words & company_words else "Individual"


@dataclass
class _Context:
    company_id: int
    principal_id: int
    fallback_branch: Branch
    apply: bool
    branches: dict[str, int] = field(default_factory=dict)
    plans: dict[tuple[int, Decimal], int] = field(default_factory=dict)
    engineers: dict[str, int] = field(default_factory=dict)
    models: dict[str, tuple[int, int]] = field(default_factory=dict)  # key -> (id, principal id)
    unmapped_model: tuple[int, int] | None = None
    machines: dict[str, tuple[int, int | None, int]] = field(
        default_factory=dict
    )  # serial -> (id, customer, principal)
    customers_by_code: dict[str, int] = field(default_factory=dict)
    customers_by_name: dict[str, int | None] = field(default_factory=dict)
    contracts: dict[tuple[int, dt.date], ServiceContract | None] = field(default_factory=dict)
    machine_contracts: dict[int, list[tuple[dt.date, dt.date, int | None]]] = field(default_factory=dict)
    marked_customers: set[int] = field(default_factory=set)
    next_placeholder: int = -1

    def placeholder(self) -> int:
        """A stand-in id for a record a preview would create (negative, never a real id)."""
        self.next_placeholder -= 1
        return self.next_placeholder


class AscImportService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    def run(
        self, content: bytes, file_name: str, branch_id: int, principal_id: int | None, *, apply: bool
    ) -> AscImportResult:
        sheet, rows = parse_asc_register(content)
        ctx = self._context(rows, branch_id, principal_id, apply)
        outcomes = [self._row(row, ctx) for row in rows]
        if apply:
            self._db.commit()
        else:
            self._db.rollback()
        summary = AscImportSummary(
            file_name=file_name,
            sheet_name=sheet,
            total=len(outcomes),
            inserts=sum(o.action == "insert" for o in outcomes),
            updates=sum(o.action == "update" for o in outcomes),
            skips=sum(o.action == "skip" for o in outcomes),
            new_customers=sum(o.new_customer for o in outcomes),
            new_machines=sum(o.new_machine for o in outcomes),
            new_models=sum(o.new_model for o in outcomes),
        )
        return AscImportResult(applied=apply, summary=summary, rows=outcomes)

    # ------------------------------------------------------------------ one row

    def _row(self, row: AscRow, ctx: _Context) -> AscImportRow:
        out = AscImportRow(
            row_number=row.row_number,
            branch=row.branch,
            customer_name=row.customer,
            customer_code=row.customer_code,
            serial_number=row.serial,
            model=row.model,
            start_date=row.start,
            end_date=row.end,
            action="skip",
        )
        if not row.serial:
            out.messages.append("No machine serial number; skipped.")
            return out
        if row.start is None:
            out.messages.append("No start date (or it isn't a date); skipped.")
            return out
        end = row.end or plan_end_date(row.start, row.months or 12)
        out.end_date = end
        if end < row.start:
            out.messages.append("The expiry date is before the start date; skipped.")
            return out

        branch_id = self._branch(row, ctx, out)
        machine = ctx.machines.get(row.serial.upper())
        if machine is not None:
            machine_id, customer_id, principal_id = machine
            if customer_id is None:
                customer_id = self._customer(row, ctx, out)
                if customer_id is None:
                    return out
                if ctx.apply and machine_id > 0:
                    unit = self._db.get(MachineUnit, machine_id)
                    if unit is not None:
                        unit.customer_id = customer_id
                ctx.machines[row.serial.upper()] = (machine_id, customer_id, principal_id)
                out.messages.append("The machine had no customer; linked to this one.")
        else:
            customer_id = self._customer(row, ctx, out)
            if customer_id is None:
                return out
            model = self._model(row, ctx, out)
            if model is None:
                return out
            machine_id, principal_id = self._new_machine(row, ctx, customer_id, model, branch_id), model[1]
            out.new_machine = True

        key = (machine_id, row.start)
        if key in ctx.contracts:
            contract = ctx.contracts[key]
            if contract is not None and contract.status == "Cancelled":
                out.messages.append("This ASC was cancelled in Trishul; not changed.")
                return out
            out.action = "update"
            if contract is not None:
                out.contract_id, out.contract_no = contract.id, contract.contract_no
                if ctx.apply:
                    self._fill(contract, row, ctx, end, branch_id)
        else:
            out.action = "insert"
            contract = (
                self._insert(row, ctx, machine_id, customer_id, principal_id, end, branch_id) if ctx.apply else None
            )
            ctx.contracts[key] = contract
            ctx.machine_contracts.setdefault(machine_id, []).append((row.start, end, contract.id if contract else None))
            if contract is not None:
                out.contract_id, out.contract_no = contract.id, contract.contract_no
        if ctx.apply and customer_id > 0 and customer_id not in ctx.marked_customers:
            customer = self._db.get(Customer, customer_id)
            if customer is not None:
                customer.is_asc_customer = True
            ctx.marked_customers.add(customer_id)
        return out

    def _branch(self, row: AscRow, ctx: _Context, out: AscImportRow) -> int:
        if row.branch and (found := ctx.branches.get(row.branch.upper())):
            return found
        if row.branch:
            out.messages.append(f"Branch '{row.branch}' isn't in Trishul; recorded under {ctx.fallback_branch.name}.")
        return ctx.fallback_branch.id

    def _customer(self, row: AscRow, ctx: _Context, out: AscImportRow) -> int | None:
        if row.customer_code and row.customer_code in ctx.customers_by_code:
            return ctx.customers_by_code[row.customer_code]
        if row.customer:
            matched = ctx.customers_by_name.get(_normalize_name(row.customer))
            if matched is not None:
                if row.customer_code:
                    ctx.customers_by_code[row.customer_code] = matched
                return matched
        if not row.customer:
            out.messages.append("No customer name; skipped.")
            return None
        code = (row.customer_code or f"ASC-{row.serial}")[:20]
        if ctx.apply:
            customer = Customer(
                company_id=ctx.company_id,
                code=code,
                name=row.customer[:200],
                customer_type=_customer_type(row.customer),
                gst_registration_type="Unregistered",
                primary_phone=row.phone or _PLACEHOLDER_PHONE,
                is_asc_customer=True,
                created_by_user_id=self._actor.id,
            )
            if row.is_key_account:
                customer.priority_tier = "Key"
            self._db.add(customer)
            self._db.flush()
            customer_id = customer.id
        else:
            customer_id = ctx.placeholder()
        ctx.customers_by_code[code] = customer_id
        if row.customer_code and row.customer_code != code:
            ctx.customers_by_code[row.customer_code] = customer_id
        ctx.customers_by_name.setdefault(_normalize_name(row.customer), customer_id)
        out.new_customer = True
        return customer_id

    def _model(self, row: AscRow, ctx: _Context, out: AscImportRow) -> tuple[int, int] | None:
        if not row.model:
            if ctx.unmapped_model is None:
                out.messages.append("No model and no 'UNMAPPED' model in the master; skipped.")
                return None
            out.messages.append("No model given; the machine is added as 'Model not yet identified'.")
            return ctx.unmapped_model
        for candidate in _model_candidates(row.model):
            if found := ctx.models.get(_model_key(candidate)):
                return found
        code = row.model.upper().strip()[:20]
        if ctx.apply:
            model = MachineModel(
                model_code=code,
                model_name=code,
                product_line=_product_line(code),
                principal_id=ctx.principal_id,
                created_by_user_id=self._actor.id,
            )
            self._db.add(model)
            self._db.flush()
            found = (model.id, ctx.principal_id)
        else:
            found = (ctx.placeholder(), ctx.principal_id)
        ctx.models[_model_key(code)] = found
        out.new_model = True
        out.messages.append(f"Model '{code}' added to the model master.")
        return found

    def _new_machine(self, row: AscRow, ctx: _Context, customer_id: int, model: tuple[int, int], branch_id: int) -> int:
        serial = (row.serial or "")[:40]
        if ctx.apply:
            machine = MachineUnit(
                serial_number=serial,
                model_id=model[0],
                principal_id=model[1],
                customer_id=customer_id,
                status="Sold",
                commissioning_date=row.commissioned,
                sold_by_branch_id=branch_id,
                created_by_user_id=self._actor.id,
            )
            self._db.add(machine)
            self._db.flush()
            self._db.add(
                MachineOwnership(
                    machine_unit_id=machine.id,
                    customer_id=customer_id,
                    from_date=dt.date.today(),
                    created_by_user_id=self._actor.id,
                )
            )
            machine_id = machine.id
        else:
            machine_id = ctx.placeholder()
        ctx.machines[serial.upper()] = (machine_id, customer_id, model[1])
        return machine_id

    def _insert(
        self,
        row: AscRow,
        ctx: _Context,
        machine_id: int,
        customer_id: int,
        principal_id: int,
        end: dt.date,
        branch_id: int,
    ) -> ServiceContract:
        contract = ServiceContract(
            company_id=ctx.company_id,
            contract_no=next_document_no(
                self._db, company_id=ctx.company_id, document_type=DOCUMENT_TYPE, branch_id=branch_id
            ),
            principal_id=principal_id,
            customer_id=customer_id,
            contract_type=ASC,
            start_date=row.start,
            end_date=end,
            status="Active",
            enrolled_on=row.start,
            created_by_user_id=self._actor.id,
        )
        self._fill(contract, row, ctx, end, branch_id, new=True)
        if row.is_renewal:
            earlier = [c for c in ctx.machine_contracts.get(machine_id, []) if c[1] < (row.start or end) and c[2]]
            if earlier:
                contract.renewed_from_contract_id = max(earlier)[2]
        self._db.add(contract)
        self._db.flush()
        plan = self._db.get(ContractPlan, contract.contract_plan_id) if contract.contract_plan_id else None
        self._db.add(
            ContractCoverage(
                service_contract_id=contract.id,
                machine_unit_id=machine_id,
                covers_labour=plan.covers_labour if plan else True,
                covers_parts=plan.covers_parts if plan else False,
                covers_travel=plan.covers_travel if plan else True,
                parts_discount_pct=plan.parts_discount_pct if plan else DEFAULT_PARTS_DISCOUNT_PCT,
                created_by_user_id=self._actor.id,
            )
        )
        return contract

    def _fill(
        self, contract: ServiceContract, row: AscRow, ctx: _Context, end: dt.date, branch_id: int, *, new: bool = False
    ) -> None:
        """Copy the register's values onto the contract (a blank cell leaves what Trishul has)."""
        contract.end_date = end
        contract.branch_id = branch_id
        if row.visits_included is not None:
            contract.visits_included = row.visits_included
        if new or row.visits_used:
            contract.visits_used = row.visits_used
        if row.amount is not None:
            contract.contract_value = row.amount
            months = row.months or _whole_months(row.start or end, end)
            contract.contract_plan_id = ctx.plans.get(
                (months, row.amount.quantize(Decimal("1"))), contract.contract_plan_id
            )
        for attribute, value, length in (
            ("book_no", row.book, 20),
            ("oem_contract_id", row.oem_id, 40),
            ("receipt_no", row.receipt, 60),
            ("invoice_ref", row.invoice, 60),
        ):
            if value:
                setattr(contract, attribute, value[:length])
        contract.is_renewal = row.is_renewal
        if row.engineer:
            contract.engineer_name = row.engineer[:100]
            contract.engineer_employee_id = ctx.engineers.get(row.engineer.lower())
        if not new:
            contract.updated_at = _now()
            contract.updated_by_user_id = self._actor.id

    # ------------------------------------------------------------------ context

    def _context(self, rows: list[AscRow], branch_id: int, principal_id: int | None, apply: bool) -> _Context:
        branch = self._db.get(Branch, branch_id)
        if branch is None or not branch.is_active:
            raise NotFound("Branch not found.")
        principal = self._principal(principal_id)
        ctx = _Context(company_id=branch.company_id, principal_id=principal.id, fallback_branch=branch, apply=apply)
        db = self._db

        for bid, name in db.execute(
            select(Branch.id, Branch.name).where(Branch.company_id == branch.company_id, Branch.is_active)
        ):
            ctx.branches[name.upper()] = bid
        for plan in db.scalars(
            select(ContractPlan).where(
                ContractPlan.contract_type == ASC, ContractPlan.is_active, ContractPlan.principal_id == principal.id
            )
        ):
            total = plan_total(plan.price, plan.gst_pct)
            if total is not None:
                ctx.plans.setdefault((plan.duration_months, total), plan.id)
        for emp_id, first, last in db.execute(
            select(Employee.id, Employee.first_name, Employee.last_name).where(Employee.is_active)
        ):
            ctx.engineers.setdefault(" ".join(p for p in (first, last) if p).lower(), emp_id)
        for model in db.scalars(select(MachineModel).where(MachineModel.is_active)):
            entry = (model.id, model.principal_id)
            if model.model_code == _UNMAPPED_MODEL_CODE:
                ctx.unmapped_model = entry
                continue
            ctx.models.setdefault(_model_key(model.model_code), entry)
            ctx.models.setdefault(_model_key(model.model_name), entry)

        serials = sorted({row.serial for row in rows if row.serial})
        for chunk in _chunks(serials):
            for machine in db.scalars(select(MachineUnit).where(MachineUnit.serial_number.in_(chunk))):
                ctx.machines[machine.serial_number.upper()] = (machine.id, machine.customer_id, machine.principal_id)
        codes = sorted({row.customer_code for row in rows if row.customer_code})
        for chunk in _chunks(codes):
            for cid, code in db.execute(
                select(Customer.id, Customer.code).where(
                    Customer.company_id == branch.company_id, Customer.code.in_(chunk)
                )
            ):
                ctx.customers_by_code[code] = cid
        for cid, name in db.execute(
            select(Customer.id, Customer.name).where(Customer.company_id == branch.company_id, Customer.is_active)
        ):
            key = _normalize_name(name)
            if key:
                # Two customers with one name: don't guess.
                ctx.customers_by_name[key] = None if key in ctx.customers_by_name else cid

        machine_ids = sorted({entry[0] for entry in ctx.machines.values()})
        for id_chunk in _chunks(machine_ids):
            for contract, machine_id in db.execute(
                select(ServiceContract, ContractCoverage.machine_unit_id)
                .join(ContractCoverage, ContractCoverage.service_contract_id == ServiceContract.id)
                .where(
                    ContractCoverage.machine_unit_id.in_(id_chunk),
                    ServiceContract.contract_type == ASC,
                    ServiceContract.is_active,
                )
            ):
                ctx.contracts.setdefault((machine_id, contract.start_date), contract)
                ctx.machine_contracts.setdefault(machine_id, []).append(
                    (contract.start_date, contract.end_date, contract.id)
                )
        return ctx

    def _principal(self, principal_id: int | None) -> Principal:
        if principal_id is not None:
            principal = self._db.get(Principal, principal_id)
            if principal is None or not principal.is_active:
                raise NotFound("Brand not found.")
            return principal
        principal = self._db.scalars(
            select(Principal).where(Principal.code == _DEFAULT_PRINCIPAL_CODE, Principal.is_active).limit(1)
        ).first()
        if principal is None:
            raise ApiError(f"The default brand '{_DEFAULT_PRINCIPAL_CODE}' is not set up. Choose a brand to import.")
        return principal


def _chunks[T](values: list[T], size: int = 500) -> list[list[T]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _whole_months(start: dt.date, end: dt.date) -> int:
    after = end + dt.timedelta(days=1)
    return max(1, (after.year - start.year) * 12 + after.month - start.month)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
