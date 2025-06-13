import time
from datetime import datetime
import csv
import os
import subprocess
import psutil
import zmq
import numpy
import pandas as pd
import matplotlib.pyplot as plt
import obsws_python as obs
from langchain_google_genai import ChatGoogleGenerativeAI
import re
from rich.console import Console
from rich.markdown import Markdown

CWD = os.path.dirname(os.path.abspath(__file__))
os.chdir(CWD)

HOST = "127.0.0.1"
PORT_STREAM = 5555
PORT_MANOEUVRE = 6666

OBS_PATH = "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"
VLC_PATH = "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"

def setup_obs(saves_dir):
    obs_running = any(
        proc.info['name'] and 'obs64.exe' in proc.info['name'].lower()
        for proc in psutil.process_iter(['name'])
    )
    if not obs_running:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 2  # 6 = SW_MINIMIZE
        subprocess.Popen(OBS_PATH, cwd=OBS_PATH[:-9], startupinfo=startupinfo)
        time.sleep(10) # wait for OBS to start up - it needs to be ready for the below requests
    obs_client = obs.ReqClient() # default args: host='localhost', port=4455, password='', timeout=None
    obs_client.set_record_directory(saves_dir)
    # obs_client.set_profile_parameter("AdvOut", 'FFFilePath', RECORDING_DIR) # if using advanced recording settings in OBS studio
    return obs_client

def communicate_xp(i, obs_client):
    with zmq.Context() as c:
        with c.socket(zmq.PUSH) as s:
            s.connect(f'tcp://{HOST}:{PORT_MANOEUVRE}')
            s.send_json(i)
        with c.socket(zmq.PULL) as s:
            s.bind(f'tcp://{HOST}:{PORT_STREAM}')
            data = collect_data(s, obs_client)
    return data

def collect_data(sock, obs_client):
    values = []
    manoeuvre_description = None
    aircraft_type = None # "Cessna 172 SP Skyhawk - 180HP - G1000"
    crashed = 'Trainee did not crash the plane'
    while True:
        data = sock.recv_json()
        if data['stream'] == 'variables':
            values.append(data['data'])
        elif data['stream'] == 'stop':
            break
        elif data['stream'] == 'recording':
            if data['data'] == 'start':
                obs_client.start_record()
            elif data['data'] == 'stop':
                obs_client.stop_record()
        elif data['stream'] == 'aircraft type':
            aircraft_type = data['data']
        elif data['stream'] == 'manoeuvre':
            manoeuvre_description = data['data']
        elif data['stream'] == 'crashed':
            crashed = f'Trainee crashed the plane at {data["data"]} seconds'
        else:
            raise KeyError(f"Unknown stream type") 
    return values, manoeuvre_description, aircraft_type, crashed

def process_dataframe(values):
    df = pd.DataFrame(values[:-1])
    df['Δt'] = df['t'].diff()
    df = df.set_index('t')
    df['pitch deviation'] = df['pitch'] - df['ideal pitch']
    df['heading deviation'] = df['heading'] - df['ideal heading']
    df['heading deviation'] = [hd - 360 if hd > 180 else hd + 360 if hd < -180 else hd for hd in df['heading deviation']]
    df['dist ok bo'] = [True if d > 152.4 and d < 457.2 else False for d in df['distance']]
    df['pdev ok bo'] = [True if abs(pdev) < 5 else False for pdev in df['pitch deviation']]
    df['hdev ok bo'] = [True if abs(hdev) < 5 else False for hdev in df['heading deviation']]
    n = len(df.index)
    dob, pob, hob = df[['dist ok bo', 'pdev ok bo', 'hdev ok bo']].sum() / n * 100
    return df, dob, pob, hob

def save_df(df, saves_dir, flight_description, manoeuvre_description):
    df = df.round(2)
    df.index = df.index.round(2)
    df.to_csv(os.path.join(saves_dir, f'{flight_description}.csv'))
    return df

def write_log(dir: str, filename: str, content: str):
    with open(os.path.join(dir, filename), 'a', encoding='utf-8') as f:
        f.write(content)

def rating(group):
    while True:
        try:
            rating = int(input(f"On a scale of 1 to 5, how useful was the {group}?\n"))
            if rating in range(1, 6):
                break
            else:
                print('Enter an integer between 1 and 5')
        except ValueError:
            print("Enter an integer")
    return rating

def write_trainee_csv(dir: str, filename: str, columns: list, content: list):
    file_path = os.path.join(dir, filename)
    file_exists = os.path.exists(file_path)
    with open(file_path, 'a', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(columns)
        writer.writerow(content)

def main():
    name = input("Enter your name: ")
    name = name.upper()
    date_time = datetime.now()
    str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")
    saves_dir = os.path.join(CWD, 'saves', f'{name} {str_date_time}')
    os.makedirs(saves_dir)
    trainee_data = ['control', name, str_date_time]

    obs_client = setup_obs(saves_dir)

    for i in range(10):
        subprocess.run(['start', 'steam://run/2014780'], shell=True)
        
        flight_description = ['familiarisation', 'pre-training', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'post-training'][i]
        print(f"\n--- Starting {flight_description} flight ---\n")

        obs_client.set_profile_parameter("Output", "FilenameFormatting", flight_description)

        values, manoeuvre_description, aircraft_type, crashed = communicate_xp(i, obs_client)

        df, dob, pob, hob = process_dataframe(values)
        df = save_df(df, saves_dir, flight_description, manoeuvre_description)
        if i in (1, 9):
            trainee_data.extend((dob, pob, hob))
            write_log(saves_dir, 'scores.txt', f'**{flight_description}**:\n\n%time within:\n500ft<distance<1500ft: {dob},\nabs(pitch dev<5deg): {pob}, \nabs(heading dev<5deg): {hob}\n\n\n\n')
        if i in range(2, 9):
            print(f'\nEnemy aircraft executed "{manoeuvre_description}"\n')

            vlc_process = subprocess.Popen([VLC_PATH, '--play-and-exit', os.path.join(saves_dir, f'{flight_description}.mp4')])
            while vlc_process.poll() is None:
                time.sleep(1)

            print("Self-reflect for 30 seconds.")

            time.sleep(30)
    feedback_rating = rating('feedback')
    feedback_feedback = input("Any feedback on the feedback?\n")
#    write_log(saves_dir, 'rating.txt', f'feedback rating from 1 to 5:\n{feedback_rating}\nfeedback on feedback:\n{feedback_feedback}')
    trainee_data.extend((feedback_rating, feedback_feedback))
    trainee_data_cols = ['group, name, strdatetime, pre dob, pre pob, pre hob, post dob, post pob, post hob, rating, feedback']
    write_trainee_csv(CWD, 'trainee_data.csv', trainee_data_cols, trainee_data)

if __name__ == "__main__":
    main()
