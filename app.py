from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import weaviate
import openai
import csv
import gspread
from google.oauth2.service_account import Credentials
import json 
import io 
import re
import threading

app = Flask(__name__)

key = "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"
lm_client = openai.OpenAI(api_key=key)
credentials_path = 'credentials.json'
response = "Done."
app.secret_key = 'your_very_secret_key_here'

def add_row_to_sheet(data, sheet_id):
    creds = Credentials.from_service_account_file(credentials_path, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    client = gspread.authorize(creds)

    try:
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)
        print(data)
        worksheet.append_row(data)
        print("Row added successfully!")
    except Exception as e:
        print("Error: ", e)


layer_1 = weaviate.Client(
    url="https://job1-5ctne2bv.weaviate.network",
    # auth_client_secret=weaviate.AuthApiKey(api_key="vvZhMKvXbg2iETqRZ1EyLJ8302jWE436t2oG"),
    additional_headers={"X-OpenAI-Api-Key": "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"}
)

name_1 = 'job1'

layer_2 = weaviate.Client(
    url="https://job2-ytnx25w3.weaviate.network",
    # auth_client_secret=weaviate.AuthApiKey(api_key="vvZhMKvXbg2iETqRZ1EyLJ8302jWE436t2oG"),
    additional_headers={"X-OpenAI-Api-Key": "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"}
)

name_2 = 'job2'

@app.route('/')
def index():
    return render_template('viz.html')

custom_functions = [
    {
        'name': 'return_response',
        'description': 'Function to be used to return the response to the question, and a boolean value indicating if the information given was suffieicnet to generate the entire answer.',
        'parameters': {
            'type': 'object',
            'properties': {
                'item_list': {
                    'type': 'array',
                    'description': 'List of chunk ids. ONLY the ones used to generate the response to the question being asked. return the id only if the info was used in the response. think carefully.',
                    'items': {
                        'type': 'integer'
                    }
                },
                'response': {
                    'type': 'string',
                    'description': "This should be the answer that was generated from the context, given the question"
                },
                'sufficient': {
                    'type': 'boolean',
                    'description': "This should represent wether the information present in the context was sufficent to answer the question. Return True is it was, else False."
                },
            },
            "required": ["response", "sufficient", "item_list"]
        }
    }
]

custom_functions_1 = [
    {
        'name': 'return_response',
        'description': 'Function to be used to return the response to the question, and a boolean value indicating if the information given was suffieicnet to generate the entire answer.',
        'parameters': {
            'type': 'object',
            'properties': {
                'response': {
                    'type': 'boolean',
                    'description': "This should be the answer that was generated from the context, given the question"
                },
                'sufficient': {
                    'type': 'boolean',
                    'description': "This should represent wether the information present in the context was sufficent to answer the question. Return True is it was, else False."
                },
            },
            "required": ["response", "sufficient"]
        }
    }
]

import time

def ask_gpt(question, context, gpt, addition, language):
    user_message = "Question: \n\n" + question + "\n\n\nContext: \n\n" + context
    # print(user_message)
    system_message = "You will be given context from several pdfs, this context is from several chunks, rettrived from a vector DB. each chunk will have a chunk id above it. You will also be given a question. Formulate an answer in {}, ONLY using the context, and nothing else. provide in-text citations within square brackets at the end of each sentence, right after each fullstop. The citation number represents the chunk id that was used to generate that sentence. Do Not bunch multiple citations in one bracket. Uee seperate brackets for each digit. {} Return the response along with a boolean value indicating if the information from the context was enough to answer the question. Return true if it was, False if it wasnt. Return the response, which is th answer to the question asked in {}".format(language, addition, language)
    print("\n\n",system_message)
    msg = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_message}
    ]

    def call_api():
        nonlocal args
        response = lm_client.chat.completions.create(
        model=gpt,
        messages=msg, max_tokens=4000, temperature=0.0,  functions=custom_functions, function_call='auto')
        args = response

    args = None
    thread = threading.Thread(target=call_api)
    start = time.time()
    thread.start()
    thread.join(timeout=160)

    if thread.is_alive():
        print(time.time()-start)
        return "Timeout. Pranav has set level timeout to 160  seconds. The timeout error usually happens when the API has been used multiple times.", False, [0,1]
    
    response = args
    reply = response.choices[0].message.content
    item_list = []
    sufficient = False
    print("Reply: ",response)
    if reply is None:
       reply = json.loads(response.choices[0].message.function_call.arguments)["response"]
       sufficient = json.loads(response.choices[0].message.function_call.arguments)["sufficient"]
       item_list = json.loads(response.choices[0].message.function_call.arguments)["sufficient"]
    print("Reply: ",reply)
    
    return reply, sufficient, item_list


def ask_gpt_fast(question, context, addition, language):
    user_message = "Question: \n\n" + question + "\n\n\nContext: \n\n" + context
    system_message = "You will be given context from several pdfs, this context is from several chunks, rettrived from a vector DB. each chunk will have a chunk id above it. You will also be given a question. Formulate an answer in {}, ONLY using the context, and nothing else. {} Return the text response and a boolean value indicating if the information from the context was enough to answer the question. Return true if it was, False if it wasnt. Return the response, which is the answer to the question asked in {}. If the answer cannot be formulated using the context, say that it is not possile. Remeber, provide the response in {} language only".format(language, addition, language, language)

    msg = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_message}
    ]
    print(custom_functions_1)
    response = lm_client.chat.completions.create(
        model="gpt-3.5-turbo-16k",
        messages=msg, max_tokens=4000, temperature=0.0,  functions=custom_functions_1, function_call='auto')
    
    print(response)
    reply = response.choices[0].message.content
    sufficient = False
    if reply is None:
        reply = json.loads(response.choices[0].message.function_call.arguments)["response"]
        sufficient = json.loads(response.choices[0].message.function_call.arguments)["sufficient"]
    return reply, sufficient

