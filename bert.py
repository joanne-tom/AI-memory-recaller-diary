from datasets import load_dataset
dataset=load_dataset("go_emotions")
#--import the tokenizer--
from transformers import BertTokenizer 
tokenizer=BertTokenizer.from_pretrained("bert-base-uncased")
def tokenizer_function(examples):
    return tokenizer(examples["text"],padding="max_length",truncation=True)
tokenized_datasets=dataset.map(tokenizer_function,batched=True)
#--load the pretrained bert model--
from transformers import BertForSequenceClassification
#--number of emotion lables(GoEmotions has 27)
num_labels=27
#--load the pretrained BERT for classification
model=BertForSequenceClassification.from_pretrained("bert-base-uncased",num_labels=num_labels,problem_type="multi_label_classification")
#Fine-tune BERT on GoEMotions
from transformers import TrainingArguments, Trainer
import torch

training_args = TrainingArguments(
    output_dir="./results",
    eval_strategy="epoch",
    save_strategy="epoch",
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=3,  # Adjust based on performance
    weight_decay=0.01,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["test"],
)

trainer.train()
trainer.evaluate()
import torch

def predict_emotion(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    outputs = model(**inputs)
    logits = outputs.logits
    predicted_class = torch.argmax(logits, dim=1)
    return predicted_class.item()
# Example prediction
text =input("hey!! how do you feel today!!")
emotion_label = predict_emotion(text)
print(f"Predicted Emotion Label: {emotion_label}")