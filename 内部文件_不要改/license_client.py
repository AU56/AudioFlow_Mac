# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import json
import platform
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from settings import BUILTIN_LICENSE_SERVER_URL, LICENSE_SERVER_CANDIDATES, VERIFY_SECRET, app_data_dir

LICENSE_FILE = app_data_dir() / "license.json"
OFFLINE_GRACE_SECONDS = 12 * 3600


def machine_code() -> str:
    raw = f"{platform.node()}|{platform.system()}|{platform.machine()}|{uuid.getnode()}"
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest().upper()[:32]


def _sign_payload(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(VERIFY_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()


def verify_server_signature(payload: dict[str, Any], signature: str) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(_sign_payload(payload), signature)


def save_license(data: dict[str, Any]) -> None:
    data = dict(data)
    data["verified_at"] = time.time()
    LICENSE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_license() -> None:
    try:
        LICENSE_FILE.unlink()
    except FileNotFoundError:
        pass


def load_license() -> dict[str, Any] | None:
    if not LICENSE_FILE.exists():
        return None
    try:
        return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def offline_grace_status() -> tuple[bool, str, dict[str, Any] | None]:
    data = load_license()
    if not data:
        return False, "未激活", None
    ok, msg, payload = local_status()
    if not ok:
        return False, msg, payload
    verified_at = float(data.get("verified_at") or (payload or {}).get("issued_at") or 0)
    remain = OFFLINE_GRACE_SECONDS - int(time.time() - verified_at)
    if remain <= 0:
        return False, "在线校验失败，离线宽限已超过 12 小时", payload
    return True, f"{msg}｜离线宽限 {remain // 3600} 小时{remain % 3600 // 60} 分钟", payload


def _previous_machine_code() -> str:
    payload = (load_license() or {}).get("payload") or {}
    return str(payload.get("machine_code") or "").strip().upper()


def _server_candidates(preferred: str | None = None) -> list[str]:
    values = []
    if preferred:
        values.append(preferred)
    values.extend(LICENSE_SERVER_CANDIDATES)
    values.append(BUILTIN_LICENSE_SERVER_URL)
    seen = set()
    result = []
    for raw in values:
        base = str(raw or "").strip().rstrip("/")
        if base and base not in seen:
            result.append(base)
            seen.add(base)
    return result


def local_status() -> tuple[bool, str, dict[str, Any] | None]:
    data = load_license()
    if not data:
        return False, "未激活", None
    payload = data.get("payload") or {}
    sig = data.get("signature") or ""
    if not verify_server_signature(payload, sig):
        return False, "授权文件校验失败", None
    current_machine = machine_code()
    if payload.get("machine_code") != current_machine:
        return False, "授权设备不匹配", None
    if payload.get("permanent") or payload.get("card_type") == "lifetime":
        return True, "永久卡｜已激活｜离线可用", payload
    expires_at = float(payload.get("expires_at") or 0)
    now = time.time()
    if expires_at <= now:
        return False, "授权已到期", payload
    card_type = payload.get("card_type_name") or payload.get("card_type") or "授权"
    expire_date = time.strftime("%Y-%m-%d", time.localtime(expires_at))
    remain_seconds = int(expires_at - now)
    if remain_seconds < 48 * 3600:
        remain = f"剩余 {max(0, remain_seconds // 3600)} 小时"
    else:
        remain = f"剩余 {remain_seconds // 86400} 天"
    return True, f"{card_type}｜{remain}｜到期：{expire_date}", payload


def activate_license(card_key: str, server_url: str | None = None) -> tuple[bool, str, dict[str, Any] | None]:
    card_key = card_key.strip()
    if not card_key:
        return False, "请输入卡密", None
    current_payload = (load_license() or {}).get("payload") or {}
    current_card_key = str(current_payload.get("card_key") or "").strip()
    errors = []
    server_messages = []
    for base in _server_candidates(server_url):
        try:
            resp = requests.post(
                f"{base}/api/license/activate",
                json={
                    "card_key": card_key,
                    "machine_code": machine_code(),
                    "previous_machine_code": _previous_machine_code(),
                    "current_card_key": current_card_key if current_card_key and current_card_key != card_key else "",
                },
                timeout=10,
            )
            data = resp.json()
        except Exception as e:
            errors.append(f"{base}：{e}")
            continue
        if not data.get("ok"):
            server_messages.append(f"{base}：{data.get('message') or '激活失败'}")
            continue
        payload = data.get("payload") or {}
        sig = data.get("signature") or ""
        if not verify_server_signature(payload, sig):
            return False, "服务器签名校验失败，请检查客户端与后台密钥是否一致", None
        save_license({"payload": payload, "signature": sig, "server_url": base})
        return True, data.get("message") or "激活成功", payload
    else:
        if server_messages:
            return False, server_messages[-1], None
        return False, "连接授权服务器失败：\n" + "\n".join(errors[-3:]), None


def online_verify() -> tuple[bool, str, dict[str, Any] | None]:
    lic = load_license()
    if not lic:
        return False, "未激活", None
    key = (lic.get("payload") or {}).get("card_key")
    ok_local, local_msg, local_payload = local_status()
    if ok_local and ((local_payload or {}).get("permanent") or (local_payload or {}).get("card_type") == "lifetime"):
        return True, local_msg, local_payload
    errors = []
    server_messages = []
    for base in _server_candidates(lic.get("server_url")):
        try:
            resp = requests.post(
                f"{base}/api/license/verify",
                json={"card_key": key, "machine_code": machine_code(), "previous_machine_code": _previous_machine_code()},
                timeout=10,
            )
            data = resp.json()
        except Exception as e:
            errors.append(f"{base}：{e}")
            continue
        if not data.get("ok"):
            message = data.get("message") or "授权无效"
            server_messages.append(f"{base}：{message}")
            if "不存在" in message or "not found" in message.lower():
                clear_license()
                return False, "服务器没有这张卡密，本地旧授权已清除。请使用当前公网后台生成的新卡密重新激活。", None
            continue
        payload = data.get("payload") or {}
        sig = data.get("signature") or ""
        if not verify_server_signature(payload, sig):
            return False, "服务器签名校验失败", None
        save_license({"payload": payload, "signature": sig, "server_url": base})
        return True, data.get("message") or "授权有效", payload
    else:
        if server_messages:
            return False, server_messages[-1], None
        grace_ok, grace_msg, grace_payload = offline_grace_status()
        if grace_ok:
            return True, grace_msg, grace_payload
        return False, "在线校验失败：\n" + "\n".join(errors[-3:]), None
