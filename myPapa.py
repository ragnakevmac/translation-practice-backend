from flask import Flask, request, jsonify
import requests
import json
import random
import time
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from jisho_api.tokenize import Tokens
from jisho_api.word import Word
import os
import openai
from openai.error import RateLimitError
import re
from credentials import (
    PAPAGO_CLIENT_ID, 
    PAPAGO_CLIENT_SECRET, 
    WANIKANI_API_TOKEN,
    OPENAI_API_KEY
)
openai.api_key = OPENAI_API_KEY


app = Flask(__name__)


@app.route('/tokenize', methods=['POST'])
def tokenize():
    content = request.get_json()
    source = content['textToTranslate']
    print("SOURCE", source)


    r = Tokens.request(source)
    
    numOfTokens = len(r.data)
    tokenizedArray = []
    for i in range(numOfTokens):
        word = r.data[i].token
        tokenizedArray.append(word)

    content["tokenizedArray"] = tokenizedArray

    print("TOKENIZED ARRAY", content["tokenizedArray"])

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

    # messages = [
    #     {"role": "system", "content": """You are an expert at reading Japanese. Your role is to only give me the Furigana reading of the Japanese word that I will provide."""},
    #     {"role": "user", "content": """How do you read the word""" + word + """in Japanese? 
    #     Strictly return in your response only a JSON object in a format like this: {”食べる": "たべる - to eat"}
    #     And if the word I provided are all in Hiragana, then just return "reading - meaning" for the furigana value like this: {”です": "です - to be"}
    #     And if you don't know how to provide the furigana reading, then just return an empty string for the furigana value like this: {”。": "。 - period"}
    #     Pay attention to the context when generating the meaning. If there are severl meanings, then just return the most appropriate meaning depending on the context.
    #     For example, for the sentence "やばい、これ美味しい！", the meaning should be "amazing" and not "dangerous" because the context is positive.
    #     Context:""" + context },
    # ]



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

    start = time.time()
    response = make_request_with_retry()
    end = time.time()
    total_time = end - start
    print(f"LOADING TIME: {total_time}")

    if response:

        print("Raw Response: ", response['choices'][0]['message']['content'])

        s = response['choices'][0]['message']['content']
        cleaned_s = extract_json(s)

        obj_response = json.loads(cleaned_s)
        print("obj_response", obj_response)
        print("whole content: ", content)
        # if not content["reading"]:
        #     content["reading"] = {}

        # content["reading"] = {**content["reading"], **obj_response}
        # print("Content of reading: ", content["reading"])
        content["reading"] = obj_response
        return (jsonify(content), 201)







# start = time.time()

# # prompt = """What is the meaning of {} in {}""".format(tokenizedJapaneseSentenceArray[4], source)
# prompt = """What's the reading for the word {}in the context of {}? Only return the reading in Hiragana form.""".format(tokenizedJapaneseSentenceArray[1], source)

# response = openai.Completion.create(
#     model="text-davinci-003",
#     prompt= prompt,
#     temperature=0.7,
#     max_tokens=3000,
#     top_p=1,
#     frequency_penalty=0,
#     presence_penalty=0
# )

# end = time.time()

# total_time = end - start

# print(f"LOADING TIME: {total_time}")
# print(response['choices'][0]['text'])











def fetch_data(url):
    response = requests.get(url)
    return response.json()

def fetch_papago_data(url, headers, payload):
    response = requests.post(url, headers=headers, data=payload)
    return response.json()

def fetch_openai_data(openai_prompt):
    # Call the OpenAI API with the provided prompt
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=openai_prompt,
        temperature=0.7,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    return response

def fetch_all_data(urls, openai_prompt, papago_headers=None, papago_payload=None):
    with ThreadPoolExecutor() as executor:
        tasks = [executor.submit(fetch_data, url) for url in urls[:-1]]
        tasks.append(executor.submit(fetch_papago_data, urls[-1], papago_headers, papago_payload))
        tasks.append(executor.submit(fetch_openai_data, openai_prompt))

        results = [task.result() for task in tasks]
        return results



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


    start = time.time()

    response = openai.ChatCompletion.create(
        messages=messages,
        model="gpt-3.5-turbo",
        max_tokens=1500,
    )


    end = time.time()

    total_time = end - start

    print(f"HINT LOADING TIME: {total_time}")


    content['hint'] = response['choices'][0]['message']['content']
    print(content['hint'])
    return (jsonify(content), 201)



