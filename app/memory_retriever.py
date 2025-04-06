import chromadb
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import os
import hashlib
from datetime import datetime
import pprint

GEMINI_API_KEY = 'Your_API_Key'

# Setup MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["memoir_db"]
memories_collection = db["entries"]

# Setup ChromaDB
chroma_client = chromadb.PersistentClient(path="./memories_db")
memory_collection = chroma_client.get_or_create_collection(name="user_memories")
# Fetch all stored memories from ChromaDB
all_stored_memories = memory_collection.get()

"""# Check if there are existing memories
if all_stored_memories and "ids" in all_stored_memories:
    existing_ids = all_stored_memories["ids"]
    
    if existing_ids:
        print(f"🗑️ Deleting {len(existing_ids)} records from ChromaDB...")
        memory_collection.delete(existing_ids)
        print("✅ All memories have been deleted from ChromaDB!")
    else:
        print("🛑 No records found to delete.")
else:
    print("🛑 No records found in ChromaDB.")"""

print("ChromaDB initialized successfully!")

# Load embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model loaded successfully!")

# Google Gemini API (Use environment variable for security)
genai.configure(api_key=GEMINI_API_KEY)

# Function to store memories in ChromaDB
def generate_memory_id(text):
    return hashlib.md5(text.encode()).hexdigest()  # Unique ID for each memory text

# Function to detect emotion
def detect_emotion(user_input):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-002")
        prompt = f"Detect the emotion in the following user input: '{user_input}'. Respond with just the emotion (joy, sadness, anger, fear, anticipation, optimism, love, surprise, trust, pessimism, disgust)."
        response = model.generate_content(prompt)
        print(f"Raw response: {response.text}")
        return response.text.strip().lower()
    except Exception as e:
        print(f"⚠️ Error detecting emotion: {e}")
        return "neutral"

# Function to migrate memories from MongoDB to ChromaDB
# Function to migrate memories from MongoDB to ChromaDB with email in metadata
def migrate_memories(user_id):
    print("Migrate memories called")

    # Fetch all stored memories in ChromaDB
    all_stored_memories = memory_collection.get()
    stored_texts = set()

    # If there are stored memories, collect their texts
    if all_stored_memories and "metadatas" in all_stored_memories:
        stored_texts = {meta["text"] for meta in all_stored_memories["metadatas"]}

    print(f"📂 Existing memories in ChromaDB: {len(stored_texts)}")

    # Fetch memories from MongoDB
    memories = list(memories_collection.find({}))
    print(f"🔍 Found {len(memories)} memories in MongoDB.")

    # Step 2: Add updated memories with email to ChromaDB
    for memory in memories:
        memory_text = memory.get("content", "").strip()
        if not memory_text:
            continue  # Skip empty memories

        # Check if this exact memory already exists
        if memory_text in stored_texts:
            print(f"✅ Memory already exists, skipping: {memory_text}")
            continue

        # Generate unique ID
        memory_id = generate_memory_id(memory_text)
        embedding = embedding_model.encode(memory_text).tolist()
        emotion = detect_emotion(memory_text)

        # Get timestamp from MongoDB or use current time
        timestamp = memory.get("created_at", datetime.now()).isoformat()

        # Include the user's email in the metadata
        user_email = user_id  # Add email from MongoDB

        print(f"➕ Adding new memory to ChromaDB: {memory_text}")

        memory_collection.add(
            ids=[memory_id],  # Use unique hashed ID
            embeddings=[embedding],
            metadatas=[{
                "user_id": str(memory["_id"]), 
                "text": memory_text, 
                "emotion": emotion, 
                "timestamp": timestamp,
                "email": user_email  # Include email in metadata
            }]
        )

    print("🚀 Migration completed with emails included!")
    print(memory_collection.get())

# Function to retrieve happy memories based on user's emotion
# Function to retrieve memories based on user's emotion
def retrieve_memory(user_id, emotion, user_input):
    # Fetch all memories stored in ChromaDB
    all_stored_memories = memory_collection.get()
    if not all_stored_memories or "metadatas" not in all_stored_memories:
        return "No memories found in the database."
    opposite_emotion = {
        "sadness": "joy", "anger": "joy", "pessimism": "optimism",
        "fear": "trust", "disgust": "love", "surprise": "anticipation"
    }.get(emotion, "joy")

    # Filter memories based on user's emotion
    relevant_memories = []
    for meta in all_stored_memories["metadatas"]:
        print(f'user id of texts: {meta["user_id"]}')
        if meta["emotion"] == opposite_emotion and meta["user_id"] == user_id:  # Compare with actual user_id in metadata
            relevant_memories.append(meta)
    print(f"Emotion requested: {emotion}")
    print(f"opp Emotion requested: {opposite_emotion}")
    print(f'hello user id:{user_id}')
    print(f"Relevant memories found: {relevant_memories}")

    # If no relevant memories are found, return a message
    if not relevant_memories:
        return "No relevant memories found."

    # Sort memories by timestamp in ascending order (chronological)
    relevant_memories_sorted = sorted(relevant_memories, key=lambda x: x["timestamp"])

    # Get the list of memory texts in chronological order
    sorted_memory_texts = [meta["text"] for meta in relevant_memories_sorted]

    # Join them into a string to display in the response
    memories_string = "\n".join(sorted_memory_texts)

    return memories_string

# Chat with user
def chat_with_user(user_id, user_input, happy_memory_provided=False):
    emotion = detect_emotion(user_input)
    migrate_memories(user_id)
    model = genai.GenerativeModel("gemini-1.5-pro-002")  # Uncomment Gemini API call when ready

    if emotion in ["sadness", "anger", "pessimism", "fear", "disgust"]:
        memory = retrieve_memory(user_id, emotion, user_input)
        prompt = f"The user is feeling {emotion}. Respond with a comforting message and share this memory: '{memory}'. Tell that the memory hopefully makes them feel better and say goodbye."
        response = model.generate_content(prompt)
        return response.text.strip(), False  # Return the response, and False to indicate happy memory not provided.
    else:
        if happy_memory_provided:
            return "I'm so glad you shared that happy memory❤. Remember, I'm here for you, always. Take care😊. Goodbye.", False
        else:
            prompt = f"The user is feeling {emotion}. Respond with a short, encouraging message and ask a line about their happy moment."
            response = model.generate_content(prompt)
            return response.text.strip(), True  # Return the response and True to indicate happy memory is expected.
