import time
from datetime import datetime
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

MODEL_NAME = "gemini-2.5-flash-preview-05-20"
GOOGLE_API_KEY = "AIzaSyDh7u2AuBEfk_O_IuhuA0A2wIw6pXczlfE"

OBS_PATH = "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"
# RECORDING_DIR = CWD
# RECORDING_NAME = "I love DSTA"
# RECORDING_PATH = os.path.join(RECORDING_DIR, RECORDING_NAME + '.mp4')

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
    # obs_client.set_profile_parameter("Output", "FilenameFormatting", first_name)
    # obs_client.set_profile_parameter("Output", 'OverwriteIfExists', 'true')
    return obs_client

def communicate_xp(manoeuvre_no, obs_client):
    with zmq.Context() as c:
        with c.socket(zmq.PUSH) as s:
            s.connect(f'tcp://{HOST}:{PORT_MANOEUVRE}')
            s.send_json(manoeuvre_no)
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
    df['rate of change of distance'] = df['distance'].diff() / df['Δt']
    df['rate of change of indicated airspeed'] = df['indicated airspeed'].diff() / df['Δt']
    df['pitch rate'] = df['pitch'].diff() / df['Δt']
    df['roll rate'] = df['roll'].diff() / df['Δt']
    df['in front of or behind enemy plane'] = ['behind' if aa < 90 else 'in front' for aa in df['aspect angle']]
    df['pdev ok bo'] = [True if abs(pdev) < 5 else False for pdev in df['pitch deviation']]
    df['hdev ok bo'] = [True if abs(hdev) < 5 else False for hdev in df['heading deviation']]
    df['dist ok bo'] = [True if d > 152.4 and d < 457.2 else False for d in df['distance']]
    n = len(df.index)
    pob, hob, dob = df[['pdev ok bo', 'hdev ok bo', 'dist ok bo']].sum() / n * 100
    return df, pob, hob, dob

def plot_and_save(df, saves_dir, flight_description, manoeuvre_description):
    wanted_vars = [
        'pitch deviation', 'heading deviation', 'distance', 'indicated airspeed', 'pitch', 'angle of attack', 'sideslip angle', 'roll',
        'centre stick pitch ratio', 'centre stick roll ratio', 'rudder pedal ratio', 'throttle ratio'
    ]
    df.plot(kind='line', title=manoeuvre_description, y=wanted_vars, subplots=True, figsize=(20, 20))
    plt.savefig(os.path.join(saves_dir, f'{flight_description}.jpg'))

    df = df.round(2)
    df.index = df.index.round(2)
    df.to_csv(os.path.join(saves_dir, f'{flight_description}.csv'))
    return df

def slice_and_dice(df):
    df.drop(columns=[
        'Δt', 
        'sideslip angle', 
        'ideal pitch', 'ideal heading', #'pitch', 'heading', 'roll',
        'aspect angle', 
        # 'pitch rate', 'roll rate',
        'rate of change of indicated airspeed',
        # 'centre stick pitch ratio', 'centre stick roll ratio', 'rudder pedal ratio'
    ], inplace=True)
    df = df[df.index > 4] # the kias dataref stream starts at 0 knots at t = 0, stabilising around t = 4 s
    return df

