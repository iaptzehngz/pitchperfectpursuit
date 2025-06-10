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

class MainApp(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.name = ""  # store the entered name
        self.frame = FirstFrame(self)
        self.frame.pack()

    def change(self, frame_class):
        self.frame.pack_forget()
        self.frame = frame_class(self)
        self.frame.pack()

class FirstFrame(tk.Frame):
    def __init__(self, master=None, **kwargs):
        tk.Frame.__init__(self, master, **kwargs)

        master.title("Enter Name")
        master.geometry("300x200")

        lbl = tk.Label(self, text="Enter your name")
        lbl.pack()

        self.name_entry = tk.Entry(self)
        self.name_entry.pack()
        self.name_entry.focus()

        done_btn = tk.Button(self, text="Done", command=self.proceed)
        done_btn.pack()

        cancel_btn = tk.Button(self, text="Cancel", command=self.quit)
        cancel_btn.pack()

    def proceed(self):
        name = self.name_entry.get().strip()
        if name:
            self.master.name = name  #store name
            self.master.change(SecondFrame)

class SecondFrame(tk.Frame):
    def __init__(self, master=None, **kwargs):
        tk.Frame.__init__(self, master, **kwargs)
        master.title("Enter Name")
        master.geometry("600x400")

        lbl = tk.Label(self, text=f'Welcome to flight training {master.name}! Kindly wait while the simulator loads...')
        lbl.pack()
        master.after(1500, master.destroy)


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
                print(f'{pickle.loads(data)}')
            
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
        difficulty = 3
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

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()

    global difficulty, distance_time, pitch_time, heading_time, saves_dir, direction, csv_data, dataset_raw
    dataset_raw = []
    difficulty = 0
    direction = 1

    app = MainApp() #login page
    app.mainloop()

    date_time = datetime.now()
    str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")
    name = app.name.upper()
    file_name = f'{name} {str_date_time}'
    saves_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saves', file_name) #file name and directory
    os.makedirs(saves_dir)
    cl.set_record_directory(saves_dir)

    for i in range(10):
        subprocess.run('start steam://run/2014780', shell=True)
        conn, addr = sock.accept()
        with conn:
            if i == 1:
                flight_desc = 'PRE-TEST'
            elif i == 9:
                flight_desc = 'POST-TEST'
            else:
                flight_desc = str(i-1)
            if i in (1,2,3,4,5,6,7,8,9):
                cl.set_profile_parameter("Output", "FilenameFormatting", flight_desc)

            difficulty, distance_time, pitch_time, heading_time = get_diff(i, dataset_raw, difficulty)
            direction *= -1

            conn.send(pickle.dumps([difficulty, direction]))
            dataset_raw = stream_actions(conn)

            if i in (2,3,4,5,6,7,8):
                subprocess.Popen(["C:\\Program Files\\VideoLAN\\VLC\\vlc.exe", '--play-and-exit', os.path.join(saves_dir, f'{flight_desc}.mkv')])      

            if i == 2:
                write_log(saves_dir, 'scores.txt', f'**PRE-TEST**:\n\n% time within:\nabs(pitch dev<5deg): {pitch_time}, \nabs(heading dev<5deg): {heading_time}, \n500ft<distance<1500ft: {distance_time}\n\n\n\n')
                csv_data = ['DDA', name, str_date_time, distance_time, pitch_time, heading_time]
            if i in (2,3,4,5,6,7,8):
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
write_trainee_csv(os.path.dirname(os.path.abspath(__file__)), 'trainee_data.csv', 
                                  ['group, name, strdatetime, pre dob, pre pob, pre hob, post dob, post pob, post hob, rating, feedback'],
                                  csv_data)