def ask_gpt_generic(question, language):
    user_message = question
    system_message = "Answer the question. Return the response in {}".format(language) + session['generic_system_msg_level_3']
    msg = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_message}
    ]

    response = lm_client.chat.completions.create(
        model="gpt-3.5-turbo-16k",
        messages=msg, max_tokens=4000, temperature=0.0)
    reply = response.choices[0].message.content
    return reply


def qdb(query, db_client, name, cname):
    context = None
    try:
        limit = 10
        res = db_client.query.get(
        name,
        ["text", "metadata"])\
        .with_near_text({"concepts": query})\
        .with_limit(limit)\
        .do()
        context = "" 
        metadata = []
        chunk_id = 0
        # print(res)
        for i in range(limit):
            context += "Chunk ID: " + str(chunk_id) + "\n"
            context += res['data']['Get'][cname][i]['text'] + "\n\n"
            metadata.append(res['data']['Get'][cname][i]['metadata'])
            chunk_id += 1
    except Exception as e:
        print("Exception, dude.")
        print(e)
    return context, metadata

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    level = data['level']
    feedback = data['feedback']
    response = data['response']
    print(feedback, response)
    add_row_to_sheet([feedback,session['transcription'], response], "1OvOj468hgwhjrBFqWrHrZtSirrodrUEejBUUr37by_Y")
    return jsonify({'status': 'success'})

def transcribe(audio_file):
    response = lm_client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    transcription = response.text
    print(transcription)

    return transcription

class FileWithNames(io.BytesIO):
    name = "audio.wav"

def process_response(input_string, replacements):
    def replacement(match):
        index = int(match.group(1))
        return f'[{replacements[index]}]' if index < len(replacements) else match.group(0)

    try:
        return re.sub(r'\[(\d+)\]', replacement, input_string)
    except:
        return input_string
     
   

@app.route('/level1', methods=['POST'])
def level1():
    session['transcription'] = request.form['query']
    session['generic_system_msg_level_1'] = request.form['lmprompt1']
    session['language'] = request.form['lang']
    print(type(session['language']), session['language'])
    session['language'] = 'english' if session['language'] == "" else session['language']
    session['fast'] = request.form['fast']

    # print("\n\n\nFast: ",type(session['fast']), "\n\n\n")
    
    # return jsonify({'response': "response", 'sufficient': False})

    audio_file = request.files['audio'] if 'audio' in request.files else None
    
    try:
        if audio_file:
            audio_bytes = audio_file.read()
            audio_file = FileWithNames(audio_bytes)
            session['transcription'] = transcribe(audio_file)
    except Exception as e:
        print(e)    

    add_row_to_sheet(["Question: ", session['generic_system_msg_level_1']], "1OvOj468hgwhjrBFqWrHrZtSirrodrUEejBUUr37by_Y")
    context, metadata = qdb(session['transcription'], layer_1, "job3", 'Job3')
    print(context)
    
    if session['fast'] == 'false':
        response, sufficient, _ = ask_gpt(session['transcription'], context, 'gpt-4', session['generic_system_msg_level_1'], session['language'])
    else:
        response, sufficient = ask_gpt_fast(session['transcription'], context, session['generic_system_msg_level_1'], session['language'])

    response = process_response(response, metadata)
    print("\n\n\n\nDone\n\n\n\n")
    print(response)

    return jsonify({'response': response, 'sufficient': False})

@app.route('/level2', methods=['POST'])
def level2():
    print("Level2......\n")
    session['generic_system_msg_level_2'] = request.form['lmprompt2']
    audio_file = request.files['audio'] if 'audio' in request.files else None
    context, metadata = qdb(session['transcription'], layer_2, name_2, 'Job2')
    # return jsonify({'response': "response", 'sufficient': False})
    if session['fast'] == 'false':
        response, sufficient, _ = ask_gpt(session['transcription'], context, 'gpt-4', session['generic_system_msg_level_2'], session['language'])
    else:
        # response, sufficient = ask_gpt_fast(session['transcription'], context, session['generic_system_msg_level_2'], session['language'])
        response, sufficient = ask_gpt_fast(session['transcription'], context, session['generic_system_msg_level_2'], session['language'])

    
    print(response)
    response = process_response(response, metadata)
    return jsonify({'response': response, 'sufficient': False})

@app.route('/level3', methods=['POST'])
def level3():
    print("Level  3......\n")
    session['generic_system_msg_level_3'] = request.form['lmprompt3']
    response = ask_gpt_generic(session['transcription'], session['language'])
    return jsonify({'response': response, 'sufficient': True})

@app.route('/visualize', methods=['GET'])
def visualize():
    query = request.args.get('query', '')
    data = generate_data(query)
    return render_template('viz.html', query=query, data=data)

if __name__ == '__main__':
    app.run(debug=True)