def generate_feedback(llm_client, df_to_csv, aircraft_type, flight_description, manoeuvre_description, crashed, dir, date_time):
    system_content = f"""You are a flight instructor training new Air Force trainee pilots to visually track enemy aircraft on a {aircraft_type} simulator with a centre stick instead of a yoke. This is only their {flight_description} session flying in a simulator, and they have not flown a real aircraft yet. You can assume that they are unknowledgeable about aviation, their aircraft layout, flight dynamics and basic fighter manoeuvres, likely only knowing about basic flight controls like centre stick and throttle inputs. Hence, you should explain terms likely foreign to trainees. Ensure that your input is precise, succinct and very reliable. If you are unsure of your input, say so. Your input is very important to trainees."""
    user_content_qn = f"""Given the following flight data from an enemy tracking training flight of a pilot in a {aircraft_type}, generate detailed and specific feedback for the trainee pilot. When giving technical explanations, summarize them in plain, actionable language suitable for a beginner trainee. As the syllabus has already been determined, do not suggest training scenarios or self-directed practice. Your feedback should be encouraging and motivational, acknowledging what the pilot did well. The feedback should answer the 3 following questions: 'What are my goals? (keep the response to this question to 25 words) How am I doing? How to improve?'. Include no more than one point per question and keep your response to 200 words.

    {df_to_csv}

    Notes on the data:
    - The enemy aircraft is executing a {manoeuvre_description}.
    - {crashed}
    - Distance is in metres.
    - Indicated airspeed is in knots.
    - Pitch and heading deviations are in degrees and are unavailable to trainees.
        - Positive pitch deviation means the trainee is pointing too high (above the enemy) and should pitch down to re-center the target vertically.
        - Positive heading deviation means the trainee is pointing too far right and should turn left to center the target horizontally.
        - Trainee loses visual contact with the enemy aircraft if the absolute value of pitch deviation > 8° or heading deviation > 30°.
    - Centre stick and rudder pedal ratios represent simulator-derived input intensities for pitch/roll and yaw control, respectively. These values are for analysis only and should not be quoted verbatim in your feedback (e.g., do not say 'rudder pedal ratio'). Instead, describe control behavior in plain language.
    """
    
    messages = [
        {"role": "system", "content": system_content},
        # *chat_history, # could pass in a list of {'role': '...' (e.g., 'assistant'), 'content': '...'} if we wanted the LLM to remember past feedback/parameters
        {"role": "user", "content": user_content_qn}
    ]

    start_time = time.perf_counter()
    response = llm_client.invoke(messages)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time    
    print(f"Response time: {elapsed_time:.2f} seconds")

    write_log(dir, 'messages.txt', f'at {date_time}, messages:\n\n{messages}\n\n\n\n')
    write_log(dir, 'responses.txt', f'at {date_time}, response content:\n\n{response.content}\n\n\n\n')
    write_log(dir, 'time_taken.txt', f'at {date_time}, time taken for response:\n\n{elapsed_time:.2f} s\n\n\n\n')
    return response.content

def suggest_variables(llm_client, feedback, available_vars):
    # could use function/tool calling (available on langchain and in gemini's own API) to get the LLM to suggest variables to plot against time to illustrate the points raised in feedback
    pass

def write_log(dir, filename, content):
    with open(os.path.join(dir, filename), 'a', encoding='utf-8') as f:
        f.write(content)

def format_md(feedback):
    return re.sub(r'(\*\*.+?\*\*)\n', r'\1  \n', feedback) # add 2 whitespaces after the double asterisk the LLM usually gives so markdown gives me a newline

def main():
    date_time = datetime.now()
    str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")
#    saves_dir = f'saves/{str_date_time}/'
    saves_dir = os.path.join(CWD, 'saves', str_date_time)
    os.makedirs(saves_dir)

    obs_client = setup_obs(saves_dir)
    
    llm_client = ChatGoogleGenerativeAI(
        google_api_key=GOOGLE_API_KEY,
        model=MODEL_NAME
    )

    for i in range(10):
        subprocess.run(['start', 'steam://run/2014780'], shell=True)
        
        manoeuvre_no = (8, 4, 1, 2, 3, 4, 5, 6, 7, 5)[i] # 8 spawns my aircraft facing away from the AI aircraft and at 3000 m elevation
        flight_description = ['familiarisation', 'pre-test', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'post-test'][i]
        print(f"\n--- Starting {flight_description} flight ---\n")

        obs_client.set_profile_parameter("Output", "FilenameFormatting", flight_description)

        values, manoeuvre_description, aircraft_type, crashed = communicate_xp(manoeuvre_no, obs_client)

        df, pob, hob, dob = process_dataframe(values)
        df = plot_and_save(df, saves_dir, flight_description, manoeuvre_description)
        if i in (1, 9):
            write_log(saves_dir, 'scores.txt', f'**{flight_description}**:\n\n%time within:\nabs(pitch dev<5deg): {pob}, \nabs(heading dev<5deg): {hob}, \n500ft<distance<1500ft: {dob}\n\n\n\n')
        if i in range(2, 9):
            print(f'Enemy aircraft executed "{manoeuvre_description}"')

            vlc_process = subprocess.Popen([VLC_PATH, '--play-and-exit', os.path.join(saves_dir, f'{flight_description}.mp4')])
            df = slice_and_dice(df)
            df_to_csv = df.to_csv()

            feedback = generate_feedback(llm_client, df_to_csv, aircraft_type, flight_description, manoeuvre_description, crashed, saves_dir, date_time)

            console = Console()
            feedback = format_md(feedback)
            md = Markdown(f"  \n--- Feedback for manoeuvre {i+1} ---  \n" + feedback)
            while vlc_process.poll() is None:
                time.sleep(1)
            console.print(md)

            time.sleep(30)

if __name__ == "__main__":
    main()
