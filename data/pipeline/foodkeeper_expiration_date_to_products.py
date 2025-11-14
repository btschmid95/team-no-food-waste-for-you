import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch
from collections import Counter

fk_products = pd.read_excel("data/FoodKeeper-Data.xls", sheet_name="Product").fillna('')
fk_categories = pd.read_excel("data/FoodKeeper-Data.xls", sheet_name="Category").fillna('')
fk_products = fk_products.merge(fk_categories, left_on='Category_ID', right_on='ID', how='left')

def build_fk_text(row):
    parts = [str(row['Category_Name']), str(row['Subcategory_Name']), str(row['Name']), str(row['Keywords'])]
    return " ".join([p for p in parts if p])

fk_products['text'] = fk_products.apply(
    lambda row: " ".join([
        str(row['Name']),
        str(row['Name_subtitle']) if pd.notna(row['Name_subtitle']) else "",
        str(row['Keywords']).replace(",", " ") if pd.notna(row['Keywords']) else ""
    ]).lower(),
    axis=1
)

fk_products['Keywords'] = np.where(fk_products['Keywords'] == '', fk_products['Name'], fk_products['Keywords'])

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

def map_tj_to_fk_category(tj_category, tj_subcategory):
    cat_map = tj_to_fk_mapping.get(tj_category, {})
    if tj_subcategory in cat_map:
        return cat_map[tj_subcategory]

    if tj_category in tj_to_fk_mapping and len(tj_to_fk_mapping[tj_category]) > 0:
        first_fk = next(iter(tj_to_fk_mapping[tj_category].values()))
        return first_fk


    return ("Unknown", "")


tj_df = pd.read_csv("data/trader_joes_products_v3.csv")
tj_df = tj_df[['product_name', 'category', 'sub_category']]


tj_df[['FK_Category', 'FK_Subcategory']] = tj_df.apply(
    lambda r: pd.Series(map_tj_to_fk_category(r['category'], r['sub_category'])),
    axis=1
)
tj_df['product_name_lower'] = tj_df['product_name'].str.lower()

model = SentenceTransformer('all-MiniLM-L6-v2')
fk_products['embedding'] = fk_products['text'].apply(lambda x: model.encode(x, convert_to_tensor=True))

def match_fk_keywords(product_name_lower, fk_cat, fk_df, min_score=0):

    fk_filtered = fk_df[fk_df['Category_Name'] == fk_cat]
    if fk_filtered.empty:
        return None

    product_emb = model.encode(product_name_lower, convert_to_tensor=True)


    sims = torch.tensor([util.cos_sim(product_emb, emb).item() for emb in fk_filtered['embedding']])
    best_idx = torch.argmax(sims).item()
    
    if sims[best_idx] < min_score:
        return None
    
    return fk_filtered.iloc[best_idx]

def parse_max_expiration(max_val, metric):
    if pd.isna(max_val) or not metric:
        return None
    metric = metric.lower().strip()
    if metric.startswith('day'):
        return pd.Timedelta(days=max_val)
    elif metric.startswith('week'):
        return pd.Timedelta(weeks=max_val)
    elif metric.startswith('month'):
        return pd.Timedelta(days=max_val*30)
    elif metric.startswith('year'):
        return pd.Timedelta(days=max_val*365)
    return None

purchase_date = pd.Timestamp('2025-11-09')

def get_default_storage_type(fk_cat):
    """Return preferred storage type for a category."""
    if not fk_cat:
        return ['Refrigerate', 'Pantry', 'Freeze']

    fk_cat_lower = fk_cat.lower()

    if "frozen" in fk_cat_lower:
        return ['Freeze', 'Refrigerate', 'Pantry']

    pantry_first = ["grains, beans & pasta", "shelf stable foods", "condiments, sauces & canned goods"]
    if fk_cat_lower in pantry_first:
        return ['Pantry', 'Refrigerate', 'Freeze']

    return ['Refrigerate', 'Pantry', 'Freeze']

def assign_expiration_priority(row):
    fk_row = row.get('fk_match', {}) or {}
    fk_cat = row.get('FK_Category')

    if fk_cat in category_defaults:
        defaults = category_defaults[fk_cat]

        for pref in ['Refrigerate', 'Pantry', 'Freeze']:
            if f"{pref}_Max" not in fk_row or pd.isna(fk_row.get(f"{pref}_Max")):
                if pref in defaults:
                    fk_row[f"{pref}_Max"] = defaults[pref]['shelf_life_days']
                    fk_row[f"{pref}_Metric"] = 'Days'

    storage_order = get_default_storage_type(fk_cat) if fk_cat else ['Refrigerate', 'Pantry', 'Freeze']

    for col_prefix in storage_order:
        max_val_col = f"{col_prefix}_Max"
        metric_col = f"{col_prefix}_Metric"
        val = fk_row.get(max_val_col)
        metric = fk_row.get(metric_col)

        if pd.isna(val) or not metric:
            continue

        exp = parse_max_expiration(val, metric)
        if exp is not None:
            return {
                "shelf_life": val,
                "shelf_life_unit": metric,
                "expiration_offset": exp,
                "Expiration_Date": purchase_date + exp
            }

    return pd.NA

