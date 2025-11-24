from pathlib import Path
import joblib
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from torch.nn.functional import softmax
import torch

MODEL_DIR = Path("models/tj_product_classifier")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
label_encoder = joblib.load(MODEL_DIR / "label_encoder.pkl")

categories = {
    "Fresh Fruits & Veggies": {
        "Fruits": "https://www.traderjoes.com/home/products/category/fruits-116",
        "Veggies": "https://www.traderjoes.com/home/products/category/veggies-119"
    },
    "Meat, Seafood & Plant-based": {
        "Beef, Pork & Lamb": "https://www.traderjoes.com/home/products/category/beef-pork-lamb-125",
        "Chicken & Turkey": "https://www.traderjoes.com/home/products/category/chicken-turkey-128",
        "Fish & Seafood": "https://www.traderjoes.com/home/products/category/fish-seafood-131",
        "Plant-based Protein": "https://www.traderjoes.com/home/products/category/plant-based-protein-134"
    },
    "Bakery": {
        "Sliced Bread": "https://www.traderjoes.com/home/products/category/sliced-bread-14",
        "Loaves, Rolls, Buns": "https://www.traderjoes.com/home/products/category/loaves-rolls-buns-17",
        "Bagels": "https://www.traderjoes.com/home/products/category/bagels-20",
        "Tortillas & Flatbreads": "https://www.traderjoes.com/home/products/category/tortillas-flatbreads-23",
        "Sweet Stuff": "https://www.traderjoes.com/home/products/category/sweet-stuff-26"
    },
    "Cheese": {
        "Slices, Shreds, Crumbles": "https://www.traderjoes.com/home/products/category/slices-shreds-crumbles-32",
        "Wedges, Wheels, Loaves, Logs": "https://www.traderjoes.com/home/products/category/wedges-wheels-loaves-logs-38",
        "Cream and Creamy Cheeses": "https://www.traderjoes.com/home/products/category/cream-and-creamy-cheeses-41"
    },
    "Dairy & Eggs": {
        "Milk & Cream": "https://www.traderjoes.com/home/products/category/milk-cream-47",
        "Butter": "https://www.traderjoes.com/home/products/category/butter-50",
        "Yogurt": "https://www.traderjoes.com/home/products/category/yogurt-etc-53",
        "Eggs": "https://www.traderjoes.com/home/products/category/eggs-56"
    },
    "Dips, Sauces & Dressings": {
        "Condiments": "https://www.traderjoes.com/home/products/category/condiments-62",
        "BBQ, Pasta, Simmer": "https://www.traderjoes.com/home/products/category/bbq-pasta-simmer-65",
        "Salsa & Hot Sauce": "https://www.traderjoes.com/home/products/category/salsa-hot-sauce-68",
        "Dip/Spread": "https://www.traderjoes.com/home/products/category/dipspread-71",
        "Dressing & Seasoning": "https://www.traderjoes.com/home/products/category/dressing-seasoning-74"
    },
    "Fresh Prepared Foods": {
        "Salads, Soups & Sides": "https://www.traderjoes.com/home/products/category/salads-soups-sides-83",
        "Wraps, Burritos & Sandwiches": "https://www.traderjoes.com/home/products/category/wraps-burritos-sandwiches-86",
        "Entrées & Center of Plate": "https://www.traderjoes.com/home/products/category/entrees-center-of-plate-89",
        "Dessert & Sweets": "https://www.traderjoes.com/home/products/category/dessert-sweets-92"
    },
    "From The Freezer": {
        "Appetizers": "https://www.traderjoes.com/home/products/category/appetizers-98",
        "Entrées & Sides": "https://www.traderjoes.com/home/products/category/entrees-sides-101",
        "Fruit & Vegetables": "https://www.traderjoes.com/home/products/category/fruit-vegetables-104",
        "Cool Desserts": "https://www.traderjoes.com/home/products/category/cool-desserts-107"
    },
    "For the Pantry": {
        "Pastas & Grains": "https://www.traderjoes.com/home/products/category/pastas-grains-140",
        "Packaged Fish, Meat, Fruit & Veg": "https://www.traderjoes.com/home/products/category/packaged-fish-meat-fruit-veg-143",
        "Nut Butters & Fruit Spreads": "https://www.traderjoes.com/home/products/category/nut-butters-fruit-spreads-146",
        "Oils & Vinegars": "https://www.traderjoes.com/home/products/category/oils-vinegars-149",
        "For Baking & Cooking": "https://www.traderjoes.com/home/products/category/for-baking-cooking-152",
        "Spices": "https://www.traderjoes.com/home/products/category/spices-155",
        "Cereals": "https://www.traderjoes.com/home/products/category/cereals-158",
        "Soup, Chili & Meals": "https://www.traderjoes.com/home/products/category/soup-chili-meals-161",
        "Honeys, Syrups & Nectars": "https://www.traderjoes.com/home/products/category/honeys-syrups-nectars-164"
    },
    "Snacks & Sweets": {
        "Chips, Crackers & Crunchy Bites": "https://www.traderjoes.com/home/products/category/chips-crackers-crunchy-bites-170",
        "Candies & Cookies": "https://www.traderjoes.com/home/products/category/candies-cookies-173",
        "Nuts, Dried Fruits, Seeds": "https://www.traderjoes.com/home/products/category/nuts-dried-fruits-seeds-176",
        "Bars, Jerky &… Surprises": "https://www.traderjoes.com/home/products/category/bars-jerky-surprises-179"
    }
}
sub_to_main_category = {}
for main_cat, subcats in categories.items():
    for sub_cat in subcats.keys():
        sub_to_main_category[sub_cat] = main_cat


def predict_category(ingredient_name, top_k=3):
    inputs = tokenizer(ingredient_name, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = softmax(logits, dim=1)

    k = min(top_k, probs.shape[1])
    top_probs, top_indices = torch.topk(probs, k=k)

    results = []
    for idx, score in zip(top_indices[0], top_probs[0]):
        sub_cat = label_encoder.classes_[idx]
        main_cat = sub_to_main_category.get(sub_cat, "Unknown")
        results.append((sub_cat, score.item(), main_cat))

    while len(results) < top_k:
        results.append((None, None, None))

    return results
