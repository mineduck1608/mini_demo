"""
Script to explore /sdcard/customize/action/ directory and list .ubx files
on Alpha Mini robot via USB/WiFi connection
"""
import asyncio
import logging
from websocket_patch import apply_websocket_patch
apply_websocket_patch()

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import GetActionList, RobotActionType
from mini.apis.api_action import PlayAction

async def list_custom_actions_detailed():
    """List custom actions with detailed information"""
    try:
        print("=== Detailed Custom Actions Analysis ===")
        custom_actions = GetActionList(action_type=RobotActionType.CUSTOM)
        (result_type, response) = await custom_actions.execute()

        if response and response.isSuccess and response.actionList:
            print(f"Found {len(response.actionList)} custom .ubx files in /sdcard/customize/action/:")
            print("-" * 60)

            for i, action in enumerate(response.actionList, 1):
                print(f"{i:2d}. File: {action.id}.ubx")
                print(f"    Chinese Name: {action.cnName}")
                print(f"    English Name: {action.enName}")
                print(f"    Type: {action.type}")
                print(f"    Full Path: /sdcard/customize/action/{action.id}.ubx")
                print()

        else:
            print("No custom actions found or failed to retrieve list")
            print("This means /sdcard/customize/action/ is empty or inaccessible")

    except Exception as e:
        print(f"Error getting custom actions: {e}")

async def test_play_custom_action():
    """Test playing a custom action to verify file accessibility"""
    try:
        print("=== Testing Custom Action Playback ===")

        # Get custom actions first
        custom_actions = GetActionList(action_type=RobotActionType.CUSTOM)
        (result_type, response) = await custom_actions.execute()

        if response and response.isSuccess and response.actionList:
            # Try to play the first custom action
            first_action = response.actionList[0]
            print(f"Testing playback of: {first_action.id} ({first_action.cnName})")

            play_action = PlayAction(action_name=first_action.id)
            (play_result, play_response) = await play_action.execute()

            if play_response and play_response.isSuccess:
                print(f"✓ Successfully played {first_action.id} - file is accessible!")
            else:
                print(f"✗ Failed to play {first_action.id} - file may be corrupted")

        else:
            print("No custom actions available to test")

    except Exception as e:
        print(f"Error testing custom action: {e}")

async def analyze_action_storage():
    """Analyze action storage system"""
    print("=== Alpha Mini Action Storage Analysis ===")
    print()

    # Get built-in actions count
    inner_actions = GetActionList(action_type=RobotActionType.INNER)
    (result_type, inner_response) = await inner_actions.execute()
    inner_count = len(inner_response.actionList) if inner_response and inner_response.isSuccess else 0

    # Get custom actions count
    custom_actions = GetActionList(action_type=RobotActionType.CUSTOM)
    (result_type, custom_response) = await custom_actions.execute()
    custom_count = len(custom_response.actionList) if custom_response and custom_response.isSuccess else 0

    print(f"📊 Storage Summary:")
    print(f"   Built-in Actions: {inner_count} files (system storage)")
    print(f"   Custom Actions:   {custom_count} files (/sdcard/customize/action/)")
    print()

    print(f"📁 File Locations:")
    print(f"   Built-in: /system/res/actions/ or /data/actions/ (read-only)")
    print(f"   Custom:   /sdcard/customize/action/ (read/write via USB/ADB)")
    print()

    if custom_count > 0:
        print(f"✓ USB Access Available: You can browse /sdcard/customize/action/ via:")
        print(f"  • File Explorer (if robot mounted as USB drive)")
        print(f"  • ADB commands: adb shell ls /sdcard/customize/action/")
        print(f"  • Alpha Mini app file manager")
    else:
        print(f"ℹ No custom actions found - directory may be empty")

async def main():
    # Set up Mini SDK
    MiniSdk.set_log_level(logging.INFO)
    MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

    # Find and connect to robot
    print("Connecting to Alpha Mini robot...")
    device = await MiniSdk.get_device_by_name("000341", 10)

    if device:
        connected = await MiniSdk.connect(device)
        if connected:
            print("✓ Connected successfully!")
            await MiniSdk.enter_program()
            print()

            # Analyze storage
            await analyze_action_storage()

            # List custom actions in detail
            await list_custom_actions_detailed()

            # Test custom action playback
            await test_play_custom_action()

            # Cleanup
            await MiniSdk.quit_program()
            await MiniSdk.release()
            print("\n=== Connection closed ===")

        else:
            print("✗ Failed to connect to robot")
    else:
        print("✗ Robot not found")

if __name__ == '__main__':
    asyncio.run(main())
