"""AI avatar generation — transform a real photo into a stylized digital twin avatar.

Uses Alibaba DashScope's portrait style repaint API (wanx-style-repaint-v1),
which is on the same platform as our Qwen chat model.
"""

import base64
import logging
import time

import httpx

from dualsoul.config import AI_API_KEY

logger = logging.getLogger(__name__)

# DashScope API endpoint (same API key as Qwen)
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"

# Style presets for twin avatars
# See: https://help.aliyun.com/zh/model-studio/style-repaint
TWIN_STYLES = {
    "anime": {"index": 2, "name_zh": "动漫", "name_en": "Anime"},
    "3d": {"index": 35, "name_zh": "3D立体", "name_en": "3D"},
    "cyber": {"index": 4, "name_zh": "未来科技", "name_en": "Futuristic"},
    "clay": {"index": 31, "name_zh": "黏土世界", "name_en": "Clay"},
    "pixel": {"index": 32, "name_zh": "像素世界", "name_en": "Pixel"},
    "ink": {"index": 5, "name_zh": "水墨", "name_en": "Ink Painting"},
    "retro": {"index": 0, "name_zh": "复古漫画", "name_en": "Retro Comic"},
}

DEFAULT_STYLE = "anime"


async def generate_twin_avatar(
    image_url: str,
    style: str = DEFAULT_STYLE,
) -> dict | None:
    """Generate a stylized twin avatar from a real photo.

    Args:
        image_url: URL of the source image (must be publicly accessible)
        style: Style key from TWIN_STYLES

    Returns:
        Dict with 'url' (generated image URL) and 'style', or None on failure.
    """
    if not AI_API_KEY:
        logger.warning("No AI_API_KEY configured, cannot generate avatar")
        return None

    style_info = TWIN_STYLES.get(style, TWIN_STYLES[DEFAULT_STYLE])
    style_index = style_info["index"]

    # Submit the async task
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                DASHSCOPE_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json={
                    "model": "wanx-style-repaint-v1",
                    "input": {
                        "image_url": image_url,
                        "style_index": style_index,
                    },
                },
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"Avatar generation submit failed: {e}")
        return None

    # Get task ID for polling
    task_id = data.get("output", {}).get("task_id")
    if not task_id:
        logger.warning(f"No task_id in response: {data}")
        return None

    # Poll for result (max 60 seconds)
    task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    for _ in range(30):
        await _async_sleep(2)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    task_url,
                    headers={"Authorization": f"Bearer {AI_API_KEY}"},
                )
                result = resp.json()
        except Exception as e:
            logger.warning(f"Avatar generation poll failed: {e}")
            continue

        status = result.get("output", {}).get("task_status")
        if status == "SUCCEEDED":
            results = result.get("output", {}).get("results", [])
            if results and results[0].get("url"):
                return {
                    "url": results[0]["url"],
                    "style": style,
                    "style_name": style_info,
                }
            logger.warning(f"No image URL in result: {result}")
            return None
        elif status == "FAILED":
            logger.warning(f"Avatar generation failed: {result}")
            return None
        # PENDING or RUNNING — continue polling

    logger.warning("Avatar generation timed out")
    return None


async def generate_twin_avatar_from_base64(
    image_base64: str,
    style: str = DEFAULT_STYLE,
    save_path: str | None = None,
) -> dict | None:
    """Generate twin avatar from a base64-encoded image.

    Since DashScope needs a URL, we first need to upload the image.
    As a workaround, we save it temporarily and use the server's URL.

    Args:
        image_base64: Base64-encoded image data (with or without data URI prefix)
        style: Style key from TWIN_STYLES
        save_path: Optional path to save the source image temporarily

    Returns:
        Dict with 'image_base64' of the generated avatar, or None on failure.
    """
    if not AI_API_KEY:
        return None

    # Strip data URI prefix
    img_data = image_base64
    if "," in img_data:
        img_data = img_data.split(",", 1)[1]

    style_info = TWIN_STYLES.get(style, TWIN_STYLES[DEFAULT_STYLE])
    style_index = style_info["index"]

    # Use DashScope with base64 input directly
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                DASHSCOPE_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json={
                    "model": "wanx-style-repaint-v1",
                    "input": {
                        "image_url": f"data:image/png;base64,{img_data}",
                        "style_index": style_index,
                    },
                },
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"Avatar generation submit failed: {e}")
        return None

    task_id = data.get("output", {}).get("task_id")
    if not task_id:
        # Maybe the API doesn't support base64 directly — log the error
        logger.warning(f"No task_id in response: {data}")
        return None

    # Poll for result
    task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    for _ in range(30):
        await _async_sleep(2)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    task_url,
                    headers={"Authorization": f"Bearer {AI_API_KEY}"},
                )
                result = resp.json()
        except Exception as e:
            logger.warning(f"Avatar generation poll failed: {e}")
            continue

        status = result.get("output", {}).get("task_status")
        if status == "SUCCEEDED":
            results = result.get("output", {}).get("results", [])
            if results and results[0].get("url"):
                # Download the generated image and return as base64
                try:
                    async with httpx.AsyncClient(timeout=30) as dl_client:
                        img_resp = await dl_client.get(results[0]["url"])
                        if img_resp.status_code == 200:
                            generated_b64 = base64.b64encode(img_resp.content).decode()
                            return {
                                "image_base64": generated_b64,
                                "style": style,
                                "source_url": results[0]["url"],
                            }
                except Exception as e:
                    logger.warning(f"Failed to download generated avatar: {e}")
            return None
        elif status == "FAILED":
            logger.warning(f"Avatar generation failed: {result}")
            return None

    logger.warning("Avatar generation timed out")
    return None


def get_available_styles() -> list[dict]:
    """Return list of available twin avatar styles for the frontend."""
    return [
        {"key": k, "name_zh": v["name_zh"], "name_en": v["name_en"]}
        for k, v in TWIN_STYLES.items()
    ]


async def _async_sleep(seconds: float):
    """Async sleep without blocking."""
    import asyncio
    await asyncio.sleep(seconds)
