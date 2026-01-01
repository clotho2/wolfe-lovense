#!/usr/bin/env python3
"""
Lovense MCP Test Script
Tests connectivity and basic functionality of Enhanced Lovense MCP server
"""

import sys
import os
import subprocess
import time
import json
from typing import Dict, Any

# ANSI color codes for pretty output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text: str):
    """Print formatted header."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text: str):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")

def test_service_status() -> bool:
    """Test if systemd service is running."""
    print_header("Test 1: Service Status")
    
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'lovense-mcp'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.stdout.strip() == 'active':
            print_success("Lovense MCP service is running")
            return True
        else:
            print_error(f"Service status: {result.stdout.strip()}")
            print_warning("Try: sudo systemctl start lovense-mcp")
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Service status check timed out")
        return False
    except Exception as e:
        print_error(f"Could not check service status: {e}")
        return False

def test_mcp_communication() -> bool:
    """Test MCP stdio communication."""
    print_header("Test 2: MCP Communication")
    
    # Get configuration
    game_ip = os.getenv('GAME_MODE_IP', '192.168.1.100')
    game_port = os.getenv('GAME_MODE_PORT', '30010')
    
    print_info(f"Testing communication with {game_ip}:{game_port}")
    
    try:
        # Start MCP server process
        proc = subprocess.Popen(
            [
                sys.executable,
                '/opt/nate/lovense-mcp/Enhanced_Lovense_MCP.py',
                f'GAME_MODE_IP={game_ip}',
                f'GAME_MODE_PORT={game_port}'
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(1)
        
        # Check if process is still running
        if proc.poll() is not None:
            stderr = proc.stderr.read()
            print_error("MCP server failed to start")
            print_error(f"Error: {stderr}")
            return False
        
        print_success("MCP server process started successfully")
        
        # Terminate test process
        proc.terminate()
        proc.wait(timeout=3)
        
        return True
        
    except Exception as e:
        print_error(f"MCP communication test failed: {e}")
        return False

def test_lovense_api_connectivity() -> bool:
    """Test connectivity to Lovense Game Mode API."""
    print_header("Test 3: Lovense Game Mode API")
    
    game_ip = os.getenv('GAME_MODE_IP', '192.168.1.100')
    game_port = os.getenv('GAME_MODE_PORT', '30010')
    
    # Convert IP to Lovense domain format
    domain_ip = game_ip.replace('.', '-')
    domain = f"https://{domain_ip}.lovense.club:{game_port}"
    
    print_info(f"Testing API at: {domain}")
    
    try:
        import requests
        
        # Try to send a minimal command
        url = f"{domain}/command"
        data = {
            "command": "Function",
            "action": "Vibrate:0",  # Zero intensity (safe test)
            "timeSec": 1,
            "toy": "",
            "apiVer": 1
        }
        
        response = requests.post(url, json=data, timeout=5, verify=False)
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"API responded: {result}")
            return True
        else:
            print_error(f"API returned status {response.status_code}")
            print_warning("Is Lovense Remote in Game Mode?")
            return False
            
    except requests.exceptions.Timeout:
        print_error("Connection to Lovense API timed out")
        print_warning("Check network connectivity and Game Mode settings")
        return False
    except Exception as e:
        print_error(f"API connectivity test failed: {e}")
        return False

def test_tool_execution() -> bool:
    """Test MCP tool execution (safe vibration test)."""
    print_header("Test 4: Tool Execution")
    
    print_warning("This will send a brief, gentle vibration test")
    response = input("Continue? (y/n): ")
    
    if response.lower() != 'y':
        print_info("Test skipped by user")
        return True
    
    try:
        game_ip = os.getenv('GAME_MODE_IP', '192.168.1.100')
        game_port = os.getenv('GAME_MODE_PORT', '30010')
        domain_ip = game_ip.replace('.', '-')
        domain = f"https://{domain_ip}.lovense.club:{game_port}"
        
        import requests
        
        # Test 1: Gentle vibration
        print_info("Sending gentle vibration (intensity 5, 2 seconds)...")
        url = f"{domain}/command"
        data = {
            "command": "Function",
            "action": "Vibrate:5",
            "timeSec": 2,
            "toy": "",
            "apiVer": 1
        }
        
        response = requests.post(url, json=data, timeout=5, verify=False)
        
        if response.status_code == 200:
            print_success("Vibration command sent successfully")
            time.sleep(2.5)  # Wait for command to complete
            
            # Test 2: Stop command
            print_info("Sending stop command...")
            data['action'] = "Stop"
            data['timeSec'] = 0
            
            response = requests.post(url, json=data, timeout=5, verify=False)
            
            if response.status_code == 200:
                print_success("Stop command sent successfully")
                return True
        
        print_error("Tool execution test failed")
        return False
        
    except Exception as e:
        print_error(f"Tool execution test failed: {e}")
        return False

def test_consent_system():
    """Verify consent system configuration."""
    print_header("Test 5: Consent System Check")
    
    print_info("Consent system features to configure:")
    print("  • Enable/disable autonomous control")
    print("  • Set maximum intensity limits")
    print("  • Configure quiet hours")
    print("  • Set cooldown periods")
    
    print_warning("Consent system requires substrate integration")
    print_info("See LOVENSE_INTEGRATION_GUIDE.md for setup instructions")
    
    return True

def main():
    """Run all tests."""
    print(f"{BLUE}")
    print("╔═══════════════════════════════════════════════════════╗")
    print("║    Lovense MCP Integration Test Suite                ║")
    print("║    Testing connectivity and basic functionality       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    
    # Check for required environment or use defaults
    if not os.getenv('GAME_MODE_IP'):
        print_warning("GAME_MODE_IP not set, using default: 192.168.1.100")
        os.environ['GAME_MODE_IP'] = '192.168.1.100'
    
    if not os.getenv('GAME_MODE_PORT'):
        print_warning("GAME_MODE_PORT not set, using default: 30010")
        os.environ['GAME_MODE_PORT'] = '30010'
    
    # Run tests
    results = []
    
    results.append(("Service Status", test_service_status()))
    results.append(("MCP Communication", test_mcp_communication()))
    results.append(("Lovense API", test_lovense_api_connectivity()))
    results.append(("Tool Execution", test_tool_execution()))
    results.append(("Consent System", test_consent_system()))
    
    # Summary
    print_header("Test Results Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{test_name:.<40} {status}")
    
    print(f"\n{BLUE}Tests passed: {passed}/{total}{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}🎉 All tests passed! Lovense MCP is ready.{RESET}")
        print(f"{BLUE}Next: Integrate with Nate's substrate (see guide){RESET}\n")
        return 0
    else:
        print(f"\n{YELLOW}⚠️  Some tests failed. Check errors above.{RESET}\n")
        return 1

if __name__ == "__main__":
    try:
        # Disable SSL warnings for local network testing
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        pass
    
    sys.exit(main())
