import subprocess
import socket
import pickle
import copy
import numpy as np
import obsws_python as obs
import time
import psutil
import tkinter as tk
import os
from datetime import datetime
import csv

HOST = '127.0.0.1'
PORT = 8888
CWD = os.path.dirname(os.path.abspath(__file__))

def stream_actions(conn):
    dataset_raw = []
    getting = True
    while getting:
        data = conn.recv(1024)
        if data:
            new_data = pickle.loads(data)
            if new_data == 'end':
                subprocess.call('taskkill /F /IM X-Plane.exe')
                getting = False
            elif new_data == 'stop recording':
                cl.stop_record()
            elif new_data == 'start recording':
                cl.start_record()
            else:
                dataset_raw += [new_data,]
            
    return dataset_raw
    
def get_diff(i, difficulty):
    #GET DATA
    dataset = copy.deepcopy(dataset_raw)
    for j in range(len(dataset)-1):
        dataset[j][0] = dataset_raw [j+1][0] - dataset_raw[j][0] #process data such that time is intervals rather than timestamps
    dataset = dataset[:-1]

    def percentage_time(data, lower, upper, index):
        within_range = list(filter(lambda x:lower <= x[index] <= upper, data))
        time_within_range = 0
        total_time = sum(row[0] for row in data)
        for k in range(len(within_range)):
            time_within_range += within_range[k][0]
        percentage_time = (time_within_range/total_time)*100
        return percentage_time
    
    #GET TIMINGS
    if i > 0:
        distance_time = percentage_time(dataset, 152.4, 457.2, 1)
        pitch_time = percentage_time(dataset, -5, 5, 2)
        heading_time = percentage_time(dataset, -5, 5, 3)
    else:
        distance_time , pitch_time, heading_time = 0,0,0
    
    #GET DIFFICULTY
    if i == 0:
        difficulty = 0
    elif i == 2:
        difficulty = 4
    elif i == 1 or i == 9:
        difficulty = 8
    else:
        def diff(percentage_time):
            if percentage_time >= 70:
                diff = 2
            elif percentage_time >=50:
                diff = 0
            else:
                diff = -1
                        
            return diff
            
        distance_diff = diff(distance_time)
        pitch_diff = diff(pitch_time)
        heading_diff = diff(heading_time)
        
        diff_change = min(distance_diff, pitch_diff, heading_diff)
        difficulty = min(max(difficulty+diff_change, 1), 7)

    return difficulty, distance_time, pitch_time, heading_time

def write_log(dir, filename, content):
    with open(os.path.join(dir, filename), 'a', encoding='utf-8') as f:
        f.write(content)

def write_trainee_csv(dir, filename, columns, content):
    file_path = os.path.join(dir, filename)
    file_exists = os.path.exists(file_path)
    with open(file_path, 'a', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(columns)
        writer.writerow(content)

def one_PI(dir, wanted_filename, placeholder_filename, other_PIs, placeholder_other_PIs):
    file_path = os.path.join(dir, wanted_filename)
    file_exists = os.path.exists(file_path)
    if not file_exists:
        os.rename(os.path.join(dir, placeholder_filename), file_path)
    for i in range(2):
        other_PI = other_PIs[i]
        placeholder_other_PI = placeholder_other_PIs[i]
        file_path = os.path.join(dir, placeholder_other_PI)
        file_exists = os.path.exists(file_path)
        if not file_exists:
            os.rename(os.path.join(dir, other_PI), placeholder_other_PI)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()

    global difficulty, distance_time, pitch_time, heading_time, saves_dir, direction, csv_data, dataset_raw
    dataset_raw = []
    difficulty = 0
    direction = 1

    one_PI(CWD, 'PI_DDA.py', 'notPI_DDA.py', ('PI_control.py', 'PI_feedback.py'), ('notPI_control.py', 'notPI_feedback.py'))

    name = input("Enter your name: ")
    name = name.upper()
    date_time = datetime.now()
    str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")
    file_name = f'{name} {str_date_time}'
    saves_dir = os.path.join(CWD, 'saves', file_name) #file name and directory
    os.makedirs(saves_dir)
    cl.set_record_directory(saves_dir)

    for i in range(10):
        if i == 1:
            flight_desc = 'pre-training'
        elif i == 9:
            flight_desc = 'post-training'
        elif i == 0:
            flight_desc = 'familiarisation'
        else:
            flight_desc = 'flight'+ str(i-1)
        print(f"\n--- Starting {flight_desc} ---\n")
        subprocess.run('start steam://run/2014780', shell=True)
        conn, addr = sock.accept()
        with conn:
            
            if i in (1,2,3,4,5,6,7,8,9):
                cl.set_profile_parameter("Output", "FilenameFormatting", flight_desc)

            difficulty, distance_time, pitch_time, heading_time = get_diff(i, difficulty)
            direction *= -1

            conn.send(pickle.dumps([difficulty, direction]))
            dataset_raw = stream_actions(conn)

            if i in (2,3,4,5,6,7,8):
                subprocess.Popen(["C:\\Program Files\\VideoLAN\\VLC\\vlc.exe", '--play-and-exit', os.path.join(saves_dir, f'{flight_desc}.mkv')])      

            if i == 2:
                write_log(saves_dir, 'scores.txt', f'**PRE-TEST**:\n\n% time within:\nabs(pitch dev<5deg): {pitch_time}, \nabs(heading dev<5deg): {heading_time}, \n500ft<distance<1500ft: {distance_time}\n\n\n\n')
                csv_data = ['DDA', name, str_date_time, distance_time, pitch_time, heading_time]

            if i in (2,3,4,5,6,7,8):
                time.sleep(34) 
                print("\nSelf-reflect for 30 seconds.\n")
                time.sleep(30)
            
            
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startupinfo.wShowWindow = 2
obs_running = any(
        proc.info['name'] and 'obs64.exe' in proc.info['name'].lower()
        for proc in psutil.process_iter(['name'])
    )
if not obs_running:
    subprocess.Popen(r'C:\Program Files\obs-studio\bin\64bit\obs64.exe', cwd='C:/Program Files/obs-studio/bin/64bit/', startupinfo=startupinfo)
    time.sleep(7)
cl = obs.ReqClient()

main()
difficulty, distance_time, pitch_time, heading_time = get_diff(9, 8)
write_log(saves_dir, 'scores.txt', f'**POST-TEST**:\n\n%time within:\nabs(pitch dev<5deg): {pitch_time}, \nabs(heading dev<5deg): {heading_time}, \n500ft<distance<1500ft: {distance_time}\n\n\n\n')
csv_data += [distance_time, pitch_time, heading_time]
write_trainee_csv(CWD, 'trainee_data.csv', 
                                  ['Group', 'Name', 'Date time', 'Pre distance score', 'Pre pitch score', 'Pre heading score ', 'Post distance score','Post pitch score',  "Post heading score",' Rating', 'Feedback'],
                                  csv_data)
