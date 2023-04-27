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
from credentials import (
    PAPAGO_CLIENT_ID, 
    PAPAGO_CLIENT_SECRET, 
    WANIKANI_API_TOKEN,
    OPENAI_API_KEY
)
openai.api_key = OPENAI_API_KEY


app = Flask(__name__)




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






@app.route('/translation', methods=['POST'])
def translation():








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
