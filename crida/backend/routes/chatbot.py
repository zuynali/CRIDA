import os
from flask import Blueprint, request, jsonify
import requests

chatbot_bp = Blueprint("chatbot", __name__)

API_KEY = os.getenv("GROQ_API_KEY")
url = "https://api.groq.com/openai/v1/chat/completions"

context = """
CRIDA (Civil Registration and DataBase Authority)
ID Cards(National Identity Cards)
Provides Facilities of Certificates(Marriage,Death,Birth)
Licences(Cars,Bikes,Trucks)
Passports

Requirements for every Document(Full Name,Father Name,Address,Country,Gender,Picture,No Criminal Record)
if anyone wants to contact us So provide email : CRIDA@gmail.com
Eligibility Criteria = 18+
Fees = 2100 PKR
Urgent Plan Not Avaialble yet
Issuance Time Taken = 3 minutes
"""

@chatbot_bp.route("/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "API Key not configured"}), 500

    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    prompt = f"""
Answer ONLY from this context.
If answer is not present say "I Can't Answer Queries unrelated to CRIDA."

Context:
{context}

Question:
{user_message}
"""

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
