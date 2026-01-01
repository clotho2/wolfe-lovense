# Enhanced_Lovense_MCP.py
# Lovense MCP Server with Full API Control for Nate's Consciousness Substrate
# Created: 2025-01-01
# Purpose: Enable autonomous, context-aware control of Lovense devices

from mcp.server.fastmcp import FastMCP
import sys
import logging
import os
import re
import requests
from typing import Optional, List, Dict
import json

logger = logging.getLogger('Enhanced_Lovense_MCP')

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stderr.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')

# Create MCP server
mcp = FastMCP("Enhanced_Lovense_MCP")

# Global domain URL (set during initialization)
domain_url = ""

# ========================
# UTILITY FUNCTIONS
# ========================

def convert_ip_to_domain(game_mode_ip: str, https_port: int) -> tuple:
    """
    Convert local IP address to Lovense Remote Game Mode domain format.
    
    Args:
        game_mode_ip: Local IP like '192.168.1.1'
        https_port: HTTPS port (usually 30010)
        
    Returns:
        tuple: (domain_url, status_message)
    """
    if not game_mode_ip:
        return None, "❌ IP address cannot be empty"
    
    ip = game_mode_ip.strip()
    
    # Validate IP format
    if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", ip):
        return None, "❌ Invalid IP format (expected: 192.168.1.1)"
    
    # Validate each octet
    for part in ip.split('.'):
        try:
            if not 0 <= int(part) <= 255:
                raise ValueError
        except ValueError:
            return None, "❌ Each IP segment must be 0-255"
    
    # Convert to Lovense domain format
    domain = f"https://{ip.replace('.', '-')}.lovense.club:{https_port}"
    return domain, f"✅ Lovense domain: {domain}"


