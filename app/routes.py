from flask import Blueprint, request, jsonify, render_template, redirect, session, url_for
from app import db
import random
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from app.bert_emotions_classifier import classify_text
import requests
from app.memory_retriever import chat_with_user,detect_emotion

main = Blueprint("main", __name__)

GEMINI_URL='https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateText'

# 🏠 Home Route
@main.route("/", methods=["GET"])
def index():
    return render_template('index.html')

#Contact
@main.route('/contact',methods=['GET'])
def contact():
    return render_template('contact.html')

#About
@main.route('/about',methods=['GET'])
def about():
    return render_template('about.html')

# 🔐 Login Page
@main.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

# 📝 Registration Page
@main.route('/register', methods=['GET'])
def registration_page():
    return render_template('registration.html')

@main.route('/register', methods=['POST'])
def register():
    data = request.form
    name=data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return "Error: Email and password are required!", 400
    
    user = db.users.find_one({"email": email})  
    if user:
        return render_template("registration.html", error="Email already exists!")
    
    hashed_password = generate_password_hash(password)  # Hash password before storing
    db.users.insert_one({'name':name,"email": email, "password": hashed_password})
    return redirect(url_for('main.login_page'))

@main.route("/login", methods=["POST"])
def login():
    data = request.form
    email = data.get("email")
    user = db.users.find_one({"email": data.get("email")})

    if user and check_password_hash(user["password"], data.get("password")):
        session['logged_in']=True
        session['user_email'] = email
        session['user_name'] = user.get("name", "Guest")
        return redirect(url_for("main.main_page"))
    else:
        return render_template("login.html", error="Invalid email or password.")

# 🏠 Main Page Route
@main.route('/main', methods=['GET'])
def main_page():
    if not session.get('logged_in'):  
        return redirect(url_for('main.login_page'))
    user_email = session.get('user_email', 'Guest')
    user_name=session.get('user_name')
    if not user_name:  # If session does not have name, get from DB
        user = db.users.find_one({"email": user_email})
        if user:
            user_name = user.get("name", "Guest")
            session['user_name'] = user_name
    return render_template('main_page.html', name=user_name, email=user_email)

# 🔐 Logout
@main.route('/logout', methods=['GET'])
def logout():
    session.clear()  
    return redirect(url_for('main.login_page'))

@main.route('/write',methods=['GET'])
def write_page():
    if not session.get('logged_in'):
        return redirect(url_for('main.login_page'))
    return render_template('write.html')

@main.route("/save_entry", methods=["POST"])
def save_entry():
    data = request.json
    title = data.get("title", "")
    content = data.get("content", "")
    user_id=session.get('user_email')
    timestamp = data.get("timestamp", "")

    classified_emotion = classify_text(content)

    # 🔹 Step 2: Store Entry in Database
    entry = {
        "user_id": generate_password_hash(user_id),
        'title':title,
        'content':content,
        "emotion": classified_emotion, 
        "timestamp": timestamp,
    }
    db.entries.insert_one(entry)  

    return jsonify({"message": "Entry saved successfully!", "emotion": classified_emotion})

@main.route("/search", methods=["GET"])
def search_by_keyword():
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403

    keyword = request.args.get("keyword", "").strip().lower()
    if not keyword:
        return jsonify({"message": "Please provide a keyword"}), 400

    user_email = session.get("user_email")
    
    # Fetch only relevant fields: Exclude _id for cleaner response
    user_entries = list(db.entries.find({}, {"_id": 0, "user_id": 1, "title": 1, "content": 1, "timestamp": 1}))

    matching_entries = []
    for entry in user_entries:
        print(f"Checking entry: {entry}")  # Debugging: Show fetched entries
        
        if check_password_hash(entry["user_id"], user_email):  # Match logged-in user
            print(f"User Matched: {entry['title']}")  # Debugging: Check successful matches
            
            # Check if keyword is in title or content
            if keyword in entry["title"].lower() or keyword in entry["content"].lower():
                matching_entries.append({
                    "title": entry["title"],
                    "content": entry["content"],
                    "timestamp": entry["timestamp"]
                })
    print('Matching entries:\n')
    for i in matching_entries:
        for j in i:
            print(j)  # Debugging: Show final results

    if not matching_entries:
        return jsonify({"message": "No matching entries found."})

    return jsonify({"results": matching_entries})

#searching for date
# from bson.regex import Regex
# from datetime import datetime

# @main.route("/search", methods=["GET"])
# def search_memory():
#     if not session.get("logged_in"):
#         return jsonify({"message": "Unauthorized"}), 403

#     user_id = session.get("user_email")
#     date_str = request.args.get("date", "")

#     if not date_str:
#         return jsonify({"message": "Please select a date"}), 400

#     try:
#         # Convert date string to a datetime object
#         date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#         start_date = datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0)
#         end_date = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
#     except ValueError:
#         return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

#     search_filter = {
#         "user_id": user_id,
#         "timestamp": {"$gte": start_date, "$lt": end_date}
#     }

#     results = list(db.entries.find(search_filter, {"_id": 0}))

#     if not results:
#         return jsonify({"message": "No matching entries found."})

#     return jsonify({"results": results})

@main.route("/chat",methods=['GET'])
def chat_page():
    return render_template("chat.html")  # Renders the chat page

@main.route("/chat_api", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id")
    user_input = data.get("message").strip().lower()

    if not user_id or not user_input:
        return jsonify({"error": "Missing user_id or message"}), 400

    # Step 1: Check if the user is greeting
    greetings = ["hi", "hello", "hey"]
    if user_input in greetings:
        return jsonify({"response": "How are you feeling today?"})

    # Step 2: Detect emotion from user input
    detected_emotion = detect_emotion(user_input)

    # Step 3: Prevent looping "How are you feeling today?"
    if detected_emotion is None:
        return jsonify({"response": "Could you tell me more about how you're feeling?"})

    # Step 4: Respond based on detected emotion
    happy_memory_requested = session.get('happy_memory_requested', False) #get the value, and default to false if not set.
    response, new_happy_memory_requested = chat_with_user(user_id, user_input, happy_memory_requested)

    session['happy_memory_requested'] = new_happy_memory_requested #set the new value in the session.

    return jsonify({"response": response})


"""# 😊 3. Retrieve Memories by Emotion & RASA response
@main.route("/emotion_based", methods=["GET"])
def get_emotion_memories():
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403

    emotion = request.args.get("emotion", "").lower().strip()
    valid_emotions = ["anger", "anticipation", "joy", "love", "disgust", "fear", "optimism", "pessimism", "sadness", "surprise", "trust"]

    if emotion not in valid_emotions:
        return jsonify({"error": f"Invalid emotion. Choose from: {', '.join(valid_emotions)}"}), 400

    OPPOSITE_EMOTIONS = {
        "anger": ["trust", "love"],  
        "anticipation": ["joy", "optimism"],  
        "disgust": ["trust", "love"],  
        "fear": ["trust", "love"],    
        "optimism": ["optimism", "joy"],  
        "pessimism": ["optimism", "joy"],  
        "sadness": ["joy", "love"],  
        "surprise": ["trust", "optimism"],  
        "trust": ["trust", "love"],  
    }

    # Get opposite emotions if available, else just use the same emotion
    related_emotions = OPPOSITE_EMOTIONS.get(emotion, []) + [emotion]

    # Retrieve memories that match either the given emotion or its opposite emotions
    filtered_entries = list(db.entries.find(
        {"user_id": session.get("user_email"), "emotion": {"$in": related_emotions}}, 
        {"_id": 0}
    ))

    if not filtered_entries:
        return jsonify({"message": f"No memories found for the emotion: {emotion}."})

    return jsonify({"memories": filtered_entries})"""
