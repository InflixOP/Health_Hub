import datetime
import os

import mindsdb_sdk
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

MINDSDB_HOST = 'https://cloud.mindsdb.com'
MINDSDB_API_KEY = os.environ.get('MINDSDB_API_KEY')

client = OpenAI(
    api_key=MINDSDB_API_KEY,
    base_url="https://llm.mdb.ai/"
)

chat_history = []

def connect_to_mindsdb():
    try:
        print("Attempting to connect to MindsDB...")
        server = mindsdb_sdk.connect(MINDSDB_HOST, api_key=MINDSDB_API_KEY)
        print("Connected YAYYYY!")
        return server
    except Exception as error:
        print(f"Failed to connect to MindsDB. Error: {error}")
        return None

server = connect_to_mindsdb()
if server is None:
    print("Failed to connect to MindsDB. Please check your API key and connection settings.")
    exit(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    print(f"Received data: {data}")
    
    age = data.get('age')
    gender = data.get('gender')
    symptom1 = data.get('symptom1', '').lower()
    symptom2 = data.get('symptom2', '').lower()
    symptom3 = data.get('symptom3', '').lower()
    print(f"Parsed data: age={age}, gender={gender}, symptoms={symptom1}, {symptom2}, {symptom3}")
    
    diagnosis, explanation, confidence = predict_diagnosis(server, age, gender, symptom1, symptom2, symptom3)
    
    response = {'diagnosis': diagnosis, 'explanation': explanation, 'confidence': confidence}
    print(f"Sending response: {response}")
    return jsonify(response)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data['message']
    
    chat_history.append({"role": "user", "content": user_message})
    
    response = get_chatbot_response(user_message)
    chat_history.append({"role": "assistant", "content": response})
    
    return jsonify({'response': response})

@app.route('/generate_plan', methods=['POST'])
def generate_plan():
    data = request.json
    start_date = data['startDate']
    end_date = data['endDate']
    
    plan = generate_personalized_health_plan(start_date, end_date)
    
    return jsonify({'plan': plan})

def predict_diagnosis(server, age, gender, symptom1, symptom2, symptom3):
    try:
        if symptom1 == 'fever' and symptom2 == 'cough' and symptom3 == 'fatigue':
            return "Common Cold", "The combination of fever, cough, and fatigue is often indicative of a common cold.", 80.0

        query = f"""
        SELECT diagnosis, diagnosis_explain, confidence
        FROM health_diagnosis.diagnosis_predictor
        WHERE age = {age}
        AND gender = '{gender}'
        AND symptom1 = '{symptom1.strip()}'
        AND symptom2 = '{symptom2.strip()}'
        AND symptom3 = '{symptom3.strip()}'
        """
        print(f"Executing query: {query}")
        
        result = server.query(query)
        print("Query executed successfully")
        
        result_list = result.fetch()
        print(f"Query result: {result_list}")
        
        if result_list:
            confidence = result_list[0].get('confidence', 0.0) * 100
            diagnosis = result_list[0]['diagnosis']
            explanation = result_list[0].get('diagnosis_explain', 'No explanation provided')
            print(f"Prediction successful: {diagnosis}, {explanation}, {confidence}%")
            return diagnosis, explanation, confidence
        else:
            print("No results returned from the model")
            return "Unable to predict", "No matching data in the model for these symptoms", 0.0
    except Exception as e:
        print(f"Error during prediction: {str(e)}")
        return "Unable to predict", f"An error occurred during prediction: {str(e)}", 0.0

def get_chatbot_response(user_message):
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant specializing in health, diet, and lifestyle advice. Provide concise and helpful responses."},
                *chat_history,
                {"role": "user", "content": user_message}
            ],
            stream=False
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error getting chatbot response: {str(e)}")
        return f"An error occurred while processing your request: {str(e)}"

def generate_personalized_health_plan(start_date, end_date):
    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    date_range = (end - start).days + 1
    
    health_summary = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    
    prompt = f"""
    Based on the following chat history:
    {health_summary}
    
    Generate a personalized health plan for {date_range} days, starting from {start_date}.
    For each day, provide 3 tailored health activities or recommendations.
    Format the output as a Python dictionary where keys are date strings (YYYY-MM-DD) and values are lists of 3 activities.
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a health planner assistant. Provide personalized daily health activities."},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        plan = eval(completion.choices[0].message.content)
    except Exception as e:
        print(f"Error generating health plan: {str(e)}")
      
        plan = {}
        for i in range(date_range):
            current_date = start + datetime.timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            plan[date_str] = ["Rest and recover", "Stay hydrated", "Eat nutritious meals"]
    
    return plan

if __name__ == '__main__':
    app.run(debug=True)
