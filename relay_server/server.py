from datetime import datetime
import os
import socket
import pickle
import numpy as np # seems like I need this for one of the variables streamed from my X-Plane plugin
import pandas as pd
import matplotlib.pyplot as plt
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

HOST = "127.0.0.1"
PORT = 6969

values = []

wd = os.path.dirname(os.path.realpath(__file__))
os.chdir(wd)

date_time = datetime.now()
str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")

values_and_plots_path = 'values_and_plots/' + str_date_time + "/"
os.mkdir(values_and_plots_path)

GOOGLE_API_KEY = "AIzaSyDh7u2AuBEfk_O_IuhuA0A2wIw6pXczlfE"
CHAT_HISTORY = []

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        while True:
            data = pickle.loads(conn.recv(1024))
            print(data)
            if data == 'stop':
                break
            values.append(data)

aircraft_type = values.pop(1)
print(f'aircraft type is "{aircraft_type}"')

df = pd.DataFrame(values, columns=('t', 
                                   'manoeuvre', 
                                   'distance', 'aspect angle',
                                   'pitch', 'ideal pitch', 'roll', 'heading', 'ideal heading', 
                                   'angle of attack', 'sideslip angle',
                                   'centre stick pitch ratio', 'centre stick roll ratio', 'rudder pedal ratio', 'throttle ratio', 
                                   'kias', 
                                   'stall warning', 'has crashed'))
df['t'] = df['t'] - df.iloc[26]['t']
df['Δt'] = df['t'].diff()
df= df.set_index('t')
df['pitch dev'] = df['pitch'] - df['ideal pitch']
df['heading deviation'] = df['heading'] - df['ideal heading']
df['heading deviation'] = [hd - 360 if hd > 180 else hd + 360 if hd < -180 else hd for hd in df['heading deviation']]
df['rate of change of distance'] = df['distance'].diff() / df['Δt']
df['rate of change of kias'] = df['kias'].diff() / df['Δt']
#df['pitch rate'] = df['pitch'].diff() / df['Δt']
#df['roll rate'] = df['roll'].diff() / df['Δt']

#df['pitch dev rate'] = df['pitch dev'].diff() / df['Δt']
#df['heading dev rate'] = df['heading dev'].diff() / df['Δt']

df['in front of or behind enemy plane'] = ['behind' if aa < 90 else 'in front' for aa in df['aspect angle']]
df['pitch deviation grade'] = ['visible' if abs(pdev) < 8 else 'lost sight' for pdev in df['pitch dev']]
df['heading deviation grade'] = ['visible' if abs(hdev) < 30 else 'lost sight' for hdev in df['heading dev']]
df.drop(columns=['Δt', 'pitch', 'ideal pitch', 'heading', 'ideal heading', 'aspect angle'], inplace=True)
df = df.iloc[26:-1]

# prob pointless to include rates in wanted_vars in the end cus the kiddos can see trends frm graphs
wanted_vars = ['pitch dev', 'heading dev', 'distance', 'kias', 'pitch', 'angle of attack', 'sideslip angle', 'roll', 'yoke pitch ratio', 'yoke roll ratio', 'throttle ratio']
df.plot(kind='line', y=wanted_vars, subplots=True, figsize=(20, 20))
plt.savefig(values_and_plots_path + 'plot.jpg')

df = df.round(2)
df.index = df.index.round(2)
print(df, df.columns)

df.to_csv(values_and_plots_path + 'values.csv')
df_to_csv = df.to_csv()
print(df_to_csv)
#df_to_dict = df.to_dict()
#print(df_to_dict)

#raise

system_content = f"""You are a flight instructor training new Air Force trainee pilots to track enemy aircraft on a {aircraft_type}. This will likely be the first time they are flying a real plane. You can assume that they are unknowledgeable about aviation and basic fighter manoeuvres and their terminology (like aspect angle), likely only knowing about basic flight controls like centre stick and throttle inputs. Explain terms likely foreign to trainees if necessary. Ensure that your input is precise, succinct and very reliable. If you are unsure of your input, say so. Your input is very important to trainees."""
#ok maybe i can ownself define some lesson objectives given how mine prolly isnt rlly in the faa or dogfighting docs
user_content_qn = f"""Given the following flight data from an enemy tracking training flight of a pilot in a {aircraft_type}, generate detailed and specific feedback for the trainee pilot, telling them how exactly to execute your feedback. As the syllabus has already been determined, do not suggest training scenarios or self-directed practice. Your feedback should be encouraging and motivational, acknowledging what the pilot did well. The feedback should answer the 3 following questions: 'What are my goals? (keep the response to this question to 25 words) How am I doing? How to improve?'. Keep your response to 150 words.

{df_to_csv}
Notes on the data:
- Distance is in metres
- Positive pitch deviation means the trainee is pointing too high/above the enemy and should pitch down to re-center the target vertically. Positive heading deviation means the trainee is pointing too far right and should turn left to center the target horizontally.
"""

llm_client = ChatGoogleGenerativeAI(
    google_api_key=GOOGLE_API_KEY,
    model="gemini-2.5-flash-preview-05-20"
)

messages = [
    {"role": "system", "content": system_content},
    *CHAT_HISTORY,
    {"role": "user", "content": user_content_qn}
]

with open('prompt_characteristics.txt', 'a', encoding='utf-8') as p:
    p.write(f'''at {date_time}, messages:

{messages}



''')


response = llm_client.invoke(messages)

print(response, response.content, sep="\n"*2)

with open('responses.txt', 'a') as r:
    r.write(f'''at {date_time}, response content:
            
{response.content}



''')

raise

user_content_qn = f"""Given the following flight data from an enemy tracking training flight of a pilot in a {aircraft_type}, summarise in 250 words the feedback for the trainee pilot. The summary should be concise and to the point, while still being encouraging and motivational. The summary should answer the 3 following questions: 'What are my goals? How am I doing? How to improve?'"""

messages_to_summarise = [
    {"role": "system", "content": system_content},
    *CHAT_HISTORY,
    {"role": "user", "content": user_content_qn}
]


with open('summary_messages.txt', 'a') as s:
    s.write(f'''at {date_time}, messages:
            
{messages_to_summarise}

''')


summarised_feedback = llm_client.invoke(messages_to_summarise)

print(summarised_feedback, summarised_feedback.content, sep='\n'*2)

with open('summarised_responses.txt', 'a') as s:
    s.write(f'''at {date_time}, response content:
            
{response.content}


''')