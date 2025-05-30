import pandas as pd
import matplotlib.pyplot as plt
import os
import time
from datetime import datetime
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

GOOGLE_API_KEY = "AIzaSyDh7u2AuBEfk_O_IuhuA0A2wIw6pXczlfE"
CHAT_HISTORY = []

date_time = datetime.now()
str_date_time = date_time.strftime("%d-%m-%Y %H%M%S")
wd = os.path.dirname(os.path.realpath(__file__))
os.chdir(wd)

aircraft_type = 'Cessna 172 SP Skyhawk - 180HP - G1000'

df = pd.read_csv('values.csv', index_col=0)
df['rate of change of kias'] = df['kias'].diff() / df['Δt']
df['distance'] = df['distance'].str[:-17]

#df['pitch deviation grade'] = ['within view' if abs(pd) < 8 else 'lost sight, above me' if pd > for pd in df['pitch deviation']]
#df['heading deviation grade'] = 

df.drop(columns=['Δt', 
                 'ideal pitch', 'ideal heading', 
                 'pitch', 'heading', 'roll', 
#                 'manoeuvre',
                 'aspect angle', 'sideslip angle', 
#                 'centre stick roll ratio', 'centre stick pitch ratio', 
                 'pitch deviation grade', 'heading deviation grade'
                 ], inplace=True)
df=df.iloc[::3]
print(df.head(), df.columns, sep='\n'*2)

df_to_csv = df.to_csv()

system_content = f"""You are a flight instructor training new Air Force trainee pilots to track enemy aircraft on a {aircraft_type} simulator with a centre stick instead of a yoke. This will likely be the first time they are flying a real plane. You can assume that they are unknowledgeable about aviation and basic fighter manoeuvres and their terminology, likely only knowing about basic flight controls like centre stick and throttle inputs. Explain terms likely foreign to trainees if necessary. Ensure that your input is precise, succinct and very reliable. If you are unsure of your input, say so. Your input is very important to trainees."""
user_content_qn = f"""Given the following flight data from an enemy tracking training flight of a pilot in a {aircraft_type}, generate detailed and specific feedback for the trainee pilot, telling them how exactly to execute your feedback. As the syllabus has already been determined, do not suggest training scenarios or self-directed practice. Your feedback should be encouraging and motivational, acknowledging what the pilot did well. The feedback should answer the 3 following questions: 'What are my goals? (keep the response to this question to 25 words) How am I doing? How to improve?'. Include no more than one point per question and keep your response to 200 words.

{df_to_csv}
Notes on the data:
- Distance is in metres
- Pitch and heading deviations are in degrees and are for you to assess the trainee's performance in tracking the enemy aircraft and are unavailable to trainees.
- Positive pitch deviation means the trainee is pointing too high/above the enemy and should pitch down to re-center the target vertically. Positive heading deviation means the trainee is pointing too far right and should turn left to center the target horizontally.
- Trainee would lose sight of the enemy plane if the absolute value of the pitch deviation is greater than 8 degrees and the absolute value of the heading deviation is greater than 30 degrees.
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

start_time = time.perf_counter()
response = llm_client.invoke(messages)
end_time = time.perf_counter()
elapsed_time = end_time - start_time

print(response, response.content, sep="\n"*2)

with open('responses.txt', 'a') as r:
    r.write(f'''at {date_time}, response content:
            
{response.content}



''')
    
print(f"Response time: {elapsed_time:.2f} seconds")

with open('time_taken.txt', 'a') as t:
    t.write(f'''at {date_time}, time taken for response: 
            
{elapsed_time:.2f} s



''')