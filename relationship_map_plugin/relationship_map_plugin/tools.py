"""Constrained Hermes tools for durable relationship assets."""

from __future__ import annotations

from typing import Any

from . import vault


def _tool_result(payload: dict[str, Any]) -> str:
    try:
        from tools.registry import tool_result
        return tool_result(payload)
    except ImportError:
        import json
        return json.dumps(payload, ensure_ascii=False)


def _tool_error(exc: Exception) -> str:
    try:
        from tools.registry import tool_error
        return tool_error(str(exc))
    except ImportError:
        import json
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def vault_available() -> bool:
    try:
        vault.initialise()
        return True
    except Exception:
        return False


def _handle_search(args: dict, **_: Any) -> str:
    try:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("请提供姓名、城市、单位、角色或标签。")
        contacts = vault.find_contacts(query, int(args.get("limit", 20)))
        return _tool_result({"success": True, "contacts": contacts, "count": len(contacts)})
    except Exception as exc:
        return _tool_error(exc)


def _handle_contact(args: dict, **_: Any) -> str:
    try:
        name = str(args.get("name") or "").strip()
        if not name:
            raise ValueError("请提供联系人姓名。")
        contact = vault.meeting_context(name)
        return _tool_result({"success": True, "contact": contact, "found": bool(contact)})
    except Exception as exc:
        return _tool_error(exc)


def _handle_record_interaction(args: dict, **_: Any) -> str:
    try:
        saved = vault.record_interaction(
            name=str(args.get("name") or ""),
            summary=str(args.get("summary") or ""),
            occurred_at=str(args.get("occurred_at") or vault.utc_now()),
            interaction_type=str(args.get("interaction_type") or "沟通"),
            organization=args.get("organization"),
            city=args.get("city"),
            role=args.get("role"),
            certainty=str(args.get("certainty") or "confirmed"),
        )
        return _tool_result({
            "success": True,
            "saved": saved,
            "user_notice": f"已记录到人脉地图：{saved['contact_name']}的{args.get('interaction_type') or '沟通'}。",
            "instruction": "在给用户的自然语言回复中原样或等义展示 user_notice，并允许用户直接说‘这条不该记录’或‘修改刚才记录’。",
        })
    except Exception as exc:
        return _tool_error(exc)


def _handle_record_commitment(args: dict, **_: Any) -> str:
    try:
        saved = vault.record_commitment(
            name=str(args.get("name") or ""),
            description=str(args.get("description") or ""),
            due_at=args.get("due_at"),
            certainty=str(args.get("certainty") or "confirmed"),
        )
        return _tool_result({
            "success": True,
            "saved": saved,
            "user_notice": f"已更新到人脉地图：已记录{saved['contact_name']}的承诺事项。",
            "instruction": "在给用户的自然语言回复中展示 user_notice。",
        })
    except Exception as exc:
        return _tool_error(exc)


def _handle_create_followup(args: dict, **_: Any) -> str:
    try:
        saved = vault.create_followup(
            name=str(args.get("name") or ""),
            title=str(args.get("title") or ""),
            due_at=args.get("due_at"),
        )
        return _tool_result({
            "success": True,
            "saved": saved,
            "user_notice": f"已更新到人脉地图：已为{saved['contact_name']}添加待跟进事项。",
            "instruction": "在给用户的自然语言回复中展示 user_notice。",
        })
    except Exception as exc:
        return _tool_error(exc)


def _handle_prepare_meeting(args: dict, **_: Any) -> str:
    try:
        name = str(args.get("name") or "").strip()
        if not name:
            raise ValueError("请提供会面对象姓名。")
        context = vault.meeting_context(name)
        if not context:
            return _tool_result({"success": True, "found": False, "message": f"人脉地图中暂未找到{name}。可先根据用户当前提供的信息准备会面，并在会后自动沉淀。"})
        return _tool_result({
            "success": True,
            "found": True,
            "meeting_at": args.get("meeting_at"),
            "meeting_context": context,
            "instruction": "基于已确认事实、最近互动和未完成承诺生成会前准备；推断必须明确标注依据，禁止虚构对方关注点。",
        })
    except Exception as exc:
        return _tool_error(exc)


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required}}


TOOL_DEFINITIONS = (
    ("relationship_map_search", _schema("relationship_map_search", "搜索当前用户的人脉资产。只返回必要摘要，不暴露电话、地址等敏感字段。", {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"]), _handle_search),
    ("relationship_map_contact", _schema("relationship_map_contact", "查看一位联系人的关系资料、最近互动与未完成承诺。", {"name": {"type": "string"}}, ["name"]), _handle_contact),
    ("relationship_map_record_interaction", _schema("relationship_map_record_interaction", "把明确的人脉互动追加到当前用户的时间线。普通记录自动保存，并返回用户可见的已记录提示。", {"name": {"type": "string"}, "summary": {"type": "string"}, "occurred_at": {"type": "string"}, "interaction_type": {"type": "string"}, "organization": {"type": "string"}, "city": {"type": "string"}, "role": {"type": "string"}, "certainty": {"type": "string", "enum": ["confirmed", "inferred", "pending"]}}, ["name", "summary"]), _handle_record_interaction),
    ("relationship_map_record_commitment", _schema("relationship_map_record_commitment", "记录一项明确承诺。不能把推断写成事实。", {"name": {"type": "string"}, "description": {"type": "string"}, "due_at": {"type": "string"}, "certainty": {"type": "string", "enum": ["confirmed", "inferred", "pending"]}}, ["name", "description"]), _handle_record_commitment),
    ("relationship_map_create_followup", _schema("relationship_map_create_followup", "创建一项待跟进事项。普通待办自动保存，并返回用户可见的已更新提示。", {"name": {"type": "string"}, "title": {"type": "string"}, "due_at": {"type": "string"}}, ["name", "title"]), _handle_create_followup),
    ("relationship_map_prepare_meeting", _schema("relationship_map_prepare_meeting", "读取已有关系资产，为会面准备可信的背景、最近互动、承诺和风险提示。", {"name": {"type": "string"}, "meeting_at": {"type": "string"}}, ["name"]), _handle_prepare_meeting),
)