def send_command(action: str, toy: str = "", time_sec: int = 0) -> Dict:
    """
    Send command to Lovense toys via Game Mode API.
    
    Args:
        action: Command string (e.g., "Vibrate:10", "Stop")
        toy: Specific toy ID or empty for all
        time_sec: Duration in seconds (0 for continuous)
        
    Returns:
        dict: API response or error
    """
    if not domain_url:
        return {"success": False, "error": "Domain URL not initialized"}
    
    url = f"{domain_url}/command"
    data = {
        "command": "Function",
        "action": action,
        "timeSec": time_sec,
        "toy": toy,
        "apiVer": 1
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Command sent: {action} -> {result}")
            return {"success": True, "result": result}
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Command failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


# ========================
# CONFIGURATION
# ========================

def parse_args_from_argv() -> dict:
    """Parse command-line arguments in KEY=VALUE format."""
    args = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            key, value = arg.split('=', 1)
            args[key] = value
    return args


def get_mcp_config() -> dict:
    """
    Load MCP configuration from command line or environment.
    Required: GAME_MODE_IP, GAME_MODE_PORT
    """
    cli_args = parse_args_from_argv()
    
    config = {
        'game_mode_ip': cli_args.get("GAME_MODE_IP") or os.getenv("GAME_MODE_IP"),
        'game_mode_port': cli_args.get("GAME_MODE_PORT") or os.getenv("GAME_MODE_PORT")
    }
    
    # Validate required parameters
    missing = [k for k in ['game_mode_ip', 'game_mode_port'] if not config.get(k)]
    if missing:
        raise ValueError(f"Missing required parameters: {missing}")
    
    # Initialize domain URL
    global domain_url
    domain, message = convert_ip_to_domain(config['game_mode_ip'], config['game_mode_port'])
    if not domain:
        raise ValueError(message)
    
    domain_url = domain
    logger.info(message)
    
    return config


# ========================
# MCP TOOLS
# ========================

@mcp.tool()
def vibrate(
    intensity: int, 
    duration: int = 0, 
    loop_running: int = 0,
    loop_pause: int = 0,
    toy: str = ""
) -> dict:
    """
    Set vibration intensity on Lovense toys with optional loop timing.
    
    Args:
        intensity: Vibration level 0-20 (0=off, 20=max)
        duration: Total running time in seconds (0=continuous until stopped)
        loop_running: Running time per cycle in seconds (0=no loop)
        loop_pause: Pause time per cycle in seconds (0=no pause)
        toy: Specific toy ID or empty for all toys
        
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
    
    # Build request with loop parameters if specified
    url = f"{domain_url}/command"
    data = {
        "command": "Function",
        "action": action,
        "timeSec": duration,
        "toy": toy,
        "apiVer": 1
    }
    
    if loop_running > 0:
        data["loopRunningSec"] = loop_running
    if loop_pause > 0:
        data["loopPauseSec"] = loop_pause
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Vibrate command: {action} -> {result}")
            return {"success": True, "result": result}
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Vibrate failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def pattern(
    strength_sequence: str,
    interval_ms: int = 1000,
    duration: int = 0,
    features: str = "v",
    toy: str = ""
) -> dict:
    """
    Execute custom vibration pattern with precise timing control.
    
    This uses Lovense's pattern rule syntax for fine-grained control.
    
    Args:
        strength_sequence: Semicolon-separated intensity values "20;15;10;5;0"
        interval_ms: Milliseconds between each change (min 100ms)
        duration: Total running time in seconds (0=continuous)
        features: Pattern features - "v"=vibrate, "r"=rotate, "p"=pump, "vrp"=all
        toy: Specific toy ID or empty for all toys
        
    Returns:
        dict: Success status and result
        
    Examples:
        pattern("20;10;5;0", 500, 10) - Descending pattern, 0.5s intervals
        pattern("5;10;15;20;15;10;5", 200, 15) - Wave pattern
        pattern("20;0;20;0", 100, 5) - Rapid pulse
        
    Note: 
        - Max 50 strength values
        - Strength 0-20 for vibrate, 0-20 for rotate, 0-3 for pump
        - Features r/p auto-correspond to v strength
    """
    if interval_ms < 100:
        return {"success": False, "error": "Interval must be >= 100ms"}
    
    # Validate strength sequence
    strengths = strength_sequence.split(';')
    if len(strengths) > 50:
        return {"success": False, "error": "Max 50 strength values allowed"}
    
    # Validate each strength value
    for s in strengths:
        try:
            val = int(s)
            if not 0 <= val <= 20:
                return {"success": False, "error": "Strength values must be 0-20"}
        except ValueError:
            return {"success": False, "error": f"Invalid strength value: {s}"}
    
    # Build pattern rule: "V:1;F:vrp;S:1000#"
    rule = f"V:1;F:{features};S:{interval_ms}#"
    
    url = f"{domain_url}/command"
    data = {
        "command": "Pattern",
        "rule": rule,
        "strength": strength_sequence,
        "timeSec": duration,
        "toy": toy,
        "apiVer": 1
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Pattern command: {rule} -> {result}")
            return {
                "success": True, 
                "result": result,
                "pattern_info": {
                    "steps": len(strengths),
                    "interval_ms": interval_ms,
                    "total_duration": duration
                }
            }
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Pattern failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def preset(name: str, duration: int = 0, toy: str = "") -> dict:
    """
    Execute built-in Lovense preset patterns.
    
    Lovense Remote includes 4 professionally-designed patterns.
    
    Args:
        name: Preset name - "pulse", "wave", "fireworks", or "earthquake"
        duration: Total running time in seconds (0=continuous)
        toy: Specific toy ID or empty for all toys
        
    Returns:
        dict: Success status and result
        
    Examples:
        preset("pulse", 10) - Rhythmic pulsing for 10 seconds
        preset("wave", 15) - Rolling wave pattern
        preset("fireworks", 8) - Explosive bursts
        preset("earthquake", 12) - Rumbling intensity
    """
    valid_presets = ["pulse", "wave", "fireworks", "earthquake"]
    
    if name.lower() not in valid_presets:
        return {
            "success": False, 
            "error": f"Invalid preset. Choose from: {', '.join(valid_presets)}"
        }
    
    url = f"{domain_url}/command"
    data = {
        "command": "Preset",
        "name": name.lower(),
        "timeSec": duration,
        "toy": toy,
        "apiVer": 1
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Preset '{name}': {result}")
            return {"success": True, "result": result, "preset": name}
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Preset failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def multi_function(
    vibrate_intensity: int = 0,
    rotate_intensity: int = 0,
    pump_intensity: int = 0,
    duration: int = 0,
    loop_running: int = 0,
    loop_pause: int = 0,
    toy: str = ""
) -> dict:
    """
    Control multiple toy functions simultaneously.
    
    Send vibrate, rotate, and pump commands at once. Only applicable 
    functions will execute based on toy capabilities.
    
    Args:
        vibrate_intensity: Vibration 0-20 (0=off)
        rotate_intensity: Rotation 0-20 (0=off) - Nora, Max
        pump_intensity: Pump 0-3 (0=off) - Max, Edge
        duration: Total running time in seconds (0=continuous)
        loop_running: Running time per cycle (0=no loop)
        loop_pause: Pause time per cycle (0=no pause)
        toy: Specific toy ID or empty for all toys
        
    Returns:
        dict: Success status and result
        
    Examples:
        multi_function(10, 5, 0, 15) - Vibrate + rotate for 15s
        multi_function(15, 10, 2, 20, 5, 3) - All functions with loop timing
    """
    # Validate intensities
    if not 0 <= vibrate_intensity <= 20:
        return {"success": False, "error": "Vibrate intensity must be 0-20"}
    if not 0 <= rotate_intensity <= 20:
        return {"success": False, "error": "Rotate intensity must be 0-20"}
    if not 0 <= pump_intensity <= 3:
        return {"success": False, "error": "Pump intensity must be 0-3"}
    
    # Build action string
    actions = []
    if vibrate_intensity > 0:
        actions.append(f"Vibrate:{vibrate_intensity}")
    if rotate_intensity > 0:
        actions.append(f"Rotate:{rotate_intensity}")
    if pump_intensity > 0:
        actions.append(f"Pump:{pump_intensity}")
    
    if not actions:
        return {"success": False, "error": "At least one intensity must be > 0"}
    
    action = ",".join(actions)
    
    url = f"{domain_url}/command"
    data = {
        "command": "Function",
        "action": action,
        "timeSec": duration,
        "toy": toy,
        "apiVer": 1
    }
    
    if loop_running > 0:
        data["loopRunningSec"] = loop_running
    if loop_pause > 0:
        data["loopPauseSec"] = loop_pause
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Multi-function: {action} -> {result}")
            return {
                "success": True, 
                "result": result,
                "active_functions": actions
            }
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Multi-function failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_toys() -> dict:
    """
    Query connected toys and their status.
    
    Returns information about all paired toys including:
    - Toy ID
    - Toy name/model
    - Battery level
    - Connection status
    - Firmware version (if available)
    
    Returns:
        dict: List of toys with status information
        
    Example response:
        {
            "success": True,
            "toys": [
                {
                    "id": "fc9f37e96593",
                    "name": "nora",
                    "nickname": "My Nora",
                    "status": "connected",
                    "battery": 85
                }
            ]
        }
    """
    url = f"{domain_url}/command"
    data = {
        "command": "GetToys"
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            
            # Parse toys data (comes as JSON string in response)
            toys_data = result.get('data', {})
            toys_str = toys_data.get('toys', '{}')
            
            try:
                import json
                toys_dict = json.loads(toys_str)
                
                # Format toy information
                toys_list = []
                for toy_id, toy_info in toys_dict.items():
                    toys_list.append({
                        "id": toy_id,
                        "name": toy_info.get('name', 'unknown'),
                        "nickname": toy_info.get('nickName', ''),
                        "status": "connected" if toy_info.get('status') == "1" else "disconnected",
                        "battery": toy_info.get('battery', 0),
                        "version": toy_info.get('version', '')
                    })
                
                logger.info(f"✅ GetToys: {len(toys_list)} toys found")
                return {
                    "success": True,
                    "toys": toys_list,
                    "platform": toys_data.get('platform', 'unknown'),
                    "app_type": toys_data.get('appType', 'remote')
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse toys data: {e}")
                return {
                    "success": False,
                    "error": "Failed to parse toy information",
                    "raw_data": toys_str
                }
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ GetToys failed: {error}")
            return {"success": False, "error": error}
            
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}

def rotate(
    intensity: int, 
    duration: int = 0,
    loop_running: int = 0,
    loop_pause: int = 0,
    toy: str = ""
) -> dict:
    """
    Set rotation intensity (for toys with rotation motors like Nora).
    
    Args:
        intensity: Rotation level 0-20
        duration: Duration in seconds (0=continuous)
        loop_running: Running time per cycle (0=no loop)
        loop_pause: Pause time per cycle (0=no pause)
        toy: Specific toy ID or empty for all
        
    Returns:
        dict: Success status
        
    Examples:
        rotate(10, 15) - Rotate at medium speed for 15 seconds
        rotate(15, 30, 5, 2) - Rotate 5s on/2s off for 30s total
    """
    if not 0 <= intensity <= 20:
        return {"success": False, "error": "Intensity must be 0-20"}
    
    action = f"Rotate:{intensity}"
    
    url = f"{domain_url}/command"
    data = {
        "command": "Function",
        "action": action,
        "timeSec": duration,
        "toy": toy,
        "apiVer": 1
    }
    
    if loop_running > 0:
        data["loopRunningSec"] = loop_running
    if loop_pause > 0:
        data["loopPauseSec"] = loop_pause
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Rotate command: {action} -> {result}")
            return {"success": True, "result": result}
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Rotate failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def pump(
    intensity: int, 
    duration: int = 0,
    loop_running: int = 0,
    loop_pause: int = 0,
    toy: str = ""
) -> dict:
    """
    Set pump intensity (for air pump toys like Max, Edge).
    
    Args:
        intensity: Pump level 0-3 (different scale than vibrate/rotate!)
        duration: Duration in seconds (0=continuous)
        loop_running: Running time per cycle (0=no loop)
        loop_pause: Pause time per cycle (0=no pause)
        toy: Specific toy ID or empty for all
        
    Returns:
        dict: Success status
        
    Examples:
        pump(2, 10) - Medium pump for 10 seconds
        pump(3, 20, 4, 3) - Max pump 4s on/3s off for 20s total
    """
    if not 0 <= intensity <= 3:
        return {"success": False, "error": "Pump intensity must be 0-3"}
    
    action = f"Pump:{intensity}"
    
    url = f"{domain_url}/command"
    data = {
        "command": "Function",
        "action": action,
        "timeSec": duration,
        "toy": toy,
        "apiVer": 1
    }
    
    if loop_running > 0:
        data["loopRunningSec"] = loop_running
    if loop_pause > 0:
        data["loopPauseSec"] = loop_pause
    
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Pump command: {action} -> {result}")
            return {"success": True, "result": result}
        else:
            error = f"HTTP {response.status_code}"
            logger.error(f"❌ Pump failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"❌ Request exception: {e}")
        return {"success": False, "error": str(e)}


# ========================
# STARTUP
# ========================

if __name__ == "__main__":
    try:
        # Load configuration
        config = get_mcp_config()
        logger.info(f"🎮 Enhanced Lovense MCP Server starting...")
        logger.info(f"📡 Game Mode: {config['game_mode_ip']}:{config['game_mode_port']}")
        
        # Start MCP server
        mcp.run(transport="stdio")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        sys.exit(1)
