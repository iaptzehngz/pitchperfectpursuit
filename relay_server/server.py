import time
from datetime import datetime
import os
import subprocess
import psutil
import zmq
import obsws_python as obs # https://github.com/aatikturk/obsws-python
import numpy
import pandas as pd
import matplotlib.pyplot as plt
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from rich.console import Console
from rich.markdown import Markdown
import re

HOST = "127.0.0.1"
PORT_STREAM = 5555
PORT_MANOEUVRE = 6666

MODEL_NAME = "gemini-2.5-flash-preview-05-20"
GOOGLE_API_KEY = "AIzaSyDh7u2AuBEfk_O_IuhuA0A2wIw6pXczlfE"

OBS_PATH = "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"
RECORDING_DIR = os.path.dirname(os.path.abspath(__file__)) # path to directory this file is in
RECORDING_NAME = "I love DSTA"
RECORDING_PATH = os.path.join(RECORDING_DIR, RECORDING_NAME + '.mp4')

VLC_PATH = "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"

def setup_obs():
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
    obs_client.set_record_directory(RECORDING_DIR)
    # obs_client.set_profile_parameter("AdvOut", 'FFFilePath', RECORDING_DIR) # if using advanced recording settings in OBS studio
    obs_client.set_profile_parameter("Output", "FilenameFormatting", RECORDING_NAME)
    obs_client.set_profile_parameter("Output", 'OverwriteIfExists', 'true')
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
    df = pd.DataFrame(values)
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
    df['pitch deviation grade'] = ['visible' if abs(pdev) < 8 else 'lost sight' for pdev in df['pitch deviation']]
    df['heading deviation grade'] = ['visible' if abs(hdev) < 30 else 'lost sight' for hdev in df['heading deviation']]
    df = df.iloc[:-1]
    return df

def plot_and_save(df, output_dir, manoeuvre_description):
    wanted_vars = [
        'pitch deviation', 'heading deviation', 'distance', 'indicated airspeed', 'pitch', 'angle of attack', 'sideslip angle', 'roll',
        'centre stick pitch ratio', 'centre stick roll ratio', 'rudder pedal ratio', 'throttle ratio'
    ]
    df.plot(kind='line', title=manoeuvre_description, y=wanted_vars, subplots=True, figsize=(20, 20))
    plt.savefig(os.path.join(output_dir, 'plot.jpg'))

    df = df.round(2)
    df.index = df.index.round(2)
    df.to_csv(os.path.join(output_dir, 'values.csv'))
    print(df, df.columns)
    return df

def drop_unneeded_columns(df):
    df.drop(columns=[
        'Δt', 
        'sideslip angle', 
        'ideal pitch', 'ideal heading', #'pitch', 'heading', 'roll',
        'aspect angle', 
        # 'pitch rate', 'roll rate',
        'rate of change of indicated airspeed',
        # 'centre stick pitch ratio', 'centre stick roll ratio', 'rudder pedal ratio',
        'pitch deviation grade', 'heading deviation grade'
    ], inplace=True)
    return df