@app.route('/analysis', methods=['POST'])
def analysis():

    content = request.get_json()


    openai_prompt = """I'm trying to practice translating Japanese sentences into English. 
                        Using the source text, rate and give me an analysis and evaluation on my translation attempt. 
                        Be critical of the nuances of the Japanese words and the English words I used. \n\n
                        Source text: {}\n\n
                        My attempt: {}\n\n
                        Analysis: """.format(content['textToTranslate'], content['translatedText'])
    


    start = time.time()


    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=openai_prompt,
        temperature=0.7,
        max_tokens=2000,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    end = time.time()

    total_time = end - start

    print(f"ATTEMPT ANALYSIS LOADING TIME: {total_time}")




    content['attemptAnalysis'] = response['choices'][0]['text']

    return (jsonify(content), 201)













@app.route('/morphoanalysis', methods=['POST'])
def morphoanalysis():

    content = request.get_json()

    source_text = content['textToTranslate']




    
    openai_prompt = """You will return the Furigana and English meaning of the Japanese words from a text that I will provide you. 
                        Pay attention to the tone and context I gave you when generating the meaning.
                        When tokenizing, look for more idiomatic expressions or common phrases instead of just breaking down everything to small words and giving out their literal meanings.
                        When the tokenized word doesn't have any Kanji, just provide an empty string for the furigana.
                        Also pay attention to the correct reading for the tokenized word like 辺り should have the reading あたり instead of へんり.
                        The order of the objects should be the same as the order of the Japanese words in the source text.

                        Example source text: この辺りは治安も悪くないけど、あの辺りは治安が良くないからね。

                        I want you to return a JSON object like this: 
                        [
                            { "text": "この", "furigana": "", "meaning": "this" }, 
                            { "text": "辺り", "furigana": "あたり", "meaning": "area" }, 
                            { "text": "は", "furigana": "", "meaning": "topic marker" }, 
                            { "text": "治安", "furigana": "ちあん", "meaning": "public order" }, 
                            { "text": "も", "furigana": "", "meaning": "also" }, 
                            { "text": "悪くない", "furigana": "わるくない", "meaning": "not bad" }, 
                            { "text": "けど", "furigana": "", "meaning": "but" }, 
                            { "text": "、", "furigana": "", "meaning": "comma" }, 
                            { "text": "あの", "furigana": "", "meaning": "that" }, 
                            { "text": "辺り", "furigana": "あたり", "meaning": "area" }, 
                            { "text": "は", "furigana": "", "meaning": "topic marker" }, 
                            { "text": "治安", "furigana": "ちあん", "meaning": "public order" }, 
                            { "text": "が", "furigana": "", "meaning": "subject marker" }, 
                            { "text": "良くない", "furigana": "よくない", "meaning": "not good" }, 
                            { "text": "から", "furigana": "", "meaning": "because" }, 
                            { "text": "ね", "furigana": "", "meaning": "confirmation marker" }, 
                            { "text": "。", "furigana": "", "meaning": "period" }
                        ]

                        Now this is my source text I want you to parse:""" + source_text + """\n\n
                        Your JSON return here: """
    

    start = time.time()

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=openai_prompt,
        temperature=0.7,
        max_tokens=3000,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    end = time.time()

    total_time = end - start

    print(f"MORPHOANALYSYS LOADING TIME: {total_time}")




    print(response['choices'][0]['text'])

    json_string = response['choices'][0]['text']

    # Remove extra formatting
    json_string = json_string.replace('\n', '').replace('\r', '').replace('\t', '')

    # Remove double quotes around the JSON array
    json_string = json_string.strip('"')

    # Parse the cleaned JSON string
    data = json.loads(json_string)


    content['morphoAnalysis'] = data



    return (jsonify(content), 201)





@app.route('/analysis2', methods=['POST'])
def analysis2():



    PAPAGO_API_URL = 'https://openapi.naver.com/v1/papago/n2mt'
    DEFAULT_CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'
    SOURCE_LANG = 'ja'
    TARGET_LANG = 'en'

    content = request.get_json()
    # print(f"My Data: {content}")

    papago_payload = {
        'text': content['textToTranslate'], 
        'source': SOURCE_LANG, 
        'target': TARGET_LANG
    }

    papago_headers = {
        'X-Naver-Client-Id': PAPAGO_CLIENT_ID,
        'X-Naver-Client-Secret': PAPAGO_CLIENT_SECRET,
        'Content-Type': DEFAULT_CONTENT_TYPE
    }


    urls = [PAPAGO_API_URL]
    openai_prompt = """I'm trying to practice translating Japanese sentences into English. 
#             Using the source text, rate and give me an analysis and evaluation on my attempt. 
#             Be critical of the nuances of the Japanese words used. \n\n
#             Source text: 人生は挑戦の連続ですが、困難な状況から学びを見つけることが重要です\n\n
#             My attempt: Life has a series of problems, but the learning from the toughest situations is important.\n\n
#             Analysis: """
    data = fetch_all_data(urls, openai_prompt, papago_headers, papago_payload)


    print("THIS IS THE DATAAAAAAAAAAAAAAA", data)








    content["suggestedTranslationFromPapago"] = data['message']['result']['translatedText']
    content["suggestedTranslation"] = data['message']['result']['translatedText']


    # papagoScore = getScore(content['suggestedTranslationFromPapago'], content['translatedText'])
    # wanikaniScore = getScore(content['generatedTextEngVerFromWanikani'], content['translatedText'])
    # finalScore = max(papagoScore, wanikaniScore)

    # content['finalScore'] = finalScore



    suggestedTranslationBoolsArray = []

    suggestedTranslationArray = content['suggestedTranslation'].split() if content['generatedTextEngVerFromWanikani'] == '' else content['generatedTextEngVerFromWanikani'].split()
    print(f"suggestedTranslationArray: {suggestedTranslationArray}")
    translatedTextArray = content['translatedText'].split()

    for elem in suggestedTranslationArray:
        if elem in translatedTextArray:
            suggestedTranslationBoolsArray.append(True)
        else:
            suggestedTranslationBoolsArray.append(False)

    content['suggestedTranslationBoolsArray'] = suggestedTranslationBoolsArray
    content['translatedTextArray'] = translatedTextArray
    content['suggestedTranslationArray'] = suggestedTranslationArray

    print(f"content['suggestedTranslationBoolsArray']: {content['suggestedTranslationBoolsArray']}")

    print(f"CONTENT: {content}")




    return (jsonify(content), 201)




# response = openai.Completion.create(
#   model="text-davinci-003",
#   prompt="""I'm trying to practice translating Japanese sentences into English. 
#             Using the source text, rate and give me an analysis and evaluation on my attempt. 
#             Be critical of the nuances of the Japanese words used. \n\n
#             Source text: 人生は挑戦の連続ですが、困難な状況から学びを見つけることが重要です\n\n
#             My attempt: Life has a series of problems, but the learning from the toughest situations is important.\n\n
#             Analysis: """,
#   temperature=0.7,
#   max_tokens=2048,
#   top_p=1,
#   frequency_penalty=0,
#   presence_penalty=0
# )

# print(response['choices'][0]['text'])






@app.route('/translation', methods=['POST'])
def translation():

    PAPAGO_API_URL = 'https://openapi.naver.com/v1/papago/n2mt'
    DEFAULT_CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'
    SOURCE_LANG = 'ja'
    TARGET_LANG = 'en'

    content = request.get_json()
    # print(f"My Data: {content}")

    payload = {
        'text': content['textToTranslate'], 
        'source': SOURCE_LANG, 
        'target': TARGET_LANG
    }

    headers = {
        'X-Naver-Client-Id': PAPAGO_CLIENT_ID,
        'X-Naver-Client-Secret': PAPAGO_CLIENT_SECRET,
        'Content-Type': DEFAULT_CONTENT_TYPE
    }

    body = requests.post(PAPAGO_API_URL, headers=headers, data=payload)


    data = json.loads(body.text)
    content["suggestedTranslationFromPapago"] = data['message']['result']['translatedText']
    content["suggestedTranslation"] = data['message']['result']['translatedText']


    papagoScore = getScore(content['suggestedTranslationFromPapago'], content['translatedText'])
    wanikaniScore = getScore(content['generatedTextEngVerFromWanikani'], content['translatedText'])
    finalScore = max(papagoScore, wanikaniScore)

    content['finalScore'] = finalScore



    suggestedTranslationBoolsArray = []

    suggestedTranslationArray = content['suggestedTranslation'].split() if content['generatedTextEngVerFromWanikani'] == '' else content['generatedTextEngVerFromWanikani'].split()
    # print(f"suggestedTranslationArray: {suggestedTranslationArray}")
    translatedTextArray = content['translatedText'].split()

    for elem in suggestedTranslationArray:
        if elem in translatedTextArray:
            suggestedTranslationBoolsArray.append(True)
        else:
            suggestedTranslationBoolsArray.append(False)

    content['suggestedTranslationBoolsArray'] = suggestedTranslationBoolsArray
    content['translatedTextArray'] = translatedTextArray
    content['suggestedTranslationArray'] = suggestedTranslationArray

    # print(f"content['suggestedTranslationBoolsArray']: {content['suggestedTranslationBoolsArray']}")

    # print(f"CONTENT: {content}")




    return (jsonify(content), 201)
















