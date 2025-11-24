import pandas as pd

df = pd.read_csv("data/trader_joes_products_v3.csv")
df = df[['product_name', 'category', 'sub_category']].dropna()
print(df.head())

foodkeeper_path = "data/FoodKeeper-Data.xls"

# Load the Product tab
fk_products = pd.read_excel(foodkeeper_path, sheet_name="Product")

fk_categories = pd.read_excel(foodkeeper_path, sheet_name="Category")

# Map Category_ID to Category_Name and Subcategory_Name
fk_cat_map = fk_categories.set_index("ID")[["Category_Name", "Subcategory_Name"]].to_dict(orient="index")

def get_category_names(cat_id):
    cat_info = fk_cat_map.get(cat_id, {"Category_Name": "", "Subcategory_Name": ""})
    return cat_info["Category_Name"], cat_info["Subcategory_Name"]

def build_text(row):
    cat_name, subcat_name = get_category_names(row["Category_ID"])
    parts = [cat_name, subcat_name, row["Name"]]
    
    if pd.notna(row.get("Name_subtitle")):
        parts.append(str(row["Name_subtitle"]))
    if pd.notna(row.get("Keywords")):
        parts.append(str(row["Keywords"]))
    
    # Ensure all parts are strings and strip extra spaces
    parts = [str(p).strip() for p in parts if p and str(p).strip()]
    
    return " ".join(parts)

fk_products["text"] = fk_products.apply(build_text, axis=1)
fk_products["sub_category"] = fk_products["Category_ID"].apply(lambda x: fk_cat_map[x]["Subcategory_Name"] if x in fk_cat_map else "Unknown")
fk_products["category"] = fk_products["Category_ID"].apply(lambda x: fk_cat_map[x]["Category_Name"] if x in fk_cat_map else "Unknown")


from sklearn.model_selection import train_test_split

# Combine sub-category and product name for context (assuming you have a 'sub_category' column)
# df['text'] = df.apply(
#     lambda r: f"{r['category']} {r['sub_category']} product: {r['product_name']}",
#     axis=1
# )

df['text'] = df.apply(lambda r: f"{r['category']} {r['sub_category']} product: {r['product_name']}", axis=1)

# Keep only necessary columns
tj_train = df[['text', 'sub_category', 'category']]

tj_to_fk_mapping = {
    "Fresh Fruits & Veggies": {
        "Fruits": ("Produce", "Fresh Fruits"),
        "Veggies": ("Produce", "Fresh Vegetables")
    },

    "Meat, Seafood & Plant-based": {
        "Beef, Pork & Lamb": ("Meat", "Fresh"),
        "Chicken & Turkey": ("Poultry", "Fresh"),
        "Fish & Seafood": ("Seafood", "Fresh"),
        "Plant-based Protein": ("Vegetarian Proteins", "")
    },

    "Bakery": {
        "Sliced Bread": ("Baked Goods", "Bakery"),
        "Loaves, Rolls, Buns": ("Baked Goods", "Bakery"),
        "Bagels": ("Baked Goods", "Bakery"),
        "Tortillas & Flatbreads": ("Baked Goods", "Bakery"),
        "Sweet Stuff": ("Baked Goods", "Bakery")
    },

    "Cheese": {
        "Slices, Shreds, Crumbles": ("Dairy Products & Eggs", ""),
        "Wedges, Wheels, Loaves, Logs": ("Dairy Products & Eggs", ""),
        "Cream and Creamy Cheeses": ("Dairy Products & Eggs", "")
    },

    "Dairy & Eggs": {
        "Milk & Cream": ("Dairy Products & Eggs", ""),
        "Butter": ("Dairy Products & Eggs", ""),
        "Yogurt": ("Dairy Products & Eggs", ""),
        "Eggs": ("Dairy Products & Eggs", "")
    },

    "Dips, Sauces & Dressings": {
        "Condiments": ("Condiments, Sauces & Canned Goods", ""),
        "BBQ, Pasta, Simmer": ("Condiments, Sauces & Canned Goods", ""),
        "Salsa & Hot Sauce": ("Condiments, Sauces & Canned Goods", ""),
        "Dip/Spread": ("Condiments, Sauces & Canned Goods", ""),
        "Dressing & Seasoning": ("Condiments, Sauces & Canned Goods", "")
    },

    "Fresh Prepared Foods": {
        "Salads, Soups & Sides": ("Deli & Prepared Foods", ""),
        "Wraps, Burritos & Sandwiches": ("Deli & Prepared Foods", ""),
        "Entrées & Center of Plate": ("Deli & Prepared Foods", ""),
        "Dessert & Sweets": ("Deli & Prepared Foods", "")
    },

    "From The Freezer": {
        "Appetizers": ("Food Purchased Frozen", ""),
        "Entrées & Sides": ("Food Purchased Frozen", ""),
        "Fruit & Vegetables": ("Food Purchased Frozen", ""),
        "Cool Desserts": ("Food Purchased Frozen", "")
    },

    "For the Pantry": {
        "Pastas & Grains": ("Grains, Beans & Pasta", ""),
        "Packaged Fish, Meat, Fruit & Veg": ("Shelf Stable Foods", ""),
        "Nut Butters & Fruit Spreads": ("Shelf Stable Foods", ""),
        "Oils & Vinegars": ("Shelf Stable Foods", ""),
        "For Baking & Cooking": ("Baked Goods", "Baking and Cooking"),
        "Spices": ("Condiments, Sauces & Canned Goods", ""),
        "Cereals": ("Grains, Beans & Pasta", ""),
        "Soup, Chili & Meals": ("Shelf Stable Foods", ""),
        "Honeys, Syrups & Nectars": ("Shelf Stable Foods", "")
    },

    "Snacks & Sweets": {
        "Chips, Crackers & Crunchy Bites": ("Shelf Stable Foods", ""),
        "Candies & Cookies": ("Shelf Stable Foods", ""),
        "Nuts, Dried Fruits, Seeds": ("Shelf Stable Foods", ""),
        "Bars, Jerky &… Surprises": ("Shelf Stable Foods", "")
    }
}


fk_to_tj_mapping = {}

for tj_main, sub_map in tj_to_fk_mapping.items():
    for tj_sub, (fk_main, fk_sub) in sub_map.items():
        if fk_main not in fk_to_tj_mapping:
            fk_to_tj_mapping[fk_main] = {}
        fk_to_tj_mapping[fk_main][fk_sub] = (tj_main, tj_sub)

def map_fk_to_tj(row):
    fk_main = row["category"]
    fk_sub = row["sub_category"]
    tj_main, tj_sub = "UNKNOWN_CATEGORY", "UNKNOWN_SUBCATEGORY"

    if fk_main in fk_to_tj_mapping:
        submap = fk_to_tj_mapping[fk_main]
        if fk_sub in submap:
            tj_main, tj_sub = submap[fk_sub]
        elif "" in submap:
            tj_main, tj_sub = submap[""]

    return pd.Series({"tj_main": tj_main, "tj_sub": tj_sub})

mapped_fk = fk_products.join(fk_products.apply(map_fk_to_tj, axis=1))

tj_train = df[['text', 'category', 'sub_category']]
mapped_fk['text'] = mapped_fk['text']  # reuse existing descriptive text
mapped_fk['category'] = mapped_fk['tj_main']
mapped_fk['sub_category'] = mapped_fk['tj_sub']

combined_df = pd.concat([tj_train, mapped_fk[['text', 'sub_category', 'category']]], ignore_index=True)

combined_df['sub_category'] = combined_df['sub_category'].fillna('UNKNOWN_SUBCATEGORY')

# Fill missing category similarly (optional)
combined_df['category'] = combined_df['category'].fillna('UNKNOWN_CATEGORY')

# Create a flag for rows we want to train on
combined_df['trainable'] = combined_df['sub_category'] != 'UNKNOWN_SUBCATEGORY'

# Split train/test using only trainable rows
trainable_df = combined_df[combined_df['trainable']]
# Train on sub-category
train_texts, test_texts, train_labels, test_labels = train_test_split(
    trainable_df['text'].tolist(),
    trainable_df['sub_category'].tolist(),
    test_size=0.2,
    random_state=42,
    stratify=trainable_df['sub_category']
)

from sklearn.preprocessing import LabelEncoder

label_encoder = LabelEncoder()
train_labels_enc = label_encoder.fit_transform(train_labels)
test_labels_enc = label_encoder.transform(test_labels)

from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset

train_dataset = Dataset.from_dict({'text': train_texts, 'label': train_labels_enc})
test_dataset = Dataset.from_dict({'text': test_texts, 'label': test_labels_enc})

model_name = "distilbert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name)

def tokenize(batch):
    return tokenizer(batch['text'], padding='max_length', truncation=True, max_length=128)


train_dataset = train_dataset.map(tokenize, batched=True)
test_dataset = test_dataset.map(tokenize, batched=True)

train_dataset.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
test_dataset.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])

from transformers import AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=len(label_encoder.classes_)
)

training_args = TrainingArguments(
    output_dir="models/tj_product_classifier",
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

model.save_pretrained(MODEL_DIR)
tokenizer.save_pretrained(MODEL_DIR)

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

        main_cat = df[df['sub_category'] == subcat]['category'].iloc[0]
        results.append((subcat, main_cat, score))
    
    return results

print(classify_ingredient_subcat("Mashed Sweet Potatoes"))
print(classify_ingredient_subcat("Pork Tenderloin"))
print(classify_ingredient_subcat("Egg"))
print(classify_ingredient_subcat("Large Egg"))
print(classify_ingredient_subcat("Pico de Gallo"))