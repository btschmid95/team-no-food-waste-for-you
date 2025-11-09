import pandas as pd

df = pd.read_csv("data/trader_joes_products_v3.csv")
df = df[['product_name', 'category', 'sub_category']].dropna()
print(df.head())

from sklearn.model_selection import train_test_split

# Combine sub-category and product name for context (assuming you have a 'sub_category' column)
df['text'] = df.apply(lambda row: f"{row['sub_category']} {row['product_name']}", axis=1)

# Train on sub-category
train_texts, test_texts, train_labels, test_labels = train_test_split(
    df['text'].tolist(),
    df['sub_category'].tolist(),
    test_size=0.2,
    random_state=42
)

from sklearn.preprocessing import LabelEncoder

label_encoder = LabelEncoder()
train_labels_enc = label_encoder.fit_transform(train_labels)
test_labels_enc = label_encoder.transform(test_labels)

from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset

# Convert to HF Dataset
train_dataset = Dataset.from_dict({'text': train_texts, 'label': train_labels_enc})
test_dataset = Dataset.from_dict({'text': test_texts, 'label': test_labels_enc})

# Tokenizer
model_name = "distilbert-base-uncased"  # small and fast
tokenizer = AutoTokenizer.from_pretrained(model_name)

def tokenize(batch):
    return tokenizer(batch['text'], padding='max_length', truncation=True, max_length=64)


train_dataset = train_dataset.map(tokenize, batched=True)
test_dataset = test_dataset.map(tokenize, batched=True)

# Set format for PyTorch
train_dataset.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
test_dataset.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])

# Model
from transformers import AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=len(label_encoder.classes_)
)

training_args = TrainingArguments(
    output_dir="./tj_product_classifier",
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    eval_strategy="epoch",
    save_strategy="epoch",
    num_train_epochs=10,
    logging_dir="./logs",
    logging_steps=50
)

from transformers import Trainer

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset
)

trainer.train()

from pathlib import Path
import joblib

MODEL_DIR = Path("models/tj_product_classifier")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Save model + tokenizer
model.save_pretrained(MODEL_DIR)
tokenizer.save_pretrained(MODEL_DIR)

# Save label encoder
joblib.dump(label_encoder, MODEL_DIR / "label_encoder.pkl")

from torch.nn.functional import softmax
import torch

def classify_ingredient_subcat(ingredient_name, top_k=3):
    """
    Predict top sub-categories for a product name.
    Returns a list of tuples: (sub_category, main_category, probability)
    """
    inputs = tokenizer(ingredient_name, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = softmax(logits, dim=1)
    
    top_probs, top_indices = torch.topk(probs, k=top_k)
    top_subcats = [label_encoder.classes_[i] for i in top_indices[0]]
    top_scores = top_probs[0].tolist()

    results = []
    for subcat, score in zip(top_subcats, top_scores):
        # Lookup main category from dataframe
        main_cat = df[df['sub_category'] == subcat]['category'].iloc[0]
        results.append((subcat, main_cat, score))
    
    return results

# ---- Example predictions ----
print(classify_ingredient_subcat("Mashed Sweet Potatoes"))
print(classify_ingredient_subcat("Pork Tenderloin"))
print(classify_ingredient_subcat("Egg"))
print(classify_ingredient_subcat("Large Egg"))
print(classify_ingredient_subcat("Pico de Gallo"))