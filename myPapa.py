from flask import Flask, request, jsonify
import requests
import json
import random
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from jisho_api.tokenize import Tokens
from jisho_api.word import Word
import os
import openai
from openai.error import RateLimitError
import re
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


PAPAGO_CLIENT_ID = os.environ.get('PAPAGO_CLIENT_ID')
PAPAGO_CLIENT_SECRET = os.environ.get('PAPAGO_CLIENT_SECRET')
WANIKANI_API_TOKEN = os.environ.get('WANIKANI_API_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY



app = Flask(__name__)


CORS(app, resources={r"/*": {"origins": [
    "http://tensaihonyaku.com",
    "http://www.tensaihonyaku.com",
    "https://tensaihonyaku.com",
    "https://www.tensaihonyaku.com",
    "https://tensaihonyaku.wl.r.appspot.com",
]}})

# CORS(app, resources={r"/generation*": {"origins": "http://localhost:3000"}})







@app.route('/', methods=['GET'])
def main():
    return """
    <!doctype html>
    <html>
        <head>
            <title>My Homepage</title>
        </head>
        <body>
            <h1>Hello World!</h1>
        </body>
    </html>
    """








@app.route('/generation', methods=['GET'])
# @cross_origin()
def generation():


    difficultyRange = request.args.getlist('difficultyRange[]')

    # print('difficultyRange: ', difficultyRange)


    difficultyRangeStart = int(difficultyRange[0])
    difficultyRangeEnd =  int(difficultyRange[1])


    queryRange = 9167 - 2467 #6700


    for _ in range(58):

        ranNum = random.randint(2467 + ((queryRange//100) * difficultyRangeStart), 2467 + ((queryRange//100) * difficultyRangeEnd))

        WANIKANI_URL = 'https://api.wanikani.com/v2/subjects/' + str(ranNum)
        requestHeaders = { 'Authorization': 'Bearer ' + WANIKANI_API_TOKEN}


        body = requests.get(WANIKANI_URL, headers=requestHeaders)
 

        res = json.loads(body.text)

        resObject = res['object']


        if resObject == 'vocabulary':

            sentencesLen = len(res['data']['context_sentences'])

            if sentencesLen > 0:

                # print('sentencesLen: ', sentencesLen)

                result = jsonify(res['data']['context_sentences'][random.randint(0, sentencesLen-1)])

                return (result, 200)

    return ({"error": "Please try again after one minute."}, 404) #if all 58 iterations fail








@app.route('/tokenize', methods=['POST'])
def tokenize():
    content = request.get_json()
    source = content['textToTranslate']
    # print("SOURCE", source)


    r = Tokens.request(source)
    
    numOfTokens = len(r.data)
    tokenizedArray = []
    for i in range(numOfTokens):
        word = r.data[i].token
        tokenizedArray.append(word)

    content["tokenizedArray"] = tokenizedArray

    # print("TOKENIZED ARRAY", content["tokenizedArray"])

    return (jsonify(content), 201)





def extract_json(s):
    match = re.search(r'\{.*\}', s)
    if match:
        return match.group()
    else:
        return ''



@app.route('/reading', methods=['POST'])
def reading():

    content = request.get_json()

    word = content['wordClicked']
    context = content['textToTranslate']

    messages = [
        {"role": "system", "content": """You are an expert at reading Japanese. Your role is to only give me the Furigana reading and the meaning of the Japanese word that I will provide."""},
        {"role": "user", "content": """How do you read the word""" + word + """in Japanese? 
        Strictly return in your response only a JSON object in a format like this: {”食べる": "たべる - to eat"}. Do not add anything before or after the curly braces!
        And if the word I provided are all in Hiragana, then just return "reading - meaning" for the furigana value like this: {”です": "です - to be"}
        And if you don't know how to provide the furigana reading, then also just return the furigana value like this: {”。": "。 - period"}
        And if the word is conjugated like "飲み過ぎちゃった", then try your best and return it like this: {”飲み過ぎちゃった": "のみすぎちゃった - drank too much"} instead of {'飲み過ぎちゃった': 'のみすぎる - to drink too much'}.
        Pay attention to the context when generating the meaning. If there are several meanings, then just return the most appropriate meaning depending on the context.
        For example, for the sentence "やばい、これ美味しい！", the meaning should be "amazing" and not "dangerous" because the context is positive.
        Refer to this context: """ + context },
    ]



    def make_request_with_retry():
        max_retries = 5
        base_wait_time = 1 # 1 second

        for retry_attempt in range(max_retries):
            try:
                # Replace this line with your actual API call
                response = openai.ChatCompletion.create(
                    messages=messages,
                    model="gpt-3.5-turbo",
                    max_tokens=1500,
                    temperature=0.9,
                )
                return response
            except RateLimitError as e:
                wait_time = base_wait_time * (2 ** retry_attempt)
                print(f"RateLimitError encountered. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
        else:
            print("Max retries reached. The request has failed.")
            return None

    # start = time.time()
    response = make_request_with_retry()
    # end = time.time()
    # total_time = end - start
    # print(f"LOADING TIME: {total_time}")

    if response:

        # print("Raw Response: ", response['choices'][0]['message']['content'])

        s = response['choices'][0]['message']['content']
        cleaned_s = extract_json(s)

        obj_response = json.loads(cleaned_s)
        # print("obj_response", obj_response)
        # print("whole content: ", content)

        content["reading"] = obj_response
        return (jsonify(content), 201)








@app.route('/hint', methods=['POST'])
def hint():

    content = request.get_json()


    messages = [
        {"role": "system", "content": """You are a helpful tutor trying to help me who's trying to practice translating Japanese sentences into English. You will give me hints but will not give out the whole answer. Keep giving hints until I finish my attempt sentence."""},
        {"role": "user", "content": """
            Using the source text and my incomplete attempt, help me and give me some advice on what word to write next. Write the Japanese word I'm missing which is equivalent to the English word not present in my attempt.
            Source text: 最近、学校では、英語の授業で文法を学んでいるけど、落ち込んでいる時もあって、それを乗り越えるために、今日は友達と一緒に日本語を学ぶことにしました。
            My attempt: Recently we've been learning English grammar at school, but 
            Hint: """},
        {"role": "assistant", "content": """the missing word is a verb in past tense that means "there are times when I feel down"."""},
        {"role": "user", "content": """
            I need another hint.
            My attempt: Recently we've been learning English grammar at school, but there are times when I feel down
            Hint: """},
        {"role": "assistant", "content": """The missing word is a conjunction that means "but"."""},
        {"role": "user", "content": """
            I need another hint.
            My attempt: Recently we've been learning English grammar at school, but there are times when I feel down but
            Hint: """},
        {"role": "assistant", "content": """The missing word is a phrase that means "in order to overcome that"."""},
        {"role": "user", "content": """
            I need another hint.
            My attempt: Recently we've been learning English grammar at school, but there are times when I feel down but in order to overcome that
            Hint: """},
        {"role": "assistant", "content": """The missing word is a phrase that means "The missing word is a phrase that means "today, I decided to study Japanese together with a friend"."""},
        {"role": "user", "content": """
            I need another hint.
            My attempt: Recently we've been learning English grammar at school, but there are times when I feel down but in order to overcome that today, I decided to study Japanese together with a friend
            Hint: """},
        {"role": "assistant", "content": """The missing word is a phrase that means "Your attempt looks complete. Good job!"""},
        {"role": "user", "content": """Okay here's a new one."""},
        {"role": "assistant", "content": """Sure, I'm ready to help. Please provide me with the source text and your incomplete attempt."""},
        {"role": "user", "content": """Source text: {} \n\n
            Incomplete attempt: {} \n\n
            Hint: """.format(content['textToTranslate'], content['translatedText'])}
    ]


    # start = time.time()

    response = openai.ChatCompletion.create(
        messages=messages,
        model="gpt-4o",
        max_tokens=1500,
    )


    # end = time.time()

    # total_time = end - start

    # print(f"HINT LOADING TIME: {total_time}")


    content['hint'] = response['choices'][0]['message']['content']
    # print(content['hint'])
    return (jsonify(content), 201)








@app.route('/analysis', methods=['POST'])
def analysis():
    try:

        content = request.get_json()


        openai_prompt = """I'm trying to practice translating Japanese sentences into English. 
                            Using the source text, rate and give me an analysis and evaluation on my translation attempt. 
                            Be critical of the nuances of the Japanese words and the English words I used. \n\n
                            Source text: {}\n\n
                            My attempt: {}\n\n
                            Start your response with 'AI Analysis: '""".format(content['textToTranslate'], content['translatedText'])

        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert translator."},
                {"role": "user", "content": openai_prompt}
            ],
            max_tokens=1000,
            temperature=0.5
        )

        # print('response: ', response)





        content['attemptAnalysis'] = response['choices'][0]['message']['content']

        return (jsonify(content), 201)

    except Exception as e:
        return jsonify({'error': str(e)})







@app.route('/translation', methods=['POST'])
def translation():

    try:

        content = request.get_json()
 
        messages = [
            {"role": "system", "content": """You are an expert translator from Japanese to English."""},
            {"role": "user", "content": """
                Using the Japanese source text, give me an accurate English translation of it. Your response should only contain the translated text.
                Here's the Japanese text to be translated into English: {}""".format(content['textToTranslate'])}
        ]



        response = openai.ChatCompletion.create(
            messages=messages,
            model="gpt-4o",
            max_tokens=1500,
        )

        print('RESPONSE: ', response['choices'][0]['message']['content'])
        print('CONTENT: ', content)

        content["suggestedTranslation"] = response['choices'][0]['message']['content']

        suggestedTranslationBoolsArray = []

        suggestedTranslationArray = content['suggestedTranslation'].split() if content['generatedTextEngVerFromWanikani'] == '' else content['generatedTextEngVerFromWanikani'].split()
        translatedTextArray = content['translatedText'].split()

        for elem in suggestedTranslationArray:
            if elem in translatedTextArray:
                suggestedTranslationBoolsArray.append(True)
            else:
                suggestedTranslationBoolsArray.append(False)

        content['suggestedTranslationBoolsArray'] = suggestedTranslationBoolsArray
        content['translatedTextArray'] = translatedTextArray
        content['suggestedTranslationArray'] = suggestedTranslationArray

        print('CONTENT: ', content)

        return (jsonify(content), 201)


    except Exception as e:
        return jsonify({'error': str(e)})


    # PAPAGO_API_URL = 'https://openapi.naver.com/v1/papago/n2mt'
    # DEFAULT_CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'
    # SOURCE_LANG = 'ja'
    # TARGET_LANG = 'en'

    # content = request.get_json()
    # # print(f"My Data: {content}")

    # payload = {
    #     'text': content['textToTranslate'], 
    #     'source': SOURCE_LANG, 
    #     'target': TARGET_LANG
    # }

    # headers = {
    #     'X-Naver-Client-Id': PAPAGO_CLIENT_ID,
    #     'X-Naver-Client-Secret': PAPAGO_CLIENT_SECRET,
    #     'Content-Type': DEFAULT_CONTENT_TYPE
    # }

    # body = requests.post(PAPAGO_API_URL, headers=headers, data=payload)
    # print('body: ', body)


    # data = json.loads(body.text)
    # content["suggestedTranslationFromPapago"] = data['message']['result']['translatedText']
    # content["suggestedTranslation"] = data['message']['result']['translatedText']


    # suggestedTranslationBoolsArray = []

    # suggestedTranslationArray = content['suggestedTranslation'].split() if content['generatedTextEngVerFromWanikani'] == '' else content['generatedTextEngVerFromWanikani'].split()
    # translatedTextArray = content['translatedText'].split()

    # for elem in suggestedTranslationArray:
    #     if elem in translatedTextArray:
    #         suggestedTranslationBoolsArray.append(True)
    #     else:
    #         suggestedTranslationBoolsArray.append(False)

    # content['suggestedTranslationBoolsArray'] = suggestedTranslationBoolsArray
    # content['translatedTextArray'] = translatedTextArray
    # content['suggestedTranslationArray'] = suggestedTranslationArray


    # return (jsonify(content), 201)







if __name__ == "__main__":
    app.run(debug=True)
    # app.run(host='0.0.0.0', port=8765)