def generate_feedback(llm_client, df_to_csv, aircraft_type, i, manoeuvre_description, crashed, date_time):
    numbering = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']
    number = numbering[i]
    print(f'number is {number}')
    system_content = f"""You are a flight instructor training new Air Force trainee pilots to track enemy aircraft on a {aircraft_type} simulator with a centre stick instead of a yoke. This will be the {number} time they are flying a real plane. You can assume that they are unknowledgeable about aviation and basic fighter manoeuvres and their terminology, likely only knowing about basic flight controls like centre stick and throttle inputs. Explain terms likely foreign to trainees if necessary. Ensure that your input is precise, succinct and very reliable. If you are unsure of your input, say so. Your input is very important to trainees."""
    user_content_qn = f"""Given the following flight data from an enemy tracking training flight of a pilot in a {aircraft_type}, generate detailed and specific feedback for the trainee pilot, telling them how exactly to execute your feedback. As the syllabus has already been determined, do not suggest training scenarios or self-directed practice. Your feedback should be encouraging and motivational, acknowledging what the pilot did well. The feedback should answer the 3 following questions: 'What are my goals? (keep the response to this question to 25 words) How am I doing? How to improve?'. Include no more than one point per question and keep your response to 200 words.

{df_to_csv}
Notes on the data:
- The enemy aircraft is executing a {manoeuvre_description}.
- {crashed}
- Distance is in metres.
- Indicated airspeed is in knots.
- Pitch and heading deviations are in degrees and are unavailable to trainees.
- Positive pitch deviation means the trainee is pointing too high/above the enemy and should pitch down to re-center the target vertically. Positive heading deviation means the trainee is pointing too far right and should turn left to center the target horizontally.
- Trainee would lose sight of the enemy plane if the absolute value of the pitch deviation is greater than 8 degrees and the absolute value of the heading deviation is greater than 30 degrees.
"""
    
    messages = [
        {"role": "system", "content": system_content},
        # *chat_history, # could pass in a list of {'role': '...' (e.g., 'assistant'), 'content': '...'} if we wanted the LLM to remember past feedback/parameters
        {"role": "user", "content": user_content_qn}
    ]
    with open('prompt_characteristics.txt', 'a', encoding='utf-8') as p:
        p.write(f'''at {date_time}, messages:

{messages}



''')
    start_time = time.perf_counter()
    response = llm_client.invoke(messages)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    print(response)
    
    with open('responses.txt', 'a') as r:
        r.write(f'''at {date_time}, response content:
            
{response.content}



''')
    print(f"Response time: {elapsed_time:.2f} seconds")
    with open('time_taken.txt', 'a') as t:
        t.write(f'''at {date_time}, time taken for response: 
            
{elapsed_time:.2f} s



''')
    return response.content

def suggest_variables(llm_client, feedback, available_vars):
    # could use function/tool calling (available on langchain and in gemini's own API) to get the LLM to suggest variables to plot against time to illustrate the points raised in feedback
    pass

def main():
    obs_client = setup_obs()

    date_time = datetime.now()
    str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")
    intermediate_dir = f'values_and_plots/{str_date_time}/'
    os.mkdir(intermediate_dir)
    
    llm_client = ChatGoogleGenerativeAI(
        google_api_key=GOOGLE_API_KEY,
        model=MODEL_NAME
    )

    for i in range(7):  # For 1 familiarisation, 1 pre-test, 7 manoeuvres and 1 post-test
        print(f"\n--- Starting manoeuvre {i+1} ---\n")

        subprocess.run(['start', 'steam://run/2014780'], shell=True)

        output_dir = os.path.join(intermediate_dir, f'{i}')
        os.mkdir(output_dir)

        values, manoeuvre_description, aircraft_type, crashed = communicate_xp(i, obs_client)
        print(f'aircraft type is "{aircraft_type}"')
        print(f'manoeuvre description is "{manoeuvre_description}"')

        vlc_process = subprocess.Popen([VLC_PATH, '--play-and-exit', RECORDING_PATH])

        df = process_dataframe(values)
        df = plot_and_save(df, output_dir, manoeuvre_description)
        df = drop_unneeded_columns(df)
        df_to_csv = df.to_csv()

        feedback = generate_feedback(
            llm_client, df_to_csv, aircraft_type, i, manoeuvre_description, crashed, date_time
        )

        console = Console()
        feedback = re.sub(r'(\*\*.+?\*\*)\n', r'\1  \n', feedback) # add 2 whitespaces after the double asterisk the LLM usually gives so markdown gives me a newline
        md = Markdown(f"  \n--- Feedback for manoeuvre {i+1} ---  \n" + feedback)
        while vlc_process.poll() is None:
            time.sleep(1)
        console.print(md)
        time.sleep(30)

if __name__ == "__main__":
    main()