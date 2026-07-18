"""Standard-library CSV/XLSX ingestion for Relationship Map.

The importer preserves the uploaded source as an immutable snapshot, converts
rows into contacts plus flexible attributes, and never overwrites the source
file. It intentionally does not edit a user's original spreadsheet; a future
explicit sync adapter can be added without changing the vault data model.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from . import vault

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_FIELD_ALIASES = {
    "name": {"姓名", "联系人", "客户姓名", "客户", "姓名/称呼", "name", "customer name"},
    "organization": {"单位", "公司", "企业", "机构", "客户单位", "组织", "organization", "company"},
    "city": {"城市", "地区", "所在城市", "区域", "city", "region"},
    "role": {"职位", "职务", "身份", "岗位", "角色", "role", "title"},
    "tags": {"标签", "分类", "客户类型", "客户分类", "tags", "tag"},
}


def source_dir() -> Path:
    path = vault.vault_root() / "sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_header(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - 64
    return index - 1


def _safe_xml(payload: bytes) -> ET.Element:
    """Reject entity declarations before parsing untrusted XLSX XML with stdlib."""
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("表格包含不安全的 XML 实体声明，无法导入。")
    return ET.fromstring(payload)


def _xlsx_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = _safe_xml(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in item.iterfind(".//m:t", _NS)))
        workbook = _safe_xml(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find("m:sheets/m:sheet", _NS)
        if first_sheet is None:
            return []
        rel_id = first_sheet.attrib.get("{" + _NS["r"] + "}id", "")
        rels = _safe_xml(archive.read("xl/_rels/workbook.xml.rels"))
        target = next((r.attrib.get("Target") for r in rels if r.attrib.get("Id") == rel_id), None)
        if not target:
            return []
        sheet_path = "xl/" + target.lstrip("/")
        root = _safe_xml(archive.read(sheet_path))
        output: list[list[str]] = []
        for row in root.findall("m:sheetData/m:row", _NS):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", _NS):
                index = _column_index(cell.attrib.get("r", "A1"))
                kind = cell.attrib.get("t")
                if kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.iterfind(".//m:t", _NS))
                else:
                    raw = cell.findtext("m:v", default="", namespaces=_NS)
                    value = shared[int(raw)] if kind == "s" and raw.isdigit() and int(raw) < len(shared) else raw
                values[index] = str(value).strip()
            if values:
                output.append([values.get(i, "") for i in range(max(values) + 1)])
        return output


def _csv_rows(path: Path) -> list[list[str]]:
    for encoding in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [[str(value).strip() for value in row] for row in csv.reader(handle)]
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别 CSV 编码。")


def read_rows(file_path: str) -> list[list[str]]:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError("未找到可导入的表格文件。")
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _xlsx_rows(path)
    if suffix == ".csv":
        return _csv_rows(path)
    raise ValueError("当前仅支持 .xlsx 和 .csv 文件。")


def infer_mapping(headers: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    normalised = {_normalise_header(header): header for header in headers if str(header).strip()}
    for field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            header = normalised.get(_normalise_header(alias))
            if header:
                mapping[field] = header
                break
    return mapping


def preview(file_path: str, sample_size: int = 5) -> dict[str, Any]:
    rows = read_rows(file_path)
    if not rows:
        raise ValueError("表格为空，无法导入。")
    headers = rows[0]
    valid_headers = [header or f"字段{index + 1}" for index, header in enumerate(headers)]
    mapping = infer_mapping(valid_headers)
    samples = [dict(zip(valid_headers, row + [""] * (len(valid_headers) - len(row)))) for row in rows[1:1 + max(1, min(sample_size, 10))] if any(row)]
    return {"headers": valid_headers, "suggested_mapping": mapping, "row_count": sum(1 for row in rows[1:] if any(row)), "samples": samples}


def _split_tags(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").replace("；", ";").replace("，", ",").replace("、", ",").split(",") if item.strip()]


def import_spreadsheet(file_path: str, mapping: dict[str, str] | None = None, default_tags: list[str] | None = None) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    rows = read_rows(str(path))
    if not rows:
        raise ValueError("表格为空，无法导入。")
    headers = [header or f"字段{index + 1}" for index, header in enumerate(rows[0])]
    selected = mapping or infer_mapping(headers)
    name_header = selected.get("name")
    if not name_header:
        raise ValueError("无法自动识别姓名列。请在导入预览中指定联系人姓名对应的表头。")
    source_bytes = path.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    snapshot = source_dir() / f"{digest[:16]}-{path.name}"
    if not snapshot.exists():
        shutil.copy2(path, snapshot)
    owner_id = vault.safe_owner_id()
    vault.initialise()
    now = vault.utc_now()
    added = updated = skipped = 0
    batch_id = str(vault.uuid4())
    with vault.connection() as db:
        db.execute("INSERT OR IGNORE INTO source_documents(id, owner_id, original_name, snapshot_path, sha256, imported_at) VALUES (?, ?, ?, ?, ?, ?)", (digest, owner_id, path.name, str(snapshot), digest, now))
        db.execute("INSERT INTO import_batches(id, owner_id, source_id, row_count, created_at) VALUES (?, ?, ?, ?, ?)", (batch_id, owner_id, digest, 0, now))
        for row in rows[1:]:
            if not any(row):
                continue
            record = dict(zip(headers, row + [""] * (len(headers) - len(row))))
            name = str(record.get(name_header, "")).strip()
            if not name:
                skipped += 1
                continue
            contact_id, created = vault._resolve_or_create_contact(db, owner_id, name, record.get(selected.get("organization", "")) or None, record.get(selected.get("city", "")) or None, record.get(selected.get("role", "")) or None)
            tags = _split_tags(record.get(selected.get("tags", ""))) + list(default_tags or [])
            for tag in sorted(set(tags)):
                db.execute("INSERT OR IGNORE INTO tags(contact_id, tag, source, created_at) VALUES (?, ?, ?, ?)", (contact_id, tag, "import", now))
            reserved = set(selected.values())
            for header, value in record.items():
                if header in reserved or not str(value).strip():
                    continue
                db.execute("INSERT INTO contact_attributes(contact_id, field_name, value_json, source, certainty, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(contact_id, field_name) DO UPDATE SET value_json=excluded.value_json, source=excluded.source, certainty=excluded.certainty, updated_at=excluded.updated_at", (contact_id, header, json.dumps(value, ensure_ascii=False), "import", "confirmed", now))
            vault._audit(db, owner_id, "import", "contact", contact_id, {"batch_id": batch_id, "source_id": digest})
            added += int(created)
            updated += int(not created)
        db.execute("UPDATE import_batches SET row_count = ? WHERE id = ?", (added + updated, batch_id))
    return {"batch_id": batch_id, "source_id": digest, "source_snapshot": str(snapshot), "imported": added + updated, "added": added, "updated": updated, "skipped": skipped, "mapping": selected}
