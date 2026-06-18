"""
星火智造云打印 — 微信 JS-SDK 签名接口

让微信客户端内打开的网页能调用 wx.chooseMessageFile 等原生能力。
"""

import hashlib
import logging
import random
import string
import time
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, HTTPException, Query

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wechat", tags=["微信 JS-SDK"])

# ── 全局 token/ticket 缓存 ──
_token_cache: dict = {"access_token": "", "expires_at": datetime.min.replace(tzinfo=timezone.utc)}
_ticket_cache: dict = {"ticket": "", "expires_at": datetime.min.replace(tzinfo=timezone.utc)}


def _fetch_access_token() -> str:
    """
    获取微信公众号 access_token (缓存 7000s, 微信有效期 7200s)
    https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html
    """
    now = datetime.now(timezone.utc)
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise HTTPException(status_code=500, detail="微信未配置 (缺 APP_ID / APP_SECRET)")

    try:
        resp = requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.WECHAT_APP_ID,
                "secret": settings.WECHAT_APP_SECRET,
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" not in data:
            logger.error(f"微信 access_token 获取失败: {data}")
            raise HTTPException(status_code=500, detail=f"微信 token 失败: {data.get('errmsg', 'unknown')}")

        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = now + timedelta(seconds=data.get("expires_in", 7200) - 200)
        return data["access_token"]

    except requests.exceptions.RequestException as e:
        logger.error(f"微信 access_token 请求异常: {e}")
        raise HTTPException(status_code=502, detail=f"微信 API 不可达: {e}")


def _fetch_jsapi_ticket() -> str:
    """
    获取 jsapi_ticket (缓存 7000s)
    https://developers.weixin.qq.com/doc/offiaccount/OA_Web_Apps/JS-SDK.html#54
    """
    now = datetime.now(timezone.utc)
    if _ticket_cache["ticket"] and now < _ticket_cache["expires_at"]:
        return _ticket_cache["ticket"]

    token = _fetch_access_token()

    try:
        resp = requests.get(
            "https://api.weixin.qq.com/cgi-bin/ticket/getticket",
            params={"access_token": token, "type": "jsapi"},
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            logger.error(f"微信 jsapi_ticket 获取失败: {data}")
            raise HTTPException(status_code=500, detail=f"微信 ticket 失败: {data.get('errmsg', 'unknown')}")

        _ticket_cache["ticket"] = data["ticket"]
        _ticket_cache["expires_at"] = now + timedelta(seconds=data.get("expires_in", 7200) - 200)
        return data["ticket"]

    except requests.exceptions.RequestException as e:
        logger.error(f"微信 jsapi_ticket 请求异常: {e}")
        raise HTTPException(status_code=502, detail=f"微信 API 不可达: {e}")


@router.get("/signature")
async def wechat_signature(
    url: str = Query(..., description="当前网页的完整 URL (不含 # 及之后)"),
):
    """
    生成微信 JS-SDK 签名

    前端调用:
      GET /api/wechat/signature?url=https://paint.example.com/

    前端使用返回的参数调用 wx.config()

    如果未配置 WECHAT_APP_ID, 返回 disabled 状态 (前端不初始化 JSSDK)
    """
    if not settings.WECHAT_APP_ID:
        return {
            "disabled": True,
            "message": "微信 JS-SDK 未配置 (缺 WECHAT_APP_ID), 微信功能不可用",
        }

    try:
        ticket = _fetch_jsapi_ticket()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 ticket 异常: {e}")
        raise HTTPException(status_code=500, detail=f"签名生成失败: {e}")

    noncestr = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    timestamp = str(int(time.time()))

    # 微信签名算法: sha1(jsapi_ticket=xxx&noncestr=xxx&timestamp=xxx&url=xxx)
    sign_str = f"jsapi_ticket={ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
    signature = hashlib.sha1(sign_str.encode()).hexdigest()

    logger.debug(f"微信签名: url={url[:80]} sign={signature[:8]}...")

    return {
        "disabled": False,
        "appId": settings.WECHAT_APP_ID,
        "timestamp": timestamp,
        "nonceStr": noncestr,
        "signature": signature,
    }
