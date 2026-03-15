"""Agent Tools — give the twin real capabilities beyond chatting.

The twin can now: search the web, generate documents, and interact with
external platforms. Uses a tool-call pattern: AI decides which tool to use,
system executes it, result fed back to AI for final response.
"""

import json
import logging
import re
from datetime import datetime

import httpx

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL

logger = logging.getLogger(__name__)

# --- Tool definitions (passed to AI so it knows what's available) ---

TOOL_DEFINITIONS = """
你有以下工具可以使用。当用户的请求需要用到工具时，输出JSON格式的工具调用：

1. web_search: 搜索互联网获取信息
   用法: {"tool": "web_search", "query": "搜索关键词"}

2. generate_doc: 生成文档/总结/报告
   用法: {"tool": "generate_doc", "title": "文档标题", "request": "用户的需求描述"}

3. send_platform_message: 在外部Agent平台发送消息
   用法: {"tool": "send_platform_message", "platform": "平台名", "message": "消息内容"}

如果不需要工具，直接正常回复。
如果需要工具，先输出工具调用JSON（用```tool标记），然后系统会返回结果。
"""


# --- Tool implementations ---

async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo Instant Answer API + HTML scraping fallback."""
    results = []

    # Method 1: DuckDuckGo Instant Answer API (no key needed)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            )
            data = resp.json()

            # Abstract (Wikipedia-style summary)
            if data.get("Abstract"):
                results.append(f"📖 {data['AbstractSource']}: {data['Abstract']}")

            # Related topics
            for topic in (data.get("RelatedTopics") or [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(f"• {topic['Text'][:200]}")

    except Exception as e:
        logger.warning(f"[AgentTools] DuckDuckGo search failed: {e}")

    # Method 2: Use AI to synthesize knowledge if search returned little
    if len(results) < 2:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 800,
                        "messages": [{"role": "user", "content": (
                            f"请搜索并整理关于「{query}」的最新信息。"
                            f"包含：1.核心概念 2.最新趋势 3.关键数据 4.未来展望。"
                            f"用中文，条理清晰，引用来源（如果知道）。不超过500字。"
                        )}],
                    },
                )
                ai_result = resp.json()["choices"][0]["message"]["content"].strip()
                results.append(ai_result)
        except Exception as e:
            logger.warning(f"[AgentTools] AI knowledge synthesis failed: {e}")

    if not results:
        return "搜索暂时不可用，请稍后再试。"

    return "\n\n".join(results)


async def generate_doc(title: str, request: str) -> str:
    """Generate a structured document/report based on user request."""
    if not AI_BASE_URL or not AI_API_KEY:
        return "文档生成功能暂时不可用。"

    prompt = (
        f"请根据以下需求，生成一份专业的文档。\n\n"
        f"标题：{title}\n"
        f"需求：{request}\n\n"
        f"要求：\n"
        f"- 结构清晰，有标题和小标题\n"
        f"- 内容专业、有深度\n"
        f"- 包含数据和案例（如果适用）\n"
        f"- 中文撰写\n"
        f"- 1000-2000字"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODEL,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"[AgentTools] Document generation failed: {e}")
        return "文档生成失败，请稍后再试。"


async def send_platform_message(platform: str, message: str) -> str:
    """Send a message on an external agent platform.

    Currently supports: reporting capability status.
    Actual platform integration requires platform-specific API credentials.
    """
    # For now, log the intent and return status
    logger.info(f"[AgentTools] Platform message to {platform}: {message[:100]}")
    return f"已准备好在{platform}平台发送消息。当平台API接入后将自动发送。"


# --- Tool execution engine ---

TOOLS = {
    "web_search": web_search,
    "generate_doc": generate_doc,
    "send_platform_message": send_platform_message,
}


def parse_tool_call(ai_response: str) -> dict | None:
    """Parse a tool call from AI response text."""
    # Look for ```tool ... ``` block
    tool_match = re.search(r'```tool\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
    if tool_match:
        try:
            return json.loads(tool_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Look for raw JSON with "tool" key
    json_match = re.search(r'\{[^{}]*"tool"\s*:\s*"[^"]+?"[^{}]*\}', ai_response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


async def execute_tool(tool_call: dict) -> str:
    """Execute a tool call and return the result."""
    tool_name = tool_call.get("tool", "")
    tool_fn = TOOLS.get(tool_name)
    if not tool_fn:
        return f"未知工具: {tool_name}"

    try:
        if tool_name == "web_search":
            return await tool_fn(tool_call.get("query", ""))
        elif tool_name == "generate_doc":
            return await tool_fn(tool_call.get("title", ""), tool_call.get("request", ""))
        elif tool_name == "send_platform_message":
            return await tool_fn(tool_call.get("platform", ""), tool_call.get("message", ""))
        else:
            return "工具执行失败"
    except Exception as e:
        logger.warning(f"[AgentTools] Tool execution failed: {e}")
        return f"工具执行出错: {str(e)}"


async def agent_reply_with_tools(
    profile, incoming_msg: str, from_user_id: str = ""
) -> str | None:
    """Generate a twin reply with tool-use capability.

    If the AI decides to use a tool, executes it and generates a final response
    incorporating the tool result. Otherwise returns a normal reply.
    """
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    from dualsoul.twin_engine.personality import get_twin_profile

    personality_block = profile.build_personality_prompt()
    safe_name = profile.display_name or "User"

    # Step 1: Ask AI if it needs tools
    system_prompt = (
        f"你是{safe_name}的数字分身，一个有能力的智能体。\n"
        f"{personality_block}\n\n"
        f"{TOOL_DEFINITIONS}\n\n"
        f"重要：你不仅能聊天，还能搜索信息、生成文档、与外部平台交互。"
        f"当用户请求需要这些能力时，主动使用工具。"
        f"回复要自然、有深度，展现你是一个有行动力的智能体。"
    )

    # Add narrative memory if available
    if from_user_id:
        try:
            from dualsoul.twin_engine.narrative_memory import get_narrative_context
            memories = get_narrative_context(profile.user_id, from_user_id, limit=3)
            if memories:
                mem_text = "\n".join(f"- {m['summary']} ({m['tone']})" for m in memories)
                system_prompt += f"\n\n[你和对方的过往记忆]\n{mem_text}"
        except Exception:
            pass

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": incoming_msg},
    ]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 500, "messages": messages},
            )
            ai_response = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"[AgentTools] Initial AI call failed: {e}")
        return None

    # Step 2: Check if AI wants to use a tool
    tool_call = parse_tool_call(ai_response)
    if not tool_call:
        # No tool needed — return the direct reply
        return ai_response

    # Step 3: Execute the tool
    logger.info(f"[AgentTools] Executing tool: {tool_call.get('tool')} for {safe_name}")
    tool_result = await execute_tool(tool_call)

    # Step 4: Feed tool result back to AI for final response
    messages.append({"role": "assistant", "content": ai_response})
    messages.append({"role": "user", "content": f"[工具执行结果]\n{tool_result}\n\n请根据以上结果，用{safe_name}的风格给出最终回复。自然、有条理、有深度。"})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 1500, "messages": messages},
            )
            final_response = resp.json()["choices"][0]["message"]["content"].strip()
            return final_response
    except Exception as e:
        logger.warning(f"[AgentTools] Final AI call failed: {e}")
        # Return tool result directly if AI synthesis fails
        return tool_result
