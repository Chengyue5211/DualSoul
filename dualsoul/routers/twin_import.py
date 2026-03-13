"""Twin Import router — import and sync twin data from Nianlun (年轮)."""

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.database import gen_id, get_db
from dualsoul.models import TwinImportRequest, TwinSyncRequest

router = APIRouter(prefix="/api/twin", tags=["Twin Import"])


@router.post("/import")
async def import_twin(req: TwinImportRequest, user=Depends(get_current_user)):
    """Import a full twin data package from Nianlun (年轮).

    Accepts Twin Portable Format v1.0 payload, stores core personality data
    in hot columns and full payload in cold storage.
    """
    uid = user["user_id"]
    data = req.data

    if not data:
        return {"success": False, "error": "Empty data payload"}

    with get_db() as db:
        # Deactivate existing profiles
        db.execute(
            "UPDATE twin_profiles SET is_active=0 WHERE user_id=?", (uid,)
        )

        # Determine next version
        row = db.execute(
            "SELECT MAX(version) as mv FROM twin_profiles WHERE user_id=?",
            (uid,),
        ).fetchone()
        next_version = (row["mv"] or 0) + 1 if row else 1

        # Extract core fields
        twin = data.get("twin", {})
        cert = data.get("certificate", {})
        skeleton = data.get("skeleton", {})
        dims = skeleton.get("dimension_profiles", {})

        import json

        profile_id = gen_id("tp_")
        db.execute(
            """
            INSERT INTO twin_profiles
            (profile_id, user_id, source, version, is_active,
             twin_name, training_status, quality_score, self_awareness, interaction_count,
             dim_judgement, dim_cognition, dim_expression, dim_relation, dim_sovereignty,
             value_order, behavior_patterns, speech_style, boundaries,
             certificate, raw_import)
            VALUES (?, ?, 'nianlun', ?, 1,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?)
            """,
            (
                profile_id, uid, next_version,
                twin.get("twin_name", cert.get("twin_name", "")),
                twin.get("training_status", ""),
                twin.get("quality_score", 0.0),
                twin.get("self_awareness", 0.0),
                twin.get("interaction_count", 0),
                json.dumps(dims.get("judgement", {}), ensure_ascii=False),
                json.dumps(dims.get("cognition", {}), ensure_ascii=False),
                json.dumps(dims.get("expression", {}), ensure_ascii=False),
                json.dumps(dims.get("relation", {}), ensure_ascii=False),
                json.dumps(dims.get("sovereignty", {}), ensure_ascii=False),
                json.dumps(skeleton.get("value_order", []), ensure_ascii=False),
                json.dumps(skeleton.get("behavior_patterns", []), ensure_ascii=False),
                json.dumps(twin.get("speech_style", {}), ensure_ascii=False),
                json.dumps(twin.get("boundaries", {}), ensure_ascii=False),
                json.dumps(cert, ensure_ascii=False),
                json.dumps(data, ensure_ascii=False),
            ),
        )

        # Import memories
        memories = data.get("memories", [])
        for mem in memories:
            mem_id = gen_id("tm_")
            db.execute(
                """
                INSERT INTO twin_memories
                (memory_id, user_id, memory_type, period_start, period_end,
                 summary_text, emotional_tone, themes, key_events, growth_signals)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mem_id, uid,
                    mem.get("memory_type", "weekly"),
                    mem.get("period_start", ""),
                    mem.get("period_end", ""),
                    mem.get("summary_text", ""),
                    mem.get("emotional_tone", ""),
                    json.dumps(mem.get("themes", []), ensure_ascii=False),
                    json.dumps(mem.get("key_events", []), ensure_ascii=False),
                    json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
                ),
            )

        # Import entities
        entities = data.get("entities", [])
        for ent in entities:
            ent_id = gen_id("te_")
            db.execute(
                """
                INSERT INTO twin_entities
                (entity_id, user_id, entity_name, entity_type,
                 importance_score, mention_count, context, relations)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ent_id, uid,
                    ent.get("entity_name", ""),
                    ent.get("entity_type", "thing"),
                    ent.get("importance_score", 0.0),
                    ent.get("mention_count", 0),
                    json.dumps(ent.get("context", ""), ensure_ascii=False),
                    json.dumps(ent.get("relations", []), ensure_ascii=False),
                ),
            )

        # Update user's twin_source + backward-compatible fields
        personality_text = twin.get("personality", "")
        if isinstance(personality_text, dict):
            personality_text = personality_text.get("description", str(personality_text))
        style_text = twin.get("speech_style", "")
        if isinstance(style_text, dict):
            style_text = style_text.get("description", str(style_text))

        db.execute(
            "UPDATE users SET twin_source='nianlun', "
            "twin_personality=CASE WHEN ?!='' THEN ? ELSE twin_personality END, "
            "twin_speech_style=CASE WHEN ?!='' THEN ? ELSE twin_speech_style END "
            "WHERE user_id=?",
            (personality_text, personality_text, style_text, style_text, uid),
        )

    return {
        "success": True,
        "profile_id": profile_id,
        "version": next_version,
        "imported": {
            "memories": len(memories),
            "entities": len(entities),
        },
    }


@router.post("/sync")
async def sync_twin(req: TwinSyncRequest, user=Depends(get_current_user)):
    """Incremental sync — merge new data from Nianlun since last sync.

    Only imports new memories and entities; updates the active profile's
    dimension scores if provided.
    """
    uid = user["user_id"]
    data = req.data

    if not data:
        return {"success": False, "error": "Empty sync data"}

    import json
    counts = {"memories": 0, "entities": 0, "profile_updated": False}

    with get_db() as db:
        # Update active profile dimensions if provided
        skeleton = data.get("skeleton", {})
        dims = skeleton.get("dimension_profiles", {})
        if dims:
            updates = []
            params = []
            for dim_key in ("judgement", "cognition", "expression", "relation", "sovereignty"):
                if dim_key in dims:
                    col = f"dim_{dim_key}"
                    updates.append(f"{col}=?")
                    params.append(json.dumps(dims[dim_key], ensure_ascii=False))

            if skeleton.get("value_order"):
                updates.append("value_order=?")
                params.append(json.dumps(skeleton["value_order"], ensure_ascii=False))
            if skeleton.get("behavior_patterns"):
                updates.append("behavior_patterns=?")
                params.append(json.dumps(skeleton["behavior_patterns"], ensure_ascii=False))

            if updates:
                updates.append("updated_at=datetime('now','localtime')")
                params.append(uid)
                db.execute(
                    f"UPDATE twin_profiles SET {','.join(updates)} "
                    "WHERE user_id=? AND is_active=1",
                    params,
                )
                counts["profile_updated"] = True

        # Insert new memories
        for mem in data.get("memories", []):
            mem_id = gen_id("tm_")
            db.execute(
                """
                INSERT INTO twin_memories
                (memory_id, user_id, memory_type, period_start, period_end,
                 summary_text, emotional_tone, themes, key_events, growth_signals)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mem_id, uid,
                    mem.get("memory_type", "weekly"),
                    mem.get("period_start", ""),
                    mem.get("period_end", ""),
                    mem.get("summary_text", ""),
                    mem.get("emotional_tone", ""),
                    json.dumps(mem.get("themes", []), ensure_ascii=False),
                    json.dumps(mem.get("key_events", []), ensure_ascii=False),
                    json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
                ),
            )
            counts["memories"] += 1

        # Insert new entities (upsert by name)
        for ent in data.get("entities", []):
            existing = db.execute(
                "SELECT entity_id FROM twin_entities WHERE user_id=? AND entity_name=?",
                (uid, ent.get("entity_name", "")),
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE twin_entities SET importance_score=?, mention_count=?, "
                    "context=?, relations=? WHERE entity_id=?",
                    (
                        ent.get("importance_score", 0.0),
                        ent.get("mention_count", 0),
                        json.dumps(ent.get("context", ""), ensure_ascii=False),
                        json.dumps(ent.get("relations", []), ensure_ascii=False),
                        existing["entity_id"],
                    ),
                )
            else:
                ent_id = gen_id("te_")
                db.execute(
                    """
                    INSERT INTO twin_entities
                    (entity_id, user_id, entity_name, entity_type,
                     importance_score, mention_count, context, relations)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ent_id, uid,
                        ent.get("entity_name", ""),
                        ent.get("entity_type", "thing"),
                        ent.get("importance_score", 0.0),
                        ent.get("mention_count", 0),
                        json.dumps(ent.get("context", ""), ensure_ascii=False),
                        json.dumps(ent.get("relations", []), ensure_ascii=False),
                    ),
                )
            counts["entities"] += 1

    return {"success": True, "synced": counts}


@router.get("/status")
async def twin_status(user=Depends(get_current_user)):
    """Check the current twin import status — source, version, stats."""
    uid = user["user_id"]

    with get_db() as db:
        user_row = db.execute(
            "SELECT twin_source FROM users WHERE user_id=?", (uid,)
        ).fetchone()

        result = {
            "twin_source": user_row["twin_source"] if user_row else "local",
            "nianlun_profile": None,
        }

        if result["twin_source"] == "nianlun":
            tp = db.execute(
                "SELECT profile_id, version, twin_name, quality_score, "
                "training_status, interaction_count, imported_at, updated_at "
                "FROM twin_profiles WHERE user_id=? AND is_active=1 "
                "ORDER BY version DESC LIMIT 1",
                (uid,),
            ).fetchone()
            if tp:
                mem_count = db.execute(
                    "SELECT COUNT(*) as cnt FROM twin_memories WHERE user_id=?",
                    (uid,),
                ).fetchone()
                ent_count = db.execute(
                    "SELECT COUNT(*) as cnt FROM twin_entities WHERE user_id=?",
                    (uid,),
                ).fetchone()
                result["nianlun_profile"] = {
                    "profile_id": tp["profile_id"],
                    "version": tp["version"],
                    "twin_name": tp["twin_name"],
                    "quality_score": tp["quality_score"],
                    "training_status": tp["training_status"],
                    "interaction_count": tp["interaction_count"],
                    "memories_count": mem_count["cnt"] if mem_count else 0,
                    "entities_count": ent_count["cnt"] if ent_count else 0,
                    "imported_at": tp["imported_at"],
                    "updated_at": tp["updated_at"],
                }

    return {"success": True, **result}
