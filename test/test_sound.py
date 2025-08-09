import asyncio

from mini.apis import errors
from mini.apis.api_sound import ChangeRobotVolume, ChangeRobotVolumeResponse
from mini.apis.api_sound import FetchAudioList, GetAudioListResponse, AudioSearchType
from mini.apis.api_sound import PlayAudio, PlayAudioResponse, AudioStorageType
# from mini.apis.api_sound import PlayOnlineMusic, MusicResponse
from mini.apis.api_sound import StartPlayTTS, StopPlayTTS, ControlTTSResponse
from mini.apis.api_sound import StopAllAudio, StopAudioResponse
from mini.apis.base_api import MiniApiResultType
from mini.dns.dns_browser import WiFiDevice
from test.test_connect import test_connect, shutdown
from test.test_connect import test_get_device_by_name, test_start_run_program


# Test text synthesis sound
async def test_play_tts():
    """Test play tts

     Make the robot start playing a tts, the content is "Hello, I am Alphamini, la la la", and wait for the result

     #ControlTTSResponse.isSuccess: Is it successful

     #ControlTTSResponse.resultCode: Return code

    """
    # is_serial: Serial execution
    # text: The text to be synthesized
    block: StartPlayTTS = StartPlayTTS(text="I love FPT so much, i love my school, my school is so wonderful",)
    # Return a tuple, response is a ControlTTSResponse
    (resultType, response) = await block.execute()

    print(f'test_play_tts result: {response}')
    # The response of  StartPlayTTS block contains resultCode and isSuccess
    # If resultCode !=0, you can query the error description information through errors.get_speech_error_str(response.resultCode))
    print('resultCode = {0}, error = {1}'.format(response.resultCode, errors.get_speech_error_str(response.resultCode)))

    assert resultType == MiniApiResultType.Success, 'test_play_tts timetout'
    assert response is not None and isinstance(response, ControlTTSResponse), 'test_play_tts result unavailable'
    assert response.isSuccess, 'test_play_tts failed'

# Test stop the tts being played
async def test_stop_audio_tts():
    """Test stop all audio being played

     Play a period of tts first, after 3s, stop all sound effects, and wait for the result

     #StopAudioResponse.isSuccess: Is it successful　

     #StopAudioResponse.resultCode: Return code

    """
    # Set is_serial=False, which means that you only need to send the instruction to the robot, and await does not need to wait for the robot to finish executing the result before returning
    block: StartPlayTTS = StartPlayTTS(is_serial=False,
                                       text="You let me say, let me say, don't interrupt me, don't interrupt me, don't interrupt me")
    response = await block.execute()
    print(f'test_stop_audio.play_tts: {response}')
    await asyncio.sleep(3)

    # Stop all sounds
    block: StopAllAudio = StopAllAudio()
    (resultType, response) = await block.execute()

    print(f'test_stop_audio:{response}')

    block: StartPlayTTS = StartPlayTTS(
        text="The second time, you let me say, let me say, don’t interrupt me, don’t interrupt me, don’t interrupt me")
    asyncio.create_task(block.execute())
    print(f'test_stop_audio.play_tts: {response}')
    await asyncio.sleep(3)

    assert resultType == MiniApiResultType.Success, 'test_stop_audio timetout'
    assert response is not None and isinstance(response, StopAudioResponse), 'test_stop_audio result unavailable'
    assert response.isSuccess, 'test_stop_audio failed'


# Test, change the volume of the robot
async def test_change_robot_volume():
    """Adjust the robot volume demo

     Set the robot volume to 0.5 and wait for the reply result

     #ChangeRobotVolumeResponse.isSuccess: Is it successful

     #ChangeRobotVolumeResponse.resultCode: Return code
    """
    # volume: 0~1.0
    block: ChangeRobotVolume = ChangeRobotVolume(volume=0.5)
    # response:ChangeRobotVolumeResponse
    (resultType, response) = await block.execute()

    print(f'test_change_robot_volume result:{response}')

    assert resultType == MiniApiResultType.Success, 'test_change_robot_volume timetout'
    assert response is not None and isinstance(response,
                                               ChangeRobotVolumeResponse), 'test_change_robot_volume result unavailable'
    assert response.isSuccess, 'get_action_list failed'


async def main():
    device: WiFiDevice = await test_get_device_by_name()
    if device:
        await test_connect(device)
        #await test_start_run_program()
        await test_play_tts()
        #await test_stop_play_tts()
        #await test_get_audio_list()
        #await test_play_local_audio()
        #await test_play_online_audio()
        #await test_stop_audio_tts()
        #await test_change_robot_volume()
        await shutdown()


if __name__ == '__main__':
    asyncio.run(main())
