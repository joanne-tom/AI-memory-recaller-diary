import chromadb
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import os
import random

GEMINI_API_KEY = 'AIzaSyCJMxfkxP-QRAcdVW6Jo8M1tSa37d-n0wY'

# Setup MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")  
db = mongo_client["memoir_db"]  
memories_collection = db["entries"]

# Setup ChromaDB
chroma_client = chromadb.PersistentClient(path="./memories_db")  
memory_collection = chroma_client.get_or_create_collection(name="user_memories")

# Load embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Google Gemini API (Use environment variable for security)
genai.configure(api_key=GEMINI_API_KEY)

# Function to detect emotion
def detect_emotion(user_input):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-002")
        prompt = f"Detect the emotion in the following user input: '{user_input}'. Respond with just the emotion (joy, sadness, anger, fear, anticipation, optimism, love, surprise, trust, pessimism, disgust)."
        response = model.generate_content(prompt)
        return response.text.strip().lower()
    except Exception as e:
        print(f"⚠️ Error detecting emotion: {e}")
        return "neutral"

# Function to store memories in ChromaDB
def migrate_memories():
    memories = list(memories_collection.find({}))  
    for memory in memories:
        user_id = str(memory["_id"])  
        memory_text = memory["text"]  

        # Check if memory is already in ChromaDB
        existing_memories = memory_collection.get(where={"user_id": user_id})
        if existing_memories["ids"]:
            continue  # Skip already stored memories

        embedding = embedding_model.encode(memory_text).tolist()
        emotion = detect_emotion(memory_text)

        memory_collection.add(
            ids=[user_id],
            embeddings=[embedding],  
            metadatas=[{"user_id": user_id, "text": memory_text, "emotion": emotion}]
        )
        print(f"✅ Memory stored: {memory_text} ({emotion})")

def retrieve_memory(user_id, emotion, user_input):
    # Define opposite emotions for better responses
    opposite_emotion = {
        "sadness": "joy", "anger": "joy", "pessimism": "optimism",
        "fear": "trust", "disgust": "love", "surprise": "anticipation"
    }.get(emotion, "joy")  # Default to "joy"

    # Debug step: Check stored memories
    all_memories = memory_collection.get(where={"user_id": user_id})
    print(f"🔍 All Memories Retrieved for {user_id}: {all_memories}")  # Debugging

    # Ensure we extract metadata properly
    happy_memories = []
    for metadata in all_memories["metadatas"]:  # Extract stored metadata
        if metadata["emotion"] == opposite_emotion:
            happy_memories.append(metadata["text"])

    if not happy_memories:
        return "No relevant memories found."

    # Retrieve relevant memories using embeddings
    results = memory_collection.query(
        query_embeddings=[embedding_model.encode(user_input).tolist()],  
        n_results=5,  
        where={"user_id": user_id}  
    )

    print(f"🔍 Query Results: {results}")  # Debugging

    # Ensure correct document structure
    filtered_results = []
    for i, metadata_list in enumerate(results["metadatas"]):
        for metadata in metadata_list:  # Each metadata_list contains multiple dicts
            if metadata["emotion"] == opposite_emotion:
                filtered_results.append(metadata["text"])

    if filtered_results:
        return random.choice(filtered_results)
    else:
        return "No relevant memories found."


# Chat with user
def chat_with_user(user_id, user_input):
    emotion = detect_emotion(user_input)
    if emotion in ["sadness", "anger", "pessimism", "fear", "disgust"]:
        memory = retrieve_memory(user_id, emotion, user_input)
        return f"I sense you're feeling {emotion}. Here’s a happy memory: {memory}"
    else:
        return "I'm glad you're feeling good! Tell me more!"
