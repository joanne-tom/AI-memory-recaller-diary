import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
from transformers import pipeline
classifier=pipeline('text-classification',model='ayoubkirouane/BERT-Emotions-Classifier')
def classify_text(text):
    result=classifier(text)
    return result[0]