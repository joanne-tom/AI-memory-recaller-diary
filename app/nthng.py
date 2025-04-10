import chromadb
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import os
import random

GEMINI_API_KEY = 'AIzaSyDdi_Bq17ZUBMwfa_PaCixRUqO5TCTogUs'

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
    print(f"🔍 Found {len(memories)} memories in MongoDB.")

    for memory in memories:
        user_id = str(memory["_id"])
        memory_text = memory.get("text", "").strip()

        if not memory_text:
            print(f"⚠️ Skipping empty memory with ID {user_id}")
            continue

        # Correct way to check if memory exists in ChromaDB
        existing_memories = memory_collection.query(
            query_texts=[memory_text],
            n_results=1,
            where={"user_id": user_id}  # Filtering by user_id
        )

        if existing_memories["ids"]:  # Check if any memory already exists
            print(f"✅ Memory {user_id} already stored. Skipping.")
            continue  # Skip already stored memories

        embedding = embedding_model.encode(memory_text).tolist()
        emotion = detect_emotion(memory_text)

        print(f"Detected Emotion: {emotion}") #debug line.

        # Storing memory in ChromaDB
        memory_collection.add(
            ids=[user_id],
            embeddings=[embedding],
            metadatas=[{"user_id": user_id, "text": memory_text, "emotion": emotion}]
        )
        print(f"Memory added to ChromaDB: {user_id}") #debug line.

    print("🚀 Migration completed!")

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
        print(f"Metadata: {metadata}") #debug line.
        if metadata["emotion"] == opposite_emotion:
            happy_memories.append(metadata["text"])

    if not happy_memories:
        return "No relevant memories found."

    # Retrieve relevant memories using embeddings
    results = memory_collection.query(
        query_texts=[""],  # Empty string returns all
        n_results=10,  # Adjust as needed
        where={"user_id": user_id}  # Filter by user
    )
    print(f"Retrieving memories for user: {user_id}, Emotion: {emotion}") #debug line.
    print(f"ChromaDB Query Results: {results}") #debug line.

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
def chat_with_user(user_id, user_input, happy_memory_provided=False):
    emotion = detect_emotion(user_input)
    migrate_memories()
    model = genai.GenerativeModel("gemini-1.5-pro-002")

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