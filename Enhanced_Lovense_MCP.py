# Enhanced_Lovense_MCP.py
# Lovense MCP Server with Basic API for Remote Control
# Updated: 2026-01-21
# Purpose: Enable autonomous, context-aware control of Lovense devices over the internet

from mcp.server.fastmcp import FastMCP
import sys
import logging
import os
import requests
import threading
import time
from typing import Optional, Dict
import json
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
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

# Connected devices storage
connected_devices: Dict[str, dict] = {}
devices_lock = threading.Lock()

# Current QR code info
current_qr_code: Dict[str, str] = {}
qr_lock = threading.Lock()

# Auth token for API calls
auth_token: str = ""
auth_lock = threading.Lock()

# Default user ID
DEFAULT_UID = "angela"

# Socket.IO connection state
socket_connected = False
socket_url = ""
socket_path = ""

# ========================
# LOVENSE BASIC API
# ========================

LOVENSE_API_BASE = "https://api.lovense-api.com/api/basicApi"


def get_auth_token(uid: str = DEFAULT_UID) -> dict:
    """
    Step 1: Get authentication token from Lovense API.
    """
    global auth_token

    if not DEVELOPER_TOKEN:
        return {"success": False, "error": "Developer token not configured"}

    url = f"{LOVENSE_API_BASE}/getToken"
    data = {
        "token": DEVELOPER_TOKEN,
        "uid": uid,
        "uname": uid
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        logger.info(f"getToken response: {result}")

        if result.get("code") == 0:
            with auth_lock:
                auth_token = result.get("data", {}).get("authToken", "")
            logger.info(f"✅ Got auth token for user {uid}")
            return {
                "success": True,
                "authToken": auth_token
            }
        else:
            error = result.get("message", "Unknown error")
            logger.error(f"❌ Auth token request failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"❌ Auth token request exception: {e}")
        return {"success": False, "error": str(e)}


def get_socket_url(platform: str = "Nate Substrate") -> dict:
    """
    Step 2: Get Socket.IO connection URL.
    """
    global socket_url, socket_path

    with auth_lock:
        current_auth = auth_token

    if not current_auth:
        # Try to get auth token first
        result = get_auth_token()
        if not result.get("success"):
            return result
        current_auth = auth_token

    url = f"{LOVENSE_API_BASE}/getSocketUrl"
    data = {
        "platform": platform,
        "authToken": current_auth
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        logger.info(f"getSocketUrl response: {result}")

        if result.get("code") == 0:
            socket_url = result.get("data", {}).get("socketIoUrl", "")
            socket_path = result.get("data", {}).get("socketIoPath", "")
            logger.info(f"✅ Got socket URL: {socket_url}")
            return {
                "success": True,
                "socketIoUrl": socket_url,
                "socketIoPath": socket_path
            }
        else:
            error = result.get("message", "Unknown error")
            logger.error(f"❌ Socket URL request failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"❌ Socket URL request exception: {e}")
        return {"success": False, "error": str(e)}


def get_qr_code_from_api(uid: str = DEFAULT_UID) -> dict:
    """
    Get QR code using the HTTP API endpoint.
    This is an alternative to the Socket.IO method.
    """
    if not DEVELOPER_TOKEN:
        return {"success": False, "error": "Developer token not configured"}

    # First get auth token
    auth_result = get_auth_token(uid)
    if not auth_result.get("success"):
        return auth_result

    # Try the direct QR code endpoint
    url = "https://api.lovense-api.com/api/lan/getQrCode"
    data = {
        "token": DEVELOPER_TOKEN,
        "uid": uid,
        "uname": uid,
        "v": 2
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        logger.info(f"getQrCode response: {result}")

        if result.get("result") == True or result.get("code") == 0:
            qr_url = result.get("message", "")

            with qr_lock:
                current_qr_code["url"] = qr_url
                current_qr_code["uid"] = uid
                current_qr_code["timestamp"] = time.time()

            logger.info(f"✅ Got QR code URL for user {uid}")
            return {
                "success": True,
                "qrcode_url": qr_url,
                "uid": uid,
                "instructions": "Open this URL to see QR code, then scan with Lovense Remote app"
            }
        else:
            error = result.get("message", "Unknown error")
            logger.error(f"❌ QR code request failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"❌ QR code request exception: {e}")
        return {"success": False, "error": str(e)}


def send_command(uid: str, command: str, action: str = "",
                 time_sec: int = 0, toy: str = "", **kwargs) -> dict:
    """
    Send command to connected toys via Lovense Server API.
    """
    if not DEVELOPER_TOKEN:
        return {"success": False, "error": "Developer token not configured"}

    url = "https://api.lovense-api.com/api/lan/v2/command"
    data = {
        "token": DEVELOPER_TOKEN,
        "uid": uid,
        "command": command,
        "action": action,
        "timeSec": time_sec,
        "apiVer": 2
    }

    if toy:
        data["toy"] = toy

    # Add any extra parameters
    data.update(kwargs)

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        logger.info(f"Command response: {result}")

        if result.get("result") == True or result.get("code") == 0:
            logger.info(f"✅ Command sent: {command} {action}")
            return {"success": True, "result": result}
        else:
            error = result.get("message", "Command failed")
            logger.error(f"❌ Command failed: {error}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"❌ Command exception: {e}")
        return {"success": False, "error": str(e)}


# ========================
# CALLBACK HANDLER
# ========================

async def lovense_callback(request: Request) -> JSONResponse:
    """
    Handle callbacks from Lovense Remote app after QR code scan.
    """
    try:
        data = await request.json()
        logger.info(f"📥 Lovense callback received: {json.dumps(data, indent=2)}")

        uid = data.get("uid", DEFAULT_UID)

        with devices_lock:
            connected_devices[uid] = {
                "domain": data.get("domain"),
                "httpsPort": data.get("httpsPort"),
                "httpPort": data.get("httpPort"),
                "wsPort": data.get("wsPort"),
                "wssPort": data.get("wssPort"),
                "platform": data.get("platform"),
                "appVersion": data.get("appVersion"),
                "toys": data.get("toys", {}),
                "connected_at": time.time()
            }

        logger.info(f"✅ User {uid} connected! Toys: {data.get('toys', {})}")

        return JSONResponse({"result": True, "message": "OK"})

    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        return JSONResponse({"result": False, "message": str(e)}, status_code=400)


async def qr_code_page(request: Request) -> HTMLResponse:
    """
    Serve a page that displays the current QR code for scanning.
    """
    with qr_lock:
        qr_url = current_qr_code.get("url", "")
        uid = current_qr_code.get("uid", "")

    if qr_url:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Lovense QR Code</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #1a1a2e;
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 20px;
                }}
                h1 {{
                    color: #ff6b9d;
                }}
                img {{
                    max-width: 300px;
                    border-radius: 10px;
                    margin: 20px 0;
                }}
                .instructions {{
                    max-width: 400px;
                    line-height: 1.6;
                }}
                .uid {{
                    color: #888;
                    font-size: 0.9em;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎮 Lovense Connect</h1>
                <img src="{qr_url}" alt="QR Code">
                <div class="instructions">
                    <p>Scan this QR code with the <strong>Lovense Remote</strong> app on your phone.</p>
                    <p>After scanning, your toys will be connected and ready for control.</p>
                </div>
                <p class="uid">User ID: {uid}</p>
            </div>
        </body>
        </html>
        """
    else:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Lovense QR Code</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #1a1a2e;
                    color: white;
                }
            </style>
        </head>
        <body>
            <h1>No QR Code Generated Yet</h1>
            <p>Ask Nate to generate a QR code first using the get_qr_code tool.</p>
        </body>
        </html>
        """

    return HTMLResponse(html)


# ========================
# MCP TOOLS
# ========================

@mcp.tool()
def get_qr_code(user_id: str = DEFAULT_UID) -> dict:
    """
    Generate a QR code for linking Lovense Remote app.

    The user must scan this QR code with their Lovense Remote app to connect.
    After scanning, their toys will be available for control.

    Args:
        user_id: Unique identifier for this user (default: "angela")

    Returns:
        dict with QR code URL that user should scan, or view at /qr page
    """
    result = get_qr_code_from_api(user_id)

    if result.get("success"):
        result["view_page"] = f"{CALLBACK_URL.replace('/lovense/callback', '')}/qr"
        result["message"] = "QR code generated! User can view it at the /qr page or open the qrcode_url directly"

    return result


@mcp.tool()
def get_connected_users() -> dict:
    """
    Get list of users who have connected via QR code scan.

    Returns:
        dict with list of connected users and their toy info
    """
    with devices_lock:
        users_list = []
        for uid, data in connected_devices.items():
            toys = data.get("toys", {})
            if isinstance(toys, str):
                try:
                    toys = json.loads(toys)
                except:
                    toys = {}

            users_list.append({
                "uid": uid,
                "platform": data.get("platform"),
                "toys": toys,
                "connected": True,
                "connected_at": data.get("connected_at")
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

    return send_command(user_id, "Function", action, duration, toy, **kwargs)


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
    return send_command(user_id, "Function", "Stop", 0, toy)


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

    return send_command(
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

    return send_command(user_id, "Preset", name.lower(), duration, toy)


@mcp.tool()
def get_toys(user_id: str = DEFAULT_UID) -> dict:
    """
    Get list of toys for a connected user.

    Args:
        user_id: User ID to query (default: "angela")

    Returns:
        dict: List of toys with status information
    """
    with devices_lock:
        user = connected_devices.get(user_id)

    if not user:
        return {
            "success": False,
            "error": f"User {user_id} not connected. Generate QR code first.",
            "hint": "Use get_qr_code() to generate a QR code, then have user scan it"
        }

    toys = user.get("toys", {})

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
    """Create a combined Starlette app with MCP SSE + callback + QR page."""

    # Get the MCP SSE app
    mcp_app = mcp.sse_app()

    # Create routes
    routes = [
        Route("/lovense/callback", lovense_callback, methods=["POST"]),
        Route("/qr", qr_code_page, methods=["GET"]),
        Mount("/", app=mcp_app),
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
        print("   Set it in environment or service file to enable remote control")
    else:
        print(f"🔑 Developer Token: {DEVELOPER_TOKEN[:8]}...{DEVELOPER_TOKEN[-4:]}")

    if CALLBACK_URL:
        print(f"📡 Callback URL: {CALLBACK_URL}")
        qr_page_url = CALLBACK_URL.replace("/lovense/callback", "/qr")
        print(f"📱 QR Code Page: {qr_page_url}")
    else:
        print("⚠️  Warning: LOVENSE_CALLBACK_URL not set")

    print(f"🎮 Enhanced Lovense MCP Server starting...")

    # Create combined app
    app = create_combined_app()

    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