for prefix in ['Pantry', 'Refrigerate', 'Freeze',
               'Pantry_After_Opening', 'Refrigerate_After_Opening',
               'Refrigerate_After_Thawing', 'DOP_Pantry', 'DOP_Refrigerate', 'DOP_Freeze']:
    for suffix in ['Min', 'Max', 'Metric']:
        col = f"{prefix}_{suffix}"
        if col in fk_products.columns:
            fk_products[col] = fk_products[col].replace('', pd.NA)


def max_to_days(val, metric):
    if pd.isna(val) or not metric:
        return np.nan
    metric = str(metric).lower().strip()
    if metric.startswith('day'):
        return val
    elif metric.startswith('week'):
        return val * 7
    elif metric.startswith('month'):
        return val * 30
    elif metric.startswith('year'):
        return val * 365
    return np.nan

category_defaults = {}

for cat in fk_products['Category_Name'].unique():
    cat_rows = fk_products[fk_products['Category_Name'] == cat]
    defaults = {}
    
    for col_prefix in ['Refrigerate', 'Pantry', 'Freeze']:
        max_col = f"{col_prefix}_Max"
        metric_col = f"{col_prefix}_Metric"
        
        if max_col in cat_rows.columns and metric_col in cat_rows.columns:
            days_series = cat_rows.apply(lambda r: max_to_days(r[max_col], r[metric_col]), axis=1)
            avg_days = days_series.mean(skipna=True)
            
            if not np.isnan(avg_days):
                defaults[col_prefix] = {'shelf_life_days': avg_days}
    
    if defaults:
        category_defaults[cat] = defaults

for cat, vals in category_defaults.items():
    print(cat)
    print(vals)

def safe_match_fk_keywords(product_name_lower, fk_cat, fk_df, min_score=0):
    row = match_fk_keywords(product_name_lower, fk_cat, fk_df, min_score=min_score)
    if row is not None:
        return row.to_dict()

    if fk_cat in category_defaults:
        defaults = category_defaults[fk_cat]
        storage_order = get_default_storage_type(fk_cat)

        fk_row = {}
        for pref in ['Refrigerate', 'Pantry', 'Freeze']:
            if pref in defaults:
                fk_row[f"{pref}_Max"] = defaults[pref]['shelf_life_days']
                fk_row[f"{pref}_Metric"] = 'Days'

        return {**fk_row, "Category_Name": fk_cat, "Name": product_name_lower, "text": product_name_lower}

    return pd.NA
tj_df['fk_match'] = tj_df.apply(
    lambda r: safe_match_fk_keywords(r['product_name_lower'], r['FK_Category'], fk_products),
    axis=1
)

tj_df['expiration_info'] = tj_df.apply(assign_expiration_priority, axis=1)

expiration_df = tj_df['expiration_info'].apply(lambda x: pd.Series(x) if pd.notna(x) else pd.Series({
    "shelf_life": pd.NA,
    "shelf_life_unit": pd.NA,
    "expiration_offset": pd.NaT,
    "Expiration_Date": pd.NaT
}))

tj_df = pd.concat([tj_df, expiration_df], axis=1)


tj_file = r"data\trader_joes_products_v3.csv"
original_df = pd.read_csv(tj_file)

shelf_life_df = tj_df[['product_name', 'shelf_life', 'shelf_life_unit']]

merged_df = original_df.merge(shelf_life_df, on='product_name', how='left')

output_file = r"data\trader_joes_products_v3_with_shelf_life.xlsx"
merged_df.to_excel(output_file, index=False)


print(f"Saved merged TJ products with shelf life to {output_file}")

print(merged_df[['product_name', 'shelf_life', 'shelf_life_unit']].head(10))

print(tj_df[['product_name', 'FK_Category', 'shelf_life', 'shelf_life_unit', 'Expiration_Date']].head(10))



# print(fk_products[fk_products['Name'].str.contains('Lemon', case=False)])
# print(fk_products[fk_products['text'].str.contains('lemon')])