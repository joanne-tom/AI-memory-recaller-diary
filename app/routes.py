from flask import Blueprint, request, jsonify, render_template, redirect, session, url_for,current_app,flash
from app import db
import hashlib
import re
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from app.bert_emotions_classifier import classify_text
from datetime import datetime,timezone,timedelta
from app.memory_retriever import chat_with_user

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
    #secret_answer = request.form['secret_answer']
    #hashed_answer = hashlib.sha256(secret_answer.encode()).hexdigest()

    if not email or not password:
        return "Error: Email and password are required!", 400
    
    user = db.users.find_one({"email": email})  
    if user:
        return render_template("registration.html", error="Email already exists!")
    
    hashed_password = generate_password_hash(password)  # Hash password before storing
    email_hash = hashlib.sha256(email.encode()).hexdigest()  
    db.users.insert_one({'name':name, 'email': email,"email_hash": email_hash,"password": hashed_password})
    return redirect(url_for('main.login_page'))

"""@main.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        answer = request.form['secret_answer']
        hashed_answer = hashlib.sha256(answer.encode()).hexdigest()

        user = db.users.find_one({"email": email, "secret_answer": hashed_answer})
        if user:
            session['reset_email'] = email
            return redirect('/reset_password')
        else:
            flash("Incorrect email or answer", "danger")
    return render_template('forgot_password.html')

@main.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        return redirect('/login')

    if request.method == 'POST':
        new_password = request.form['password']
        email = session['reset_email']
        
        user = db.users.query.filter_by(email=email).first()
        user.password = generate_password_hash(new_password)  # Hash it!
        db.session.commit()
        session.pop('reset_email', None)

        flash("Password reset successful!", "success")
        return redirect('/login')

    return render_template('reset_password.html')"""

@main.route("/login", methods=["POST"])
def login():
    data = request.form
    email = data.get("email")
    user = db.users.find_one({"email": data.get("email")})

    if user and check_password_hash(user["password"], data.get("password")):
        session['logged_in']=True
        session['user_email'] = email
        session['user_name'] = user.get("name", "Guest")
        remember_me = data.get("remember_me")  # Get the 'remember me' checkbox value

        if remember_me:
            # Set a longer expiration time for the session cookie
            session.permanent = True  # Makes the session permanent (use cookie for long duration)
            current_app.permanent_session_lifetime = timedelta(days=30)  # Set the session timeout to 30 days
        else:
            session.permanent = False
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

"""
@main.route('/stack',methods=['GET'])
def stack():
    if not session.get('logged_in'):
        return redirect(url_for('main.login_page'))
    return render_template('stack.html')"""

@main.route("/save_entry", methods=["POST"])
def save_entry():
    data = request.json
    title = data.get("title", "")
    content = data.get("content", "")
    user_id=session.get('user_email')
    timestamp = data.get("timestamp", "")

    hashed_user_id = hashlib.sha256(user_id.encode()).hexdigest()

    classified_emotion = classify_text(content)

    # 🔹 Step 2: Store Entry in Database
    entry = {
        "user_id": hashed_user_id,
        'title':title,
        'content':content,
        "emotion": classified_emotion, 
        'timestamp' : datetime.now(timezone.utc),
    }
    db.entries.insert_one(entry)  

    return jsonify({"message": "Entry saved successfully!", "emotion": classified_emotion})

"""
@main.route("/view_memories", methods=["GET"])
def view_memories():
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403

    user_email = session.get("user_email")
    hashed_user_id = hashlib.sha256(user_email.encode()).hexdigest()

    entries = list(db.entries.find({"user_id": hashed_user_id}, {"_id": 0}))
    
    for entry in entries:
        if "timestamp" in entry:
            entry["timestamp"] = entry["timestamp"].isoformat()

    return jsonify({"results": entries})

@main.route("/edit_entry/<string:entry_id>", methods=["PUT"])
def edit_entry(entry_id):
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403
    
    data = request.json
    new_title = data.get("title")
    new_content = data.get("content")
    user_email = session.get("user_email")
    hashed_user_id = hashlib.sha256(user_email.encode()).hexdigest()

    updated_data = {
        "title": new_title,
        "content": new_content,
        "emotion": classify_text(new_content),
        "timestamp": datetime.now(timezone.utc)
    }

    result = db.entries.update_one(
        {"_id": ObjectId(entry_id), "user_id": hashed_user_id},
        {"$set": updated_data}
    )

    if result.matched_count == 0:
        return jsonify({"message": "Entry not found or unauthorized"}), 404

    return jsonify({"message": "Entry updated successfully"})

@main.route("/delete_entry/<string:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403

    user_email = session.get("user_email")
    hashed_user_id = hashlib.sha256(user_email.encode()).hexdigest()

    result = db.entries.delete_one({
        "_id": ObjectId(entry_id),
        "user_id": hashed_user_id
    })

    if result.deleted_count == 0:
        return jsonify({"message": "Entry not found or unauthorized"}), 404

    return jsonify({"message": "Entry deleted successfully"})"""

@main.route("/search_keyword", methods=["GET"])
def search_by_keyword():
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403

    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"message": "Please provide a keyword"}), 400
    
    escaped_keyword = re.escape(keyword)

    user_email = session.get("user_email")
    hashed_user_id=hashlib.sha256(user_email.encode()).hexdigest()

    search_filter = {
    "user_id": hashed_user_id,
    "$or": [
        {"title": {"$regex": keyword, "$options": "i"}},
        {"content": {"$regex": keyword, "$options": "i"}}
    ]
}
    
    # Fetch only relevant fields: Exclude _id for cleaner response
    user_entries = list(db.entries.find(search_filter, {"_id": 0, "user_id": 1, "title": 1, "content": 1, "timestamp": 1}))  
    
    for entry in user_entries:
        if "timestamp" in entry:
            entry["timestamp"] = entry["timestamp"].isoformat()

    if not user_entries:
        return jsonify({"message": "No matching entries found."})

    return jsonify({"results": user_entries})

#searching for date
from bson.regex import Regex

@main.route("/search_date", methods=["GET"])
def search_by_date():
    if not session.get("logged_in"):
        return jsonify({"message": "Unauthorized"}), 403

    user_id = session.get("user_email")
    hashed_user_id = hashlib.sha256(user_id.encode()).hexdigest()
    date_str = request.args.get("date", "")

    if not date_str:
        return jsonify({"message": "Please select a date"}), 400

    try:
        # Convert date string to a datetime object
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        start_date = datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0)
        end_date = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59, 999999)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    search_filter = {
        "user_id": hashed_user_id,
        "timestamp": {"$gte": start_date, "$lt": end_date}
    }

    results = list(db.entries.find(search_filter, {"_id": 0}))

    if not results:
        return jsonify({"message": "No matching entries found."})

    return jsonify({"results": results})

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
    detected_emotion = classify_text(user_input)

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
