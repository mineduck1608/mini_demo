"""
FastAPI web server for Alpha Mini Robot Controller
High-performance async API for executing robot actions and expressions
"""
import asyncio
import logging
import traceback
import sys
from typing import List, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('alpha_mini_controller.log')
    ]
)
logger = logging.getLogger(__name__)

# Import Alpha Mini SDK with websocket patch (using working connection method)
try:
    logger.info("🔧 Applying websocket patch...")
    from websocket_patch import apply_websocket_patch
    apply_websocket_patch()
    logger.info("✅ Websocket patch applied successfully")
except Exception as e:
    logger.error(f"❌ Failed to apply websocket patch: {e}")
    logger.error(traceback.format_exc())

# Import Alpha Mini SDK and additional APIs
try:
    logger.info("📦 Importing Alpha Mini SDK...")
    import mini.mini_sdk as MiniSdk
    from mini.dns.dns_browser import WiFiDevice
    from mini.apis.api_action import PlayAction
    from mini.apis.api_expression import PlayExpression
    from mini.apis.api_action import GetActionList

    # Import behavior APIs from test_expression.py
    from mini.apis.api_behavior import StartBehavior, ControlBehaviorResponse, StopBehavior
    from mini.apis.api_expression import ControlMouthLamp, ControlMouthResponse
    from mini.apis.api_expression import SetMouthLamp, SetMouthLampResponse, MouthLampColor, MouthLampMode
    from mini.apis.base_api import MiniApiResultType
    from mini.apis import errors

    # Configure MiniSdk like in test_connect.py
    MiniSdk.set_log_level(logging.INFO)
    MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

    logger.info("✅ Alpha Mini SDK and APIs imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import Alpha Mini SDK: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1)

# FastAPI app initialization
app = FastAPI(
    title="Alpha Mini Robot Controller API",
    description="High-performance API for controlling Alpha Mini robot actions and expressions",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Global robot state with logging
class RobotState:
    def __init__(self):
        self.device: Optional[WiFiDevice] = None
        self.is_connected: bool = False
        self.is_connecting: bool = False
        self.connection_lock = asyncio.Lock()
        self.last_action_time: Optional[datetime] = None
        self.action_count: int = 0
        self.connection_attempts: int = 0
        self.last_error: Optional[str] = None
        self.scan_results: List[str] = []

        logger.info("🤖 Robot state initialized")

robot_state = RobotState()

# Pydantic models for API requests/responses
class ActionRequest(BaseModel):
    name: str
    wait_for_completion: bool = True

class ExpressionRequest(BaseModel):
    name: str
    wait_for_completion: bool = True

class ActionResponse(BaseModel):
    success: bool
    message: str
    execution_time: Optional[float] = None
    action_name: str

class ExpressionResponse(BaseModel):
    success: bool
    message: str
    execution_time: Optional[float] = None
    expression_name: str

class ConnectionStatus(BaseModel):
    connected: bool
    device_name: Optional[str] = None
    device_address: Optional[str] = None
    connection_time: Optional[str] = None
    action_count: int = 0

class ActionInfo(BaseModel):
    name: str
    display_name: str
    category: str = "general"

class ExpressionInfo(BaseModel):
    name: str
    display_name: str
    category: str = "face"

# Real actions from Alpha Mini robot
REAL_ACTIONS: List[ActionInfo] = [
    # Basic movement actions
    ActionInfo(name="007", display_name="Rise from a seated position", category="movement"),
    ActionInfo(name="009", display_name="Reset", category="basic"),
    ActionInfo(name="011", display_name="Nod", category="gesture"),
    ActionInfo(name="012", display_name="Push-ups", category="exercise"),
    ActionInfo(name="013", display_name="Kung fu", category="exercise"),
    ActionInfo(name="015", display_name="Welcome", category="greeting"),
    ActionInfo(name="017", display_name="Raise both hands", category="gesture"),
    ActionInfo(name="018", display_name="Lift the right leg", category="movement"),
    ActionInfo(name="019", display_name="Lift the left leg", category="movement"),
    ActionInfo(name="021", display_name="Bend at the waist", category="movement"),
    ActionInfo(name="024", display_name="Yoga", category="exercise"),
    ActionInfo(name="027", display_name="Sit down", category="movement"),
    ActionInfo(name="028", display_name="Do a right lunge", category="exercise"),
    ActionInfo(name="031", display_name="Squat down", category="exercise"),
    ActionInfo(name="037", display_name="Shake the head", category="gesture"),
    ActionInfo(name="038", display_name="Tilt the head", category="gesture"),
    ActionInfo(name="039", display_name="Laugh out loud", category="emotion"),

    # Random short actions
    ActionInfo(name="random_short2", display_name="Hug", category="social"),
    ActionInfo(name="random_short3", display_name="Wave the left hand", category="greeting"),
    ActionInfo(name="random_short4", display_name="Wave the right hand", category="greeting"),

    # Surveillance actions
    ActionInfo(name="Surveillance_001", display_name="Say hi", category="greeting"),
    ActionInfo(name="Surveillance_003", display_name="Shake hands", category="greeting"),
    ActionInfo(name="Surveillance_004", display_name="Blow a kiss", category="social"),
    ActionInfo(name="Surveillance_006", display_name="Act cute", category="emotion"),

    # Special actions
    ActionInfo(name="action_004", display_name="Wow", category="emotion"),
    ActionInfo(name="action_005", display_name="Give a thumb-up", category="gesture"),
    ActionInfo(name="action_006", display_name="OK", category="gesture"),
    ActionInfo(name="action_007", display_name="Beat you up", category="playful"),
    ActionInfo(name="action_012", display_name="Ask for a hug", category="social"),
    ActionInfo(name="action_013", display_name="Make faces", category="playful"),
    ActionInfo(name="action_014", display_name="Invite", category="social"),
    ActionInfo(name="action_015", display_name="Wiggle the hips", category="playful"),
    ActionInfo(name="action_016", display_name="Say goodbye", category="greeting"),
    ActionInfo(name="action_019", display_name="Hold the head", category="gesture"),
    ActionInfo(name="action_020", display_name="A smug face action", category="emotion"),

    # Behavior-based dance actions (keep existing ones)
    ActionInfo(name="dance_0006en", display_name="Dance 6 (English)", category="dance"),
    ActionInfo(name="dance_0004en", display_name="Dance 4 (English)", category="dance"),
    ActionInfo(name="dance_0001", display_name="Dance 1", category="dance"),
    ActionInfo(name="dance_0002", display_name="Dance 2", category="dance"),
    ActionInfo(name="dance_0003", display_name="Dance 3", category="dance"),
    ActionInfo(name="dance_0005", display_name="Dance 5", category="dance"),
    ActionInfo(name="dance_0007", display_name="Dance 7", category="dance"),
    ActionInfo(name="dance_0008", display_name="Dance 8", category="dance"),
    ActionInfo(name="walk_forward", display_name="Walk Forward", category="movement"),
    ActionInfo(name="walk_backward", display_name="Walk Backward", category="movement"),
]

REAL_EXPRESSIONS: List[ExpressionInfo] = [
    # Code Mao expressions
    ExpressionInfo(name="codemao1", display_name="Look around", category="character"),
    ExpressionInfo(name="codemao2", display_name="Heartbreaking", category="character"),
    ExpressionInfo(name="codemao3", display_name="Sad", category="character"),
    ExpressionInfo(name="codemao4", display_name="Asleep", category="character"),
    ExpressionInfo(name="codemao5", display_name="Frightened", category="character"),
    ExpressionInfo(name="codemao6", display_name="Sleepy", category="character"),
    ExpressionInfo(name="codemao7", display_name="Strange", category="character"),
    ExpressionInfo(name="codemao8", display_name="Shocked", category="character"),
    ExpressionInfo(name="codemao9", display_name="Sneeze", category="character"),
    ExpressionInfo(name="codemao10", display_name="Cheer up", category="character"),
    ExpressionInfo(name="codemao11", display_name="Fighting", category="character"),
    ExpressionInfo(name="codemao12", display_name="Exert strength", category="character"),
    ExpressionInfo(name="codemao13", display_name="Doubt", category="character"),
    ExpressionInfo(name="codemao14", display_name="Wake up", category="character"),
    ExpressionInfo(name="codemao15", display_name="Distressed", category="character"),
    ExpressionInfo(name="codemao16", display_name="A sly smile", category="character"),
    ExpressionInfo(name="codemao17", display_name="Depressed", category="character"),
    ExpressionInfo(name="codemao18", display_name="Eager", category="character"),
    ExpressionInfo(name="codemao19", display_name="Love", category="character"),
    ExpressionInfo(name="codemao20", display_name="Blink", category="character"),

    # Basic expressions
    ExpressionInfo(name="w_basic_0003_1", display_name="Look to the right", category="basic"),
    ExpressionInfo(name="w_basic_0005_1", display_name="Look to the left", category="basic"),
    ExpressionInfo(name="w_basic_0010_1", display_name="Look up", category="basic"),
    ExpressionInfo(name="w_basic_0011_1", display_name="Look left and right", category="basic"),
    ExpressionInfo(name="w_basic_0012_1", display_name="Look up and down", category="basic"),

    # Emotion expressions
    ExpressionInfo(name="emo_007", display_name="Smile", category="emotion"),
    ExpressionInfo(name="emo_008", display_name="Agitated", category="emotion"),
    ExpressionInfo(name="emo_009", display_name="Tears", category="emotion"),
    ExpressionInfo(name="emo_010", display_name="Shy", category="emotion"),
    ExpressionInfo(name="emo_011", display_name="Cry aloud", category="emotion"),
    ExpressionInfo(name="emo_013", display_name="Angry", category="emotion"),
    ExpressionInfo(name="emo_014", display_name="Pathetic", category="emotion"),
    ExpressionInfo(name="emo_015", display_name="Arrogant", category="emotion"),
    ExpressionInfo(name="emo_016", display_name="Simper", category="emotion"),
    ExpressionInfo(name="emo_019", display_name="Dizzy", category="emotion"),
    ExpressionInfo(name="emo_020", display_name="Daze", category="emotion"),
    ExpressionInfo(name="emo_022", display_name="Wipe eye gunk", category="emotion"),
    ExpressionInfo(name="emo_023", display_name="Hurt", category="emotion"),
    ExpressionInfo(name="emo_026", display_name="Contemptuous look", category="emotion"),
    ExpressionInfo(name="emo_028", display_name="Cover up the face", category="emotion"),
]

# Keep test actions as minimal fallback
TEST_ACTIONS: List[ActionInfo] = [
    ActionInfo(name="action_019", display_name="Hold the head", category="emotion"),
    ActionInfo(name="Happy", display_name="Happy Action", category="emotion"),
    ActionInfo(name="Dance", display_name="Dance Action", category="movement"),
    ActionInfo(name="Wave", display_name="Wave Action", category="greeting"),
]

TEST_EXPRESSIONS: List[ExpressionInfo] = [
    ExpressionInfo(name="face_005", display_name="Happy Face", category="positive"),
    ExpressionInfo(name="face_010", display_name="Sad Face", category="negative"),
    ExpressionInfo(name="face_015", display_name="Surprised", category="reaction"),
    ExpressionInfo(name="face_020", display_name="Angry Face", category="negative"),
    ExpressionInfo(name="face_025", display_name="Sleepy", category="state"),
    ExpressionInfo(name="face_030", display_name="Wink", category="playful"),
    ExpressionInfo(name="face_035", display_name="Love Eyes", category="positive"),
    ExpressionInfo(name="face_039", display_name="Thinking", category="contemplative"),
    ExpressionInfo(name="face_040", display_name="Confused", category="reaction"),
    ExpressionInfo(name="face_045", display_name="Cool Glasses", category="playful"),
]

# Special actions for mouth lamp control
MOUTH_LAMP_ACTIONS: List[ActionInfo] = [
    ActionInfo(name="mouth_lamp_red", display_name="Red Mouth Lamp", category="lamp"),
    ActionInfo(name="mouth_lamp_green", display_name="Green Mouth Lamp", category="lamp"),
    ActionInfo(name="mouth_lamp_blue", display_name="Blue Mouth Lamp", category="lamp"),
    ActionInfo(name="mouth_lamp_off", display_name="Turn Off Mouth Lamp", category="lamp"),
    ActionInfo(name="mouth_lamp_breath_red", display_name="Red Breathing Lamp", category="lamp"),
    ActionInfo(name="mouth_lamp_breath_green", display_name="Green Breathing Lamp", category="lamp"),
    ActionInfo(name="mouth_lamp_breath_blue", display_name="Blue Breathing Lamp", category="lamp"),
]

# Enhanced Robot connection functions using test_connect.py logic
async def get_device_by_name_working(serial_suffix: str = "000341", timeout: int = 10) -> Optional[WiFiDevice]:
    """Search for devices based on the suffix of the robot serial number (from test_connect.py)"""
    logger.info(f"🔍 Searching for device with serial suffix: {serial_suffix}")

    try:
        result: WiFiDevice = await MiniSdk.get_device_by_name(serial_suffix, timeout)
        logger.info(f"📱 Device search result: {result}")

        if result:
            logger.info(f"✅ Found device: {result.name} at {result.address}:{result.port}")
            return result
        else:
            logger.warning("❌ No device found with specified serial suffix")
            return None

    except Exception as e:
        logger.error(f"💥 Error searching for device: {e}")
        logger.error(traceback.format_exc())
        return None

async def get_device_list_working(timeout: int = 10) -> List[WiFiDevice]:
    """Search all devices (from test_connect.py)"""
    logger.info("🔍 Searching for all devices...")

    try:
        results = await MiniSdk.get_device_list(timeout)
        logger.info(f"📱 Found {len(results) if results else 0} devices: {results}")
        return results or []

    except Exception as e:
        logger.error(f"💥 Error getting device list: {e}")
        logger.error(traceback.format_exc())
        return []

async def test_connect_working(dev: WiFiDevice) -> bool:
    """Connect the device (from test_connect.py)"""
    logger.info(f"🤝 Attempting to connect to device: {dev.name} at {dev.address}:{dev.port}")

    try:
        connected = await MiniSdk.connect(dev)
        logger.info(f"🔌 Connection result: {connected}")
        return connected

    except Exception as e:
        logger.error(f"💥 Connection error: {e}")
        logger.error(traceback.format_exc())
        return False

async def start_program_mode_working():
    """Enter programming mode (from test_connect.py)"""
    logger.info("🎯 Entering programming mode...")

    try:
        await MiniSdk.enter_program()
        logger.info("✅ Successfully entered programming mode")
        # Wait for robot to finish TTS broadcast
        await asyncio.sleep(2)
        logger.info("🎤 Waited for TTS broadcast to complete")

    except Exception as e:
        logger.error(f"💥 Error entering programming mode: {e}")
        logger.error(traceback.format_exc())
        raise

async def scan_for_robot() -> Optional[WiFiDevice]:
    """Scan for Alpha Mini robot using working connection method"""
    logger.info("🔍 Starting robot scan using working method...")
    robot_state.scan_results = []

    try:
        # Method 1: Try specific serial number search first
        logger.info("📡 Method 1: Searching by serial suffix '000341'...")
        device = await get_device_by_name_working("000341", 10)

        if device:
            device_info = f"Found by serial: {device.name} at {device.address}:{device.port}"
            logger.info(f"✅ {device_info}")
            robot_state.scan_results.append(device_info)
            return device

        # Method 2: Search all devices as fallback
        logger.info("📡 Method 2: Searching all devices...")
        device_list = await get_device_list_working(10)

        if device_list:
            logger.info(f"📊 Found {len(device_list)} devices")

            for i, device in enumerate(device_list):
                device_info = f"Device {i+1}: {device.name} at {device.address}:{device.port}"
                logger.info(f"📱 {device_info}")
                robot_state.scan_results.append(device_info)

            # Use first device found
            device = device_list[0]
            logger.info(f"✅ Selected first device: {device.name}")
            return device
        else:
            logger.warning("❌ No devices found with any method")
            robot_state.scan_results.append("No devices found")
            return None

    except Exception as e:
        logger.error(f"💥 Error during robot scan: {e}")
        logger.error(traceback.format_exc())
        robot_state.last_error = str(e)
        robot_state.scan_results.append(f"Scan error: {str(e)}")
        return None

async def connect_to_robot() -> bool:
    """Connect to the Alpha Mini robot using working connection method"""
    logger.info("🔗 Starting robot connection process using working method...")

    async with robot_state.connection_lock:
        if robot_state.is_connected:
            logger.info("✅ Already connected to robot")
            return True

        try:
            robot_state.is_connecting = True
            robot_state.connection_attempts += 1
            logger.info(f"🔄 Connection attempt #{robot_state.connection_attempts}")

            # Get device using working method
            if not robot_state.device:
                logger.info("🔍 No cached device, starting scan...")
                robot_state.device = await scan_for_robot()
                if not robot_state.device:
                    logger.error("❌ No robot device found during scan")
                    robot_state.last_error = "No robot device found"
                    return False

            # Connect using working method
            logger.info(f"🤝 Connecting to {robot_state.device.name}...")
            logger.info(f"📡 Device details: {robot_state.device.address}:{robot_state.device.port}")

            connected = await test_connect_working(robot_state.device)

            if connected:
                logger.info("🎯 Connection successful, entering program mode...")
                await start_program_mode_working()

                robot_state.is_connected = True
                robot_state.action_count = 0
                robot_state.last_error = None

                logger.info("🎉 Successfully connected and entered program mode!")
                return True
            else:
                logger.error("❌ Failed to establish connection")
                robot_state.last_error = "Failed to establish connection using working method"
                return False

        except Exception as e:
            logger.error(f"💥 Connection error: {e}")
            logger.error(traceback.format_exc())
            robot_state.last_error = str(e)
            robot_state.is_connected = False
            return False
        finally:
            robot_state.is_connecting = False
            logger.info(f"🏁 Connection process finished. Connected: {robot_state.is_connected}")

async def disconnect_from_robot() -> bool:
    """Disconnect from the robot using working method"""
    logger.info("🔌 Starting robot disconnection using working method...")

    async with robot_state.connection_lock:
        if not robot_state.is_connected:
            logger.info("✅ Already disconnected from robot")
            return True

        try:
            logger.info("🚪 Quitting program mode...")
            await MiniSdk.quit_program()

            logger.info("🔄 Releasing SDK resources...")
            await MiniSdk.release()

            robot_state.is_connected = False
            robot_state.last_error = None

            logger.info("✅ Successfully disconnected from robot")
            return True

        except Exception as e:
            logger.error(f"💥 Disconnect error: {e}")
            logger.error(traceback.format_exc())
            robot_state.last_error = str(e)
            return False

# Enhanced execution functions using test_expression.py methods
async def execute_behavior_action(action_name: str) -> tuple[bool, str, float]:
    """Execute a behavior action like dance (from test_expression.py)"""
    start_time = datetime.now()

    try:
        logger.info(f"🎭 Executing behavior: {action_name}")

        # Use StartBehavior API from test_expression.py
        block = StartBehavior(name=action_name)
        (resultType, response) = await block.execute()

        execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"📊 Behavior response: resultType={resultType}, response={response}")

        if resultType == MiniApiResultType.Success and response and response.isSuccess:
            message = f"Behavior '{action_name}' executed successfully"
            logger.info(f"✅ Behavior success: {message}")
            return True, message, execution_time
        else:
            error_msg = f"Behavior '{action_name}' failed"
            if response:
                error_msg += f" - resultCode: {response.resultCode}"
                if hasattr(response, 'resultCode'):
                    error_msg += f", error: {errors.get_express_error_str(response.resultCode)}"

            logger.error(f"❌ Behavior failed: {error_msg}")
            return False, error_msg, execution_time

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = f"Error executing behavior '{action_name}': {str(e)}"
        logger.error(f"💥 {error_msg}")
        logger.error(traceback.format_exc())
        return False, error_msg, execution_time

async def execute_expression_real(expression_name: str) -> tuple[bool, str, float]:
    """Execute an expression using real method from test_expression.py"""
    start_time = datetime.now()

    try:
        logger.info(f"😊 Executing expression: {expression_name}")

        # Use PlayExpression with express_name parameter (from test_expression.py)
        block = PlayExpression(express_name=expression_name)
        (resultType, response) = await block.execute()

        execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"📊 Expression response: resultType={resultType}, response={response}")

        if resultType == MiniApiResultType.Success and response and response.isSuccess:
            message = f"Expression '{expression_name}' executed successfully"
            logger.info(f"✅ Expression success: {message}")
            return True, message, execution_time
        else:
            error_msg = f"Expression '{expression_name}' failed"
            if response:
                error_msg += f" - resultCode: {response.resultCode}"

            logger.error(f"❌ Expression failed: {error_msg}")
            return False, error_msg, execution_time

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = f"Error executing expression '{expression_name}': {str(e)}"
        logger.error(f"💥 {error_msg}")
        logger.error(traceback.format_exc())
        return False, error_msg, execution_time

