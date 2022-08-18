from flask import Flask, request, jsonify
import requests
import json
import random
from jisho_api.tokenize import Tokens
from jisho_api.word import Word
from credentials import (
    PAPAGO_CLIENT_ID, 
    PAPAGO_CLIENT_SECRET, 
    WANIKANI_API_TOKEN
)


app = Flask(__name__)




def getDefinitions(text):

    jpToEngDict = {}

    r = Tokens.request(text)
    numOfTokens = len(r.data)
    for i in range(numOfTokens):
        word = r.data[i].token

        if word not in jpToEngDict:
            jpToEngDict[word] = [] #init
        if word == '。' or word == '、':
            continue

    
        r2 = Word.request(word)
        numOfDiffDefs = len(r2.data)
        for j in range(numOfDiffDefs):

            if r2.data[j].slug == word:
                numOfEngDef = len(r2.data[j].senses)
                definitions = []
                for k in range(numOfEngDef):
                    definitions = definitions + r2.data[j].senses[k].english_definitions

                jpToEngDict[word] = definitions

            else: #if no match found, take the first diffDef
                numOfEngDef = len(r2.data[0].senses)
                definitions = []
                for k in range(numOfEngDef):
                    definitions = definitions + r2.data[0].senses[k].english_definitions

                jpToEngDict[word] = definitions


        






    #trim unnecessary words
    for item in jpToEngDict:
        # print(jpToEngDict[item])
        for i in range(len(jpToEngDict[item])):
            jpToEngDict[item][i] = jpToEngDict[item][i].replace('to be ', '')
            jpToEngDict[item][i] = jpToEngDict[item][i].replace('to ', '')
        # print(jpToEngDict[item])

    return jpToEngDict




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
    result = { "suggestedTranslation": data['message']['result']['translatedText'] }
    content["suggestedTranslationFromPapago"] = data['message']['result']['translatedText']


    definitions = getDefinitions(content['textToTranslate'])
    # print(json.dumps(definitions))    


    """Matching Japanese target words with the translator's words"""
    textToTranslateTargets = {}
    textToTranslateTokens = [token for token in definitions]
    for tok in textToTranslateTokens:
        if tok not in textToTranslateTargets:
            textToTranslateTargets[tok] = None

    numOfTranslatedTextTargets = {}
    translatedTextTokens = content['translatedText'].split()
    for singleRefWord in translatedTextTokens:
        if singleRefWord not in numOfTranslatedTextTargets:
            numOfTranslatedTextTargets[singleRefWord] = 0 #init
        numOfTranslatedTextTargets[singleRefWord] += 1

        for definition in definitions:
            EngWordsList = definitions[definition]
            for multiWord in EngWordsList:
                if singleRefWord.lower() in multiWord.lower().split():
                    if numOfTranslatedTextTargets[singleRefWord] > 0:
                        textToTranslateTargets[definition] = multiWord
                        numOfTranslatedTextTargets[singleRefWord] -= 1 # the translator has used one Eng word

    # print(textToTranslateTargets)

    maxScore = len(textToTranslateTargets)
    score = 0

    for wordToScore in textToTranslateTargets:
        if textToTranslateTargets[wordToScore]:
            score += 1

    totalScore = int((score/maxScore)*100)









    suggestedTranslationFromPapagoTokens = content['suggestedTranslationFromPapago'].split()
    suggestedTranslationFromPapagoDict = {}
    for papagoWord in suggestedTranslationFromPapagoTokens:
        if papagoWord not in suggestedTranslationFromPapagoDict:
            suggestedTranslationFromPapagoDict[papagoWord] = 0
        suggestedTranslationFromPapagoDict[papagoWord] += 1

    translatedTextTokens = content['translatedText'].split()

    print(suggestedTranslationFromPapagoTokens)

    for translatorWord in translatedTextTokens:
        if translatorWord in suggestedTranslationFromPapagoDict:
            if suggestedTranslationFromPapagoDict[translatorWord] > 0:
                suggestedTranslationFromPapagoDict[translatorWord] -= 1

    papagoScore = 0
    papagoMaxScore = len(suggestedTranslationFromPapagoTokens)

    for papagoWord in suggestedTranslationFromPapagoDict:
        if suggestedTranslationFromPapagoDict[papagoWord] == 0:
            papagoScore += 1

    papagoTotalScore = int((papagoScore/papagoMaxScore)*100)









    generatedTextEngVerFromWanikaniTokens = content['generatedTextEngVerFromWanikani'].split()
    generatedTextEngVerFromWanikaniDict = {}
    for papagoWord in generatedTextEngVerFromWanikaniTokens:
        if papagoWord not in generatedTextEngVerFromWanikaniDict:
            generatedTextEngVerFromWanikaniDict[papagoWord] = 0
        generatedTextEngVerFromWanikaniDict[papagoWord] += 1

    translatedTextTokens = content['translatedText'].split()

    for translatorWord in translatedTextTokens:
        if translatorWord in generatedTextEngVerFromWanikaniDict:
            if generatedTextEngVerFromWanikaniDict[translatorWord] > 0:
                generatedTextEngVerFromWanikaniDict[translatorWord] -= 1

    wanikaniScore = 0
    papagoMaxScore = len(generatedTextEngVerFromWanikaniTokens)

    for papagoWord in generatedTextEngVerFromWanikaniDict:
        if generatedTextEngVerFromWanikaniDict[papagoWord] == 0:
            wanikaniScore += 1

    wanikaniTotalScore = int((wanikaniScore/papagoMaxScore)*100)









    print(f"My Data: {content}")
    print('\n')

    print(f'YOUR JAPANESE GRADE IS: {totalScore}%')
    print(f'YOUR PAPAGO GRADE IS: {papagoTotalScore}%')
    print(f'YOUR WANIKANI GRADE IS: {wanikaniTotalScore}%')

    print('\n')
    print(f'YOUR OVERALL GRADE IS: {max(totalScore, papagoTotalScore, wanikaniTotalScore)}%')
    print('\n')







    











    










    return (jsonify(result), 201)




@app.route('/generation', methods=['GET'])
def generation():

    for _ in range(58):

        ranNum = random.randint(2467, 9160)

        WANIKANI_URL = 'https://api.wanikani.com/v2/subjects/' + str(ranNum)
        requestHeaders = { 'Authorization': 'Bearer ' + WANIKANI_API_TOKEN}

        body = requests.get(WANIKANI_URL, headers=requestHeaders)
 

        res = json.loads(body.text)



        print('object: ', res['object'])
        print('num of iter: ', _)
        print('ranNum: ', ranNum)

        if res['object'] == 'vocabulary':

            sentencesLen = len(res['data']['context_sentences'])

            if sentencesLen > 0:

                print('sentencesLen: ', sentencesLen)

                result = jsonify(res['data']['context_sentences'][random.randint(0, sentencesLen-1)])

                return (result, 200)

    return ({"error": "Please try again after one minute."}, 404) #if all 58 iterations fail




if __name__ == "__main__":
    app.run(debug=True)
