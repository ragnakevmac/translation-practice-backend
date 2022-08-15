from flask import Flask, request, jsonify
import requests
import json
import random
from credentials import (
    PAPAGO_CLIENT_ID, 
    PAPAGO_CLIENT_SECRET, 
    WANIKANI_API_TOKEN
)


app = Flask(__name__)




@app.route('/translation', methods=['POST'])
def translation():

    PAPAGO_API_URL = 'https://openapi.naver.com/v1/papago/n2mt'
    DEFAULT_CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'
    SOURCE_LANG = 'ja'
    TARGET_LANG = 'en'

    content = request.get_json()
    print(f"My Data: {content}")

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
