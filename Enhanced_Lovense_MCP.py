# Enhanced_Lovense_MCP.py
# Lovense MCP Server with Standard API for Remote Control
# Updated: 2026-01-21
# Purpose: Enable autonomous, context-aware control of Lovense devices over the internet

from mcp.server.fastmcp import FastMCP
import sys
import logging
import os
import requests
import hashlib
import threading
from typing import Optional, Dict
import json
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Enhanced_Lovense_MCP')

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stderr.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')

# Create MCP server
mcp = FastMCP("Enhanced_Lovense_MCP")

# ========================
# GLOBAL STATE
# ========================

# Developer token (from Lovense developer dashboard)
DEVELOPER_TOKEN = os.getenv("LOVENSE_DEVELOPER_TOKEN", "")

# Server's public URL for callbacks
CALLBACK_URL = os.getenv("LOVENSE_CALLBACK_URL", "")

# Connected users storage: {uid: {domain, httpsPort, toys, ...}}
connected_users: Dict[str, dict] = {}
users_lock = threading.Lock()

# Default user ID for single-user mode
DEFAULT_UID = "angela"

# ========================
# LOVENSE STANDARD API
# ========================

LOVENSE_API_BASE = "https://api.lovense.com/api/lan"

def get_qr_code(uid: str = DEFAULT_UID, uname: str = "User") -> dict:
    """
    Generate a QR code for user to scan with Lovense Remote app.

    Args:
        uid: Unique user identifier
        uname: Display name for the user

    Returns:
        dict with qrcode URL and code for manual entry
    """
    if not DEVELOPER_TOKEN:
        return {"success": False, "error": "Developer token not configured"}

    # Generate user token (MD5 of uid + secret)
    utoken = hashlib.md5(f"{uid}_lovense_mcp".encode()).hexdigest()

    url = f"{LOVENSE_API_BASE}/getQrCode"
    data = {
        "token": DEVELOPER_TOKEN,
        "uid": uid,
        "uname": uname,
        "utoken": utoken,
        "v": 2
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        if result.get("result") == True or result.get("code") == 0:
            logger.info(f"✅ QR code generated for user {uid}")
            return {
                "success": True,
                "qrcode": result.get("message", ""),
                "code": result.get("code", ""),
                "uid": uid
            }
        else:
            error = result.get("message", "Unknown error")
            logger.error(f"❌ QR code generation failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"❌ QR code request failed: {e}")
        return {"success": False, "error": str(e)}


def send_command_to_user(uid: str, command: str, action: str,
                         time_sec: int = 0, toy: str = "", **kwargs) -> dict:
    """
    Send command to a connected user's toys.

    First tries direct connection via callback info, then falls back to Server API.
    """
    with users_lock:
        user = connected_users.get(uid)

    if user:
        # Try direct connection first (faster, no cloud latency)
        result = send_command_direct(user, command, action, time_sec, toy, **kwargs)
        if result.get("success"):
            return result
        logger.warning(f"Direct connection failed, trying Server API")

    # Fall back to Server API
    return send_command_server_api(uid, command, action, time_sec, toy, **kwargs)


def send_command_direct(user: dict, command: str, action: str,
                       time_sec: int = 0, toy: str = "", **kwargs) -> dict:
    """Send command directly to user's device via local connection info."""
    domain = user.get("domain")
    https_port = user.get("httpsPort")

    if not domain or not https_port:
        return {"success": False, "error": "No direct connection info"}

    url = f"https://{domain}:{https_port}/command"
    data = {
        "command": command,
        "action": action,
        "timeSec": time_sec,
        "toy": toy,
        "apiVer": 1,
        **kwargs
    }

    try:
        response = requests.post(url, json=data, timeout=5, verify=False)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Direct command sent: {action}")
            return {"success": True, "result": result, "method": "direct"}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_command_server_api(uid: str, command: str, action: str,
                           time_sec: int = 0, toy: str = "", **kwargs) -> dict:
    """Send command via Lovense Server API (cloud relay)."""
    if not DEVELOPER_TOKEN:
        return {"success": False, "error": "Developer token not configured"}

    url = f"{LOVENSE_API_BASE}/v2/command"
    data = {
        "token": DEVELOPER_TOKEN,
        "uid": uid,
        "command": command,
        "action": action,
        "timeSec": time_sec,
        "toy": toy,
        "apiVer": 2,
        **kwargs
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        if result.get("result") == True or result.get("code") == 0:
            logger.info(f"✅ Server API command sent: {action}")
            return {"success": True, "result": result, "method": "server_api"}
        else:
            error = result.get("message", "Command failed")
            logger.error(f"❌ Server API command failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"❌ Server API request failed: {e}")
        return {"success": False, "error": str(e)}


# ========================
# CALLBACK HANDLER
# ========================

async def lovense_callback(request: Request) -> JSONResponse:
    """
    Handle callbacks from Lovense Remote app after QR code scan.

    The app sends connection info including domain, ports, and toy list.
    """
    try:
        data = await request.json()
        logger.info(f"📥 Lovense callback received: {json.dumps(data, indent=2)}")

        uid = data.get("uid", DEFAULT_UID)

        with users_lock:
            connected_users[uid] = {
                "domain": data.get("domain"),
                "httpsPort": data.get("httpsPort"),
                "httpPort": data.get("httpPort"),
                "wsPort": data.get("wsPort"),
                "wssPort": data.get("wssPort"),
                "platform": data.get("platform"),
                "appVersion": data.get("appVersion"),
                "toys": data.get("toys", {}),
                "utoken": data.get("utoken"),
            }

        logger.info(f"✅ User {uid} connected! Toys: {data.get('toys', {})}")

        return JSONResponse({"result": True, "message": "OK"})

    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        return JSONResponse({"result": False, "message": str(e)}, status_code=400)


# ========================
# MCP TOOLS
# ========================

@mcp.tool()
def get_qr_code_link(user_id: str = DEFAULT_UID, display_name: str = "User") -> dict:
    """
    Generate a QR code for linking Lovense Remote app.

    The user must scan this QR code with their Lovense Remote app to connect.
    After scanning, their toys will be available for control.

    Args:
        user_id: Unique identifier for this user (default: "angela")
        display_name: Name to show in the Lovense app

    Returns:
        dict with QR code URL that user should scan
    """
    return get_qr_code(user_id, display_name)


@mcp.tool()
def get_connected_users() -> dict:
    """
    Get list of users who have connected via QR code scan.

    Returns:
        dict with list of connected users and their toy info
    """
    with users_lock:
        users_list = []
        for uid, data in connected_users.items():
            users_list.append({
                "uid": uid,
                "platform": data.get("platform"),
                "toys": data.get("toys", {}),
                "connected": True
            })

    return {
        "success": True,
        "users": users_list,
        "count": len(users_list)
    }


@mcp.tool()
def vibrate(
    intensity: int,
    duration: int = 0,
    loop_running: int = 0,
    loop_pause: int = 0,
    toy: str = "",
    user_id: str = DEFAULT_UID
) -> dict:
    """
    Set vibration intensity on Lovense toys.

    Args:
        intensity: Vibration level 0-20 (0=off, 20=max)
        duration: Total running time in seconds (0=continuous until stopped)
        loop_running: Running time per cycle in seconds (0=no loop)
        loop_pause: Pause time per cycle in seconds (0=no pause)
        toy: Specific toy ID or empty for all toys
        user_id: User ID to send command to (default: "angela")

    Returns:
        dict: Success status and result

    Examples:
        vibrate(10, 5) - Medium intensity for 5 seconds
        vibrate(15, 0) - Strong continuous vibration
        vibrate(16, 20, 9, 4) - Intensity 16, run 9s/pause 4s, loop for 20s total
    """
    if not 0 <= intensity <= 20:
        return {"success": False, "error": "Intensity must be 0-20"}

    action = f"Vibrate:{intensity}"

    kwargs = {}
    if loop_running > 0:
        kwargs["loopRunningSec"] = loop_running
    if loop_pause > 0:
        kwargs["loopPauseSec"] = loop_pause

    return send_command_to_user(user_id, "Function", action, duration, toy, **kwargs)


@mcp.tool()
def stop(toy: str = "", user_id: str = DEFAULT_UID) -> dict:
    """
    Stop all toy functions immediately.

    Args:
        toy: Specific toy ID or empty for all toys
        user_id: User ID to send command to (default: "angela")

    Returns:
        dict: Success status
    """
    return send_command_to_user(user_id, "Function", "Stop", 0, toy)


@mcp.tool()
def pattern(
    strength_sequence: str,
    interval_ms: int = 1000,
    duration: int = 0,
    features: str = "v",
    toy: str = "",
    user_id: str = DEFAULT_UID
) -> dict:
    """
    Execute custom vibration pattern with precise timing control.

    Args:
        strength_sequence: Semicolon-separated intensity values "20;15;10;5;0"
        interval_ms: Milliseconds between each change (min 100ms)
        duration: Total running time in seconds (0=continuous)
        features: Pattern features - "v"=vibrate, "r"=rotate, "p"=pump, "vrp"=all
        toy: Specific toy ID or empty for all toys
        user_id: User ID to send command to (default: "angela")

    Returns:
        dict: Success status and result

    Examples:
        pattern("20;10;5;0", 500, 10) - Descending pattern, 0.5s intervals
        pattern("5;10;15;20;15;10;5", 200, 15) - Wave pattern
        pattern("20;0;20;0", 100, 5) - Rapid pulse
    """
    if interval_ms < 100:
        return {"success": False, "error": "Interval must be >= 100ms"}

    # Validate strength sequence
    strengths = strength_sequence.split(';')
    if len(strengths) > 50:
        return {"success": False, "error": "Max 50 strength values allowed"}

    for s in strengths:
        try:
            val = int(s)
            if not 0 <= val <= 20:
                return {"success": False, "error": "Strength values must be 0-20"}
        except ValueError:
            return {"success": False, "error": f"Invalid strength value: {s}"}

    rule = f"V:1;F:{features};S:{interval_ms}#"

    return send_command_to_user(
        user_id, "Pattern", "", duration, toy,
        rule=rule, strength=strength_sequence
    )


@mcp.tool()
def preset(name: str, duration: int = 0, toy: str = "", user_id: str = DEFAULT_UID) -> dict:
    """
    Execute built-in Lovense preset patterns.

    Args:
        name: Preset name - "pulse", "wave", "fireworks", or "earthquake"
        duration: Total running time in seconds (0=continuous)
        toy: Specific toy ID or empty for all toys
        user_id: User ID to send command to (default: "angela")

    Returns:
        dict: Success status and result
    """
    valid_presets = ["pulse", "wave", "fireworks", "earthquake"]

    if name.lower() not in valid_presets:
        return {
            "success": False,
            "error": f"Invalid preset. Choose from: {', '.join(valid_presets)}"
        }

    return send_command_to_user(user_id, "Preset", name.lower(), duration, toy)


@mcp.tool()
def get_toys(user_id: str = DEFAULT_UID) -> dict:
    """
    Get list of toys for a connected user.

    Args:
        user_id: User ID to query (default: "angela")

    Returns:
        dict: List of toys with status information
    """
    with users_lock:
        user = connected_users.get(user_id)

    if not user:
        return {
            "success": False,
            "error": f"User {user_id} not connected. Generate QR code first."
        }

    toys = user.get("toys", {})

    # Parse toys if it's a string
    if isinstance(toys, str):
        try:
            toys = json.loads(toys)
        except:
            toys = {}

    toys_list = []
    for toy_id, toy_info in toys.items():
        if isinstance(toy_info, dict):
            toys_list.append({
                "id": toy_id,
                "name": toy_info.get("name", "unknown"),
                "nickname": toy_info.get("nickName", ""),
                "status": "connected" if toy_info.get("status") == 1 else "disconnected",
                "battery": toy_info.get("battery", 0)
            })

    return {
        "success": True,
        "user_id": user_id,
        "toys": toys_list,
        "count": len(toys_list)
    }


# ========================
# COMBINED SERVER
# ========================

def create_combined_app():
    """Create a combined Starlette app with MCP SSE + callback endpoint."""

    # Get the MCP SSE app
    mcp_app = mcp.sse_app()

    # Create routes for callback
    routes = [
        Route("/lovense/callback", lovense_callback, methods=["POST"]),
        Mount("/", app=mcp_app),  # Mount MCP at root
    ]

    app = Starlette(routes=routes)
    return app


# ========================
# STARTUP
# ========================

if __name__ == "__main__":
    # Check configuration
    if not DEVELOPER_TOKEN:
        print("⚠️  Warning: LOVENSE_DEVELOPER_TOKEN not set")
        print("   Set it in environment or .env file to enable remote control")

    if not CALLBACK_URL:
        print("⚠️  Warning: LOVENSE_CALLBACK_URL not set")
        print("   Set it to your public URL for the callback endpoint")

    print(f"🎮 Enhanced Lovense MCP Server starting...")
    print(f"📡 Callback URL: {CALLBACK_URL or 'Not configured'}")
    print(f"🔑 Developer Token: {'Configured' if DEVELOPER_TOKEN else 'Not configured'}")

    # Create combined app
    app = create_combined_app()

    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