def getEngMeanings(jpToken, tokenRes):

    numOfDiffDefs = len(tokenRes['data'])

    for j in range(numOfDiffDefs):

        if tokenRes['data'][j]['slug'] == jpToken:
            numOfEngDef = len(tokenRes['data'][j]['senses'])
            definitions = []
            for k in range(numOfEngDef):
                definitions = definitions + tokenRes['data'][j]['senses'][k]['english_definitions']

            return definitions


        else: #if no match found, take the first diffDef

            numOfEngDef = len(tokenRes['data'][0]['senses'])
            definitions = []
            for k in range(numOfEngDef):
                definitions = definitions + tokenRes['data'][0]['senses'][k]['english_definitions']


    return definitions










async def getAsyncRes(jpToEngDict):

    results = []

    async with aiohttp.ClientSession() as session:

        jpTokens = []

        async def get_tasks(session):
            tasks = []
            for jpToken in jpToEngDict:
                tasks.append(asyncio.create_task(session.get('https://jisho.org/api/v1/search/words?keyword=' + jpToken)))
                jpTokens.append(jpToken)
            return tasks

        tasks = await get_tasks(session)

        responses = await asyncio.gather(*tasks)


        for response in responses:
            # results.append(await response.json())

            # results.append(await response.json(content_type=None))

            data = await response.read()
            hashrate = json.loads(data)
            results.append(hashrate)


        finishedList = []

        print(f'RESULTS LENGTH: {len(results)}')
        print(f'JP DICT LENGTH: {len(jpToEngDict)}')

        print(f'JP TOKENS: {jpTokens}')



        for i in range(len(jpTokens)):

            if results[i]['data']:

                jpToEngDict[jpTokens[i]] = getEngMeanings(jpTokens[i], results[i])

            else:
                jpToEngDict[jpTokens[i]] = ['*NOT FOUND*']


    return jpToEngDict






def getDefinitions(text, r):

    jpToEngDict = {}

    start = time.time()

    numOfTokens = len(r.data)
    

    for i in range(numOfTokens):
        word = r.data[i].token
        if word == '。' or word == '、' or word == '？' or word == '！':
            continue
        if word not in jpToEngDict:
            jpToEngDict[word] = [] #init
    


    
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    jpToEngDict = asyncio.run(getAsyncRes(jpToEngDict))





    end = time.time()

    total_time = end - start

    print(f"Time it took in seconds: {total_time}")


    #trim unnecessary words
    for item in jpToEngDict:
        # print(jpToEngDict[item])
        for i in range(len(jpToEngDict[item])):
            jpToEngDict[item][i] = jpToEngDict[item][i].replace('to be ', '')
            jpToEngDict[item][i] = jpToEngDict[item][i].replace('to ', '')
        # print(jpToEngDict[item])

    print(json.dumps(jpToEngDict))

    return jpToEngDict






def getRawScoreFromJapaneseText(japaneseTargets):

    maxScore = -1 if len(japaneseTargets) == 0 else len(japaneseTargets)
    score = 0

    for wordToScore in japaneseTargets:
        if japaneseTargets[wordToScore]:
            score += 1

    totalScore = int((score/maxScore)*100)

    return totalScore














def getRootWord(word):

    # body = requests.get('https://api.dictionaryapi.dev/api/v2/entries/en/hello')
    # data = json.loads(body.text)
    # print(data)

    pass










    