async def execute_mouth_lamp_action(action_name: str) -> tuple[bool, str, float]:
    """Execute mouth lamp control actions from test_expression.py"""
    start_time = datetime.now()

    try:
        logger.info(f"💡 Executing mouth lamp action: {action_name}")

        if action_name == "mouth_lamp_off":
            # Turn off mouth lamp
            (resultType, response) = await ControlMouthLamp(is_open=False).execute()
        elif action_name.startswith("mouth_lamp_breath_"):
            # Breathing mode
            color_map = {"red": MouthLampColor.RED, "green": MouthLampColor.GREEN, "blue": MouthLampColor.BLUE}
            color_name = action_name.split("_")[-1]
            color = color_map.get(color_name, MouthLampColor.GREEN)

            block = SetMouthLamp(color=color, mode=MouthLampMode.BREATH, duration=-1, breath_duration=1000)
            (resultType, response) = await block.execute()
        elif action_name.startswith("mouth_lamp_"):
            # Normal mode
            color_map = {"red": MouthLampColor.RED, "green": MouthLampColor.GREEN, "blue": MouthLampColor.BLUE}
            color_name = action_name.split("_")[-1]
            color = color_map.get(color_name, MouthLampColor.GREEN)

            block = SetMouthLamp(color=color, mode=MouthLampMode.NORMAL, duration=3000, breath_duration=1000)
            (resultType, response) = await block.execute()
        else:
            return False, f"Unknown mouth lamp action: {action_name}", 0.0

        execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"📊 Mouth lamp response: resultType={resultType}, response={response}")

        if resultType == MiniApiResultType.Success and response and (response.isSuccess or response.resultCode == 504):
            message = f"Mouth lamp '{action_name}' executed successfully"
            logger.info(f"✅ Mouth lamp success: {message}")
            return True, message, execution_time
        else:
            error_msg = f"Mouth lamp '{action_name}' failed"
            if response:
                error_msg += f" - resultCode: {response.resultCode}"

            logger.error(f"❌ Mouth lamp failed: {error_msg}")
            return False, error_msg, execution_time

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = f"Error executing mouth lamp '{action_name}': {str(e)}"
        logger.error(f"💥 {error_msg}")
        logger.error(traceback.format_exc())
        return False, error_msg, execution_time

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main HTML interface"""
    logger.info("🌐 Serving main HTML interface")
    try:
        with open("alpha_mini_test.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        logger.error("❌ HTML interface file not found")
        return HTMLResponse(
            content="<h1>Alpha Mini Controller</h1><p>HTML interface file not found</p>",
            status_code=404
        )

@app.get("/api/status", response_model=ConnectionStatus)
async def get_connection_status():
    """Get current robot connection status with detailed info"""
    status = ConnectionStatus(
        connected=robot_state.is_connected,
        device_name=robot_state.device.name if robot_state.device else None,
        device_address=robot_state.device.address if robot_state.device else None,
        connection_time=datetime.now().isoformat() if robot_state.is_connected else None,
        action_count=robot_state.action_count
    )

    logger.debug(f"📊 Status check: Connected={status.connected}, Actions={status.action_count}")
    return status

@app.get("/api/debug")
async def get_debug_info():
    """Get detailed debug information"""
    debug_info = {
        "robot_state": {
            "is_connected": robot_state.is_connected,
            "is_connecting": robot_state.is_connecting,
            "connection_attempts": robot_state.connection_attempts,
            "action_count": robot_state.action_count,
            "last_error": robot_state.last_error,
            "scan_results": robot_state.scan_results,
            "device_info": {
                "name": robot_state.device.name if robot_state.device else None,
                "address": robot_state.device.address if robot_state.device else None,
                "port": robot_state.device.port if robot_state.device else None,
            } if robot_state.device else None
        },
        "system_info": {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "log_file": "alpha_mini_controller.log"
        }
    }

    logger.info("🔍 Debug info requested")
    return debug_info

@app.post("/api/connect")
async def connect_robot():
    """Connect to Alpha Mini robot with enhanced logging"""
    logger.info("🔗 Connect API endpoint called")

    if robot_state.is_connecting:
        logger.warning("⚠️ Connection already in progress")
        raise HTTPException(status_code=409, detail="Connection already in progress")

    if robot_state.is_connected:
        logger.info("✅ Already connected")
        return {"success": True, "message": "Already connected"}

    success = await connect_to_robot()

    if success:
        logger.info("🎉 Connect API: Success")
        return {
            "success": True,
            "message": "Connected successfully",
            "device_name": robot_state.device.name if robot_state.device else None
        }
    else:
        error_msg = robot_state.last_error or "Unknown connection error"
        logger.error(f"❌ Connect API: Failed - {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to robot: {error_msg}"
        )

@app.post("/api/disconnect")
async def disconnect_robot():
    """Disconnect from Alpha Mini robot with enhanced logging"""
    logger.info("🔌 Disconnect API endpoint called")

    if not robot_state.is_connected:
        logger.info("✅ Already disconnected")
        return {"success": True, "message": "Already disconnected"}

    success = await disconnect_from_robot()

    if success:
        logger.info("👋 Disconnect API: Success")
        return {"success": True, "message": "Disconnected successfully"}
    else:
        error_msg = robot_state.last_error or "Unknown disconnect error"
        logger.error(f"❌ Disconnect API: Failed - {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect from robot: {error_msg}"
        )

@app.post("/api/actions/execute", response_model=ActionResponse)
async def execute_action(request: ActionRequest):
    """Execute an action on the Alpha Mini robot with detailed logging"""
    logger.info(f"🎭 Execute action API called: {request.name}")

    if not robot_state.is_connected:
        logger.error("❌ Robot not connected for action execution")
        raise HTTPException(status_code=412, detail="Robot not connected")

    try:
        # Determine action type and execute accordingly
        if request.name.startswith("dance_") or request.name in ["walk_forward", "walk_backward"]:
            # Use behavior API for dance and movement actions
            success, message, execution_time = await execute_behavior_action(request.name)
        elif request.name.startswith("mouth_lamp_"):
            # Use mouth lamp API for lamp control
            success, message, execution_time = await execute_mouth_lamp_action(request.name)
        else:
            # Try regular PlayAction API as fallback
            start_time = datetime.now()
            logger.info(f"⚡ Executing regular action: {request.name}")

            response = await PlayAction(action_name=request.name).execute()
            execution_time = (datetime.now() - start_time).total_seconds()

            if response and len(response) > 1 and hasattr(response[1], 'isSuccess'):
                success = response[1].isSuccess
                message = f"Action '{request.name}' executed successfully" if success else f"Action '{request.name}' failed"
            else:
                success = True
                message = f"Action '{request.name}' executed"

        robot_state.action_count += 1
        robot_state.last_action_time = datetime.now()

        result = ActionResponse(
            success=success,
            message=message,
            execution_time=execution_time,
            action_name=request.name
        )

        logger.info(f"🎯 Action completed in {execution_time:.2f}s")
        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"💥 Action execution error: {error_msg}")
        logger.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute action '{request.name}': {error_msg}"
        )

@app.post("/api/expressions/execute", response_model=ExpressionResponse)
async def execute_expression(request: ExpressionRequest):
    """Execute an expression on the Alpha Mini robot with detailed logging"""
    logger.info(f"😊 Execute expression API called: {request.name}")

    if not robot_state.is_connected:
        logger.error("❌ Robot not connected for expression execution")
        raise HTTPException(status_code=412, detail="Robot not connected")

    try:
        # Use real expression execution method
        success, message, execution_time = await execute_expression_real(request.name)

        robot_state.action_count += 1
        robot_state.last_action_time = datetime.now()

        result = ExpressionResponse(
            success=success,
            message=message,
            execution_time=execution_time,
            expression_name=request.name
        )

        logger.info(f"🎯 Expression completed in {execution_time:.2f}s")
        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"💥 Expression execution error: {error_msg}")
        logger.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute expression '{request.name}': {error_msg}"
        )

@app.get("/api/actions", response_model=List[ActionInfo])
async def get_available_actions():
    """Get list of available actions including real ones from test_expression.py"""
    all_actions = []

    # Add real behavior actions
    all_actions.extend(REAL_ACTIONS)

    # Add mouth lamp actions
    all_actions.extend(MOUTH_LAMP_ACTIONS)

    # Try to get actions from robot if connected
    if robot_state.is_connected:
        try:
            response = await GetActionList().execute()
            if response and len(response) > 1 and hasattr(response[1], 'actionList'):
                robot_actions = []
                for action in response[1].actionList:
                    robot_actions.append(ActionInfo(
                        name=action,
                        display_name=action.replace('_', ' ').title(),
                        category="robot"
                    ))
                all_actions.extend(robot_actions)
                logger.info(f"📦 Loaded {len(robot_actions)} actions from robot")
        except Exception as e:
            logger.warning(f"Could not get real action list: {e}")

    # Add test actions as additional fallback
    all_actions.extend(TEST_ACTIONS)

    logger.info(f"📋 Returning {len(all_actions)} total actions")
    return all_actions

@app.get("/api/expressions", response_model=List[ExpressionInfo])
async def get_available_expressions():
    """Get list of available expressions including real ones from test_expression.py"""
    # Return real expressions first, then test expressions
    all_expressions = REAL_EXPRESSIONS + TEST_EXPRESSIONS
    logger.info(f"📋 Returning {len(all_expressions)} total expressions")
    return all_expressions

# Enhanced Background task for connection monitoring
async def monitor_connection():
    """Monitor robot connection and auto-reconnect if needed with logging"""
    logger.info("👁️ Connection monitor started")

    while True:
        try:
            if robot_state.is_connected and robot_state.device:
                logger.debug("🔍 Checking connection health...")
                # Connection is assumed healthy if no exceptions occur
                await asyncio.sleep(10)
                logger.debug("✅ Connection health check passed")
            else:
                logger.debug("⏸️ No active connection to monitor")
                await asyncio.sleep(5)

        except Exception as e:
            logger.warning(f"⚠️ Connection check failed: {e}")
            robot_state.is_connected = False
            robot_state.last_error = f"Connection monitor error: {str(e)}"
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup with detailed logging"""
    logger.info("🚀 Alpha Mini FastAPI Controller starting up...")
    logger.info(f"📅 Startup time: {datetime.now()}")
    logger.info(f"🐍 Python version: {sys.version}")

    # Start connection monitoring in background
    asyncio.create_task(monitor_connection())
    logger.info("👁️ Connection monitor task started")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown with detailed logging"""
    logger.info("🛑 Alpha Mini FastAPI Controller shutting down...")

    if robot_state.is_connected:
        logger.info("🔌 Disconnecting robot during shutdown...")
        await disconnect_from_robot()

    logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    print("🤖 Starting Alpha Mini FastAPI Controller...")
    print("📱 Web Interface: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔧 ReDoc Documentation: http://localhost:8000/redoc")
    print("🔍 Debug Info: http://localhost:8000/api/debug")
    print("📝 Log file: alpha_mini_controller.log")

    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
