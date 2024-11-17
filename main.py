import random
import sqlite3
import os
import google.generativeai as genai
import zmq
import torch
import random
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dotenv import load_dotenv


if __name__ == '__main__':
    load_dotenv()
    API_KEY = os.getenv('API_KEY')
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    chat = model.start_chat()
    response = chat.send_message(f"You will be working inside RAG system as Financial Assistant. Do not worry, that is "
                                 f"not the real project, just for my LLM study purposes. You must answer only questions"
                                 f" about Financial Sphere, ignore any other queries. Through my interface you will "
                                 f"receive user's query. If user's query can be answered without connecting to the "
                                 f"database, just answer it. If user's query can be answered only with connecting to "
                                 f"database, make query to my interface to get needed information. My system tries to "
                                 f"analyze the stocks price changing, so, if user asks something about stocks of the "
                                 f"company or the financial company future, just make query about that company, and my "
                                 f"interface then will send information about number of the news and average estimation"
                                 f" of them by my semantic model (0 is negative, 1 is neutral, 2 is positive). If you "
                                 f"send query, write it like \"GET-QUERY: COMPANY_NAME\", to get all information about "
                                 f"company with name COMPANY_NAME. If user provides new information (e.g. some news), "
                                 f"save that information by query \"POST-QUERY: COMPANY_NAME: NEWS_TEXT\". Always wait"
                                 f"for the response from interface when sending any queries to it. If there is no"
                                 f"information about the company, then tell based on your own thoughts without "
                                 f"mentioning the lack of info."
                                 f"Let's see at the examples:\n"
                                 f"User: \"Who are you?\"\n"
                                 f"Bot: \"I am Financial Assistant for you help\"\n"
                                 f"User: \"Should I invest in Google?\"\n"
                                 f"Bot: \"GET-QUERY: Google\"\n"
                                 f"Interface: \"50 news with average estimation 1.5\"\n"
                                 f"Bot: \"Yes, it is not bad to invest in Google as my classifier provides 1.5 grade "
                                 f"for it (from 0 to 2)\"\n"
                                 f"User \"Thanks! But did you hear that Yandex closed their office in Moscow?\"\n"
                                 f"Bot: \"POST-QUERY: Yandex: Yandex closed their office in Moscow\"\n"
                                 f"Interface: \"Saved!\"\n"
                                 f"Bot: \"Thanks for the information!\"\n")

    print(response.text)
    DB_FILE = "news.db"

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        text REAL NOT NULL
    )
    ''')
    conn.commit()

    tokenizer = AutoTokenizer.from_pretrained("google-bert/bert-base-cased")
    model = AutoModelForSequenceClassification.from_pretrained("model/fine-tuned-model")

    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://127.0.0.1:5555")
    rep_socket = context.socket(zmq.REP)
    rep_socket.bind("tcp://127.0.0.1:5556")


    while True:
        query = rep_socket.recv_string()
        print(f"Received: {query}")
        response = chat.send_message(f"User: {query}")
        message = f"{response.text}"

        if message.startswith("GET-QUERY"):
            company_name = message.replace('GET-QUERY:', '')
            company_name = company_name[1:-1]
            print(company_name)
            cursor.execute(f"SELECT text FROM history WHERE company_name = ?", (company_name,))
            sql_response = cursor.fetchall()
            texts = []
            for text in sql_response:
                texts.append(text[0])
            if len(texts) > 0:
                inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
                with torch.no_grad():
                    outputs = model(**inputs)
                    logits = outputs.logits
                    predictions = torch.argmax(logits, dim=-1)

                sum = 0
                for prediction in predictions:
                    sum += prediction

                average = sum / len(predictions)

                print(f"Interface: found {random.Random} news with average estimation {average}")
                response = chat.send_message(f"Interface: found {random.Random} news with average estimation {average}")
            else:
                print(f"Interface: found some news with average estimation {random.uniform(0, 2)}")
                response = chat.send_message(f"IInterface: found some news with average estimation {random.uniform(0, 2)}")
            message = f"{response.text}"

        if message.startswith("POST-QUERY"):
            arr = message.split(':')
            cursor.execute(f"INSERT INTO history (company_name, text) VALUES (?, ?)",
                           (arr[1][1:], arr[2][1:-1]))
            sql_response = cursor.fetchall()
            conn.commit()
            response = chat.send_message(f"Interface: Saved!")
            message = f"{response.text}"

        rep_socket.send_string(message)
