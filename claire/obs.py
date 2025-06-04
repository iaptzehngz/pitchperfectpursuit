import obsws_python as obs
import time
import os

cl = obs.ReqClient(host='localhost', port=4455, password='password', timeout=3)

cl.start_record()
time.sleep(40)

cl.stop_record()
time.sleep(0.5)

os.startfile(r"C:\Users\user\Videos\video.mkv")
time.sleep(40)

os.system('taskkill /IM Microsoft.Media.Player.exe /F')