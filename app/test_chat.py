from memory_retriever import chat_with_user

user_id = "joannetom22@gmail.com"
user_message = "I'm feeling very sad today."

response = chat_with_user(user_id, user_message)
print("Chat Response:", response)