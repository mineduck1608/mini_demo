"""
Enhanced test script to find .ubx files and explore Alpha Mini action system
"""
import asyncio
import logging
from websocket_patch import apply_websocket_patch
apply_websocket_patch()

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import GetActionList, RobotActionType

async def get_robot_actions():
    """Get list of available actions on the robot"""
    try:
        print("=== Getting INNER (built-in) actions ===")
        inner_actions = GetActionList(action_type=RobotActionType.INNER)
        (result_type, response) = await inner_actions.execute()

        if response and response.isSuccess:
            print(f"Found {len(response.actionList)} built-in actions:")
            for action in response.actionList[:10]:  # Show first 10
                print(f"  - {action}")
            if len(response.actionList) > 10:
                print(f"  ... and {len(response.actionList) - 10} more")
        else:
            print("Failed to get built-in actions")

        print("\n=== Getting CUSTOM actions ===")
        custom_actions = GetActionList(action_type=RobotActionType.CUSTOM)
        (result_type, response) = await custom_actions.execute()

        if response and response.isSuccess:
            print(f"Found {len(response.actionList)} custom actions:")
            for action in response.actionList:
                print(f"  - {action}")
        else:
            print("Failed to get custom actions or no custom actions found")

    except Exception as e:
        print(f"Error getting action lists: {e}")

async def explore_robot_storage():
    """Explore robot storage paths to find .ubx files location"""
    try:
        print("\n=== Alpha Mini .ubx file locations ===")

        print("Based on SDK analysis, .ubx files are likely stored at:")
        print("1. CUSTOM ACTIONS: /sdcard/customize/action/ (confirmed from SDK)")
        print("2. BUILT-IN ACTIONS: /system/ or /data/ (internal storage)")
        print("3. USER BEHAVIORS: /sdcard/ubiquitous/ (common path)")

        # Get actual action lists to verify
        await get_robot_actions()

    except Exception as e:
        print(f"Error exploring storage: {e}")

async def main():
    # Set up Mini SDK
    MiniSdk.set_log_level(logging.INFO)
    MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

    # Find and connect to robot
    device = await MiniSdk.get_device_by_name("000341", 10)
    if device:
        connected = await MiniSdk.connect(device)
        if connected:
            print("Connected to robot successfully!")
            await MiniSdk.enter_program()

            # Explore storage
            await explore_robot_storage()

            # Cleanup
            await MiniSdk.quit_program()
            await MiniSdk.release()
        else:
            print("Failed to connect to robot")
    else:
        print("Robot not found")

if __name__ == '__main__':
    asyncio.run(main())
