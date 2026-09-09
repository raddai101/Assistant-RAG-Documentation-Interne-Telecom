from flask import Blueprint, jsonify, g, request

from app.extensions import db
from app.modules.conversations.service import ConversationService
from app.modules.identity.decorators import require_auth

conversations_bp = Blueprint("conversations", __name__)
service = ConversationService()


def _serialize_conversation(conversation, include_messages=False, messages=None):
    data = {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }
    if include_messages:
        data["messages"] = [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message in (messages or [])
        ]
    return data


@conversations_bp.post("")
@require_auth
def create_conversation():
    # Une conversation vide n'est pas créée : elle naît avec le premier message.
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    conversation = service.repository.create(g.current_user.id, title or "Nouvelle discussion")
    db.session.commit()
    return jsonify({
        "success": True,
        "data": _serialize_conversation(conversation),
        "message": None,
        "error": None,
    }), 201


@conversations_bp.get("")
@require_auth
def list_conversations():
    conversations = service.list_for_user(g.current_user.id)
    return jsonify({
        "success": True,
        "data": {"conversations": [_serialize_conversation(c) for c in conversations]},
        "message": None,
        "error": None,
    })


@conversations_bp.get("/<int:conversation_id>")
@require_auth
def get_conversation(conversation_id: int):
    conversation = service.ensure_owned(conversation_id, g.current_user.id)
    if conversation is None:
        return jsonify({
            "success": False, "data": None, "message": None,
            "error": "Conversation introuvable.",
        }), 404

    messages = service.repository.list_messages(
        conversation_id, g.current_user.id, limit=100
    )
    return jsonify({
        "success": True,
        "data": _serialize_conversation(conversation, True, messages),
        "message": None,
        "error": None,
    })


@conversations_bp.delete("/<int:conversation_id>")
@require_auth
def delete_conversation(conversation_id: int):
    if not service.delete_owned(conversation_id, g.current_user.id):
        return jsonify({
            "success": False, "data": None, "message": None,
            "error": "Conversation introuvable.",
        }), 404
    return jsonify({
        "success": True, "data": None, "message": "Conversation supprimée.", "error": None
    })
