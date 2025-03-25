from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from pymongo import MongoClient
from app.bert_emotions_classifier import classify_text

import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["your_database"]
entries_collection = db["entries"]

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

class ActionDetectEmotion(Action):
    def name(self):
        return "action_detect_emotion"

    def run(self, dispatcher, tracker, domain):
        user_message = tracker.latest_message.get("text")  # Get user input
        detected_emotion = classify_text(user_message)  # Use existing function
        return [SlotSet("emotion", detected_emotion)]
    
class ActionRetrieveMemories(Action):
    def name(self):
        return "action_retrieve_happy_memory"

    def run(self, dispatcher, tracker, domain):
        user_emotion = tracker.get_slot("emotion")  # Retrieve detected emotion from the slot

        search_emotions = OPPOSITE_EMOTIONS.get(user_emotion, [user_emotion])  # Ensure it's a list

        # Use MongoDB's `$in` operator to find memories for any of the opposite emotions in one query
        memories = list(entries_collection.find({"emotion": {"$in": search_emotions}}, {"_id": 0}))

        if memories:  # If found, return them
            memory_texts = "\n".join([mem["text"] for mem in memories])
            dispatcher.utter_message(text=f"Here are some memories to help you feel better:\n{memory_texts}")
        else:
            dispatcher.utter_message(text="You don't have any specific memories stored. Want to create one?")

        return []