import obsws_python as obs
import time
import subprocess

cl = obs.ReqClient(host='localhost', port=4455, password='password', timeout=3)

cl.start_record()
time.sleep(40)

cl.stop_record()
time.sleep(0.5)

subprocess.Popen(['start', r"C:\Users\user\Videos\video.mkv"], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
time.sleep(40)

subprocess.Popen(['taskkill', '/IM', 'Microsoft.Media.Player.exe', '/F'], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
