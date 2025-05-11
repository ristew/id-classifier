This is a basic application for classifying ID documents and extracting basic features. It includes an API that calls Gemini 2.5 Flash via OpenRouter and a frontend and affords viewing and editing the extracted features. 

Before running, make sure you set up your `.env` with OPENROUTER_API_KEY equal to a key generated from https://openrouter.ai/settings/keys

to run the API:
    
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/uvicorn server:app --reload


and to run the frontend:
    
    cd frontend
    npm install
    npm start


then go to https://localhost:3000 to use the app

to run the verification script, do `./venv/bin/python verify_classify.py`
```