def getJapaneseTargets(textToTranslate, translatedText, definitions):

    # print(json.dumps(definitions))    


    """Matching Japanese target words with the translator's words"""
    textToTranslateTargets = {}
    textToTranslateTokens = [token for token in definitions]
    for tok in textToTranslateTokens:
        if tok not in textToTranslateTargets:
            textToTranslateTargets[tok] = None

    numOfTranslatedTextTargets = {}
    translatedTextTokens = translatedText.replace(",", "").replace(".", "").replace("?", "").replace("!", "").split()
    for singleRefWord in translatedTextTokens:
        if singleRefWord not in numOfTranslatedTextTargets:
            numOfTranslatedTextTargets[singleRefWord] = 0 #init
        numOfTranslatedTextTargets[singleRefWord] += 1

        for definition in definitions:
            engWordsList = definitions[definition]
            for multiWord in engWordsList:
                if singleRefWord.lower() in multiWord.lower().split()[0]:
                    if numOfTranslatedTextTargets[singleRefWord] > 0:
                        textToTranslateTargets[definition] = multiWord
                        numOfTranslatedTextTargets[singleRefWord] -= 1 # the translator has used one Eng word

    print(textToTranslateTargets)

    return textToTranslateTargets


















def getScore(suggestedOrGeneratedTranslationText, translatedText):

    translationFromTokens = suggestedOrGeneratedTranslationText.split()
    translationDict = {}
    for word in translationFromTokens:
        if word not in translationDict:
            translationDict[word] = 0
        translationDict[word] += 1

    translatedTextTokens = translatedText.split()

    for translatorWord in translatedTextTokens:
        if translatorWord in translationDict:
            if translationDict[translatorWord] > 0:
                translationDict[translatorWord] -= 1

    score = 0
    maxScore = -1 if len(translationDict) == 0 else len(translationDict)

    for word in translationDict:
        if translationDict[word] == 0:
            score += 1

    return int((score/maxScore)*100)















@app.route('/generation', methods=['GET'])
def generation():

    difficultyRange = request.args.getlist('difficultyRange[]')

    difficultyRangeStart = int(difficultyRange[0])
    difficultyRangeEnd =  int(difficultyRange[1])

    # print(difficultyRangeStart)
    # print(difficultyRangeEnd)


    queryRange = 9160 - 2467 #6693


    for _ in range(58):

        ranNum = random.randint(2467 + ((queryRange//100) * difficultyRangeStart), 2467 + ((queryRange//100) * difficultyRangeEnd))

        WANIKANI_URL = 'https://api.wanikani.com/v2/subjects/' + str(ranNum)
        requestHeaders = { 'Authorization': 'Bearer ' + WANIKANI_API_TOKEN}

        body = requests.get(WANIKANI_URL, headers=requestHeaders)
 

        res = json.loads(body.text)



        # print('num of iter: ', _)
        # print('ranNum: ', ranNum)

        resObject = res['object']
        # print(resObject)

        if resObject == 'vocabulary':

            sentencesLen = len(res['data']['context_sentences'])

            if sentencesLen > 0:

                # print('sentencesLen: ', sentencesLen)

                result = jsonify(res['data']['context_sentences'][random.randint(0, sentencesLen-1)])

                return (result, 200)

    return ({"error": "Please try again after one minute."}, 404) #if all 58 iterations fail








@app.route('/japanese-data', methods=['POST'])
def japaneseData():


    content = request.get_json()
    # print(content)



    r = Tokens.request(content['textToTranslate'])

    numOfTokens = len(r.data)
    tokenizedJapaneseSentenceArray = []

    for i in range(numOfTokens):
        word = r.data[i].token
        if word == '。' or word == '、' or word == '？' or word == '！':
            continue
        tokenizedJapaneseSentenceArray.append(word)

    print(f"tokenizedJapaneseSentenceArray: {tokenizedJapaneseSentenceArray}")




    engDefinitions = getDefinitions(content['textToTranslate'], r)
    # print(f'engDefinitions: {engDefinitions}')


    japaneseTargets = getJapaneseTargets(content['textToTranslate'], content['translatedText'], engDefinitions)
    # print(f'japaneseTargets: {japaneseTargets}')

    japaneseRawScore = getRawScoreFromJapaneseText(japaneseTargets)
    # print(f'japaneseRawScore: {japaneseRawScore}')




    content['engDefinitions'] = engDefinitions
    content['japaneseTargets'] = japaneseTargets
    content['japaneseRawScore'] = japaneseRawScore
    content['tokenizedJapaneseSentenceArray'] = tokenizedJapaneseSentenceArray



    return (jsonify(content), 201)













if __name__ == "__main__":
    app.run(debug=True)
