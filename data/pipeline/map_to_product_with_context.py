import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import argparse
import os
import torch
from rapidfuzz import fuzz

import re

def map_to_product_top_n_sub_main_expanded(
    ing_df, prod_df, output_path, tight_threshold=0.7, loose_threshold=0.7, top_n=3
):
    model = SentenceTransformer('all-mpnet-base-v2')

    fluff_regex = re.compile(
        r'\b(?:organic|favorite|fresh|freeze-dried|large|les|natural|petite|petites|raw|teeny|tiny)\b',
        flags=re.IGNORECASE
    )
    def clean_text(text):
        if not isinstance(text, str):
            return ""
        #text = fluff_regex.sub("", text)
        #text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()

    def token_overlap_score(ing_name, prod_name):
        ing_tokens = set(ing_name.split())
        prod_tokens = set(prod_name.split())
        if not ing_tokens:
            return 0.0
        return len(ing_tokens & prod_tokens) / len(ing_tokens)

    prod_df['clean_name'] = prod_df['product_name'].apply(clean_text)

    subcat_to_main = prod_df.set_index('sub_category')['category'].to_dict()
    prod_df['context_name'] = prod_df.apply(
        lambda r: f"{r['clean_name']} in category {r['sub_category']}", axis=1
    )

    subcat_embeddings = {}
    for subcat in prod_df['sub_category'].unique():
        subset = prod_df[prod_df['sub_category'] == subcat]
        prod_df['context_name'] = prod_df.apply(
            lambda r: f"{r['clean_name']} in category {r['sub_category']}", axis=1
        )
        subcat_embeddings[subcat] = {
            "df": subset,
            "emb": model.encode(subset['context_name'].tolist(), convert_to_tensor=True),
            "main_category": subcat_to_main.get(subcat)
        }

    maincat_embeddings = {}
    for main_cat in prod_df['category'].unique():
        subset = prod_df[prod_df['category'] == main_cat]
        maincat_embeddings[main_cat] = {
            "df": subset,
            "emb": model.encode(subset['context_name'].tolist(), convert_to_tensor=True)
        }

    all_prod_embs = model.encode(prod_df['context_name'].tolist(), convert_to_tensor=True)
    all_prod_dfs = prod_df.reset_index(drop=True)

    matched_products, match_scores, units_list, categories_list = [], [], [], []

    for _, row in ing_df.iterrows():
        ing_name_clean = clean_text(row['name'])
        ing_emb = model.encode(
            f"{ing_name_clean} as an ingredient in the recipe '{row.get('recipe_title', '')}'"
            f" categorized as '{row.get('recipe_category', '')}'",
            convert_to_tensor=True
        )
        ing_subcategories = [
            row.get('likely_sub_category_1'),
            row.get('likely_sub_category_2'),
            row.get('likely_sub_category_3')
        ]

        top_matches = []

        for subcat in ing_subcategories:
            if not subcat:
                continue

            if subcat in subcat_embeddings:
                info = subcat_embeddings[subcat]
                cos_scores = util.cos_sim(ing_emb, info['emb']).cpu().numpy().flatten()

                adjusted_scores = []
                for j, prod_row in enumerate(info['df'].itertuples()):
                    overlap = token_overlap_score(ing_name_clean, prod_row.clean_name)
                    adjusted_scores.append(cos_scores[j] + 0.1 * overlap)

                idx_sorted = np.argsort(-np.array(adjusted_scores))
                for idx in idx_sorted:
                    if adjusted_scores[idx] >= tight_threshold:
                        prod_row = info['df'].iloc[idx]
                        if prod_row['product_name'] not in [m['product_name'] for m in top_matches]:
                            top_matches.append({
                                "product_name": prod_row['product_name'],
                                "unit": prod_row['unit'],
                                "category": subcat,
                                "score": adjusted_scores[idx]
                            })
                    if len(top_matches) >= top_n:
                        break

            main_cat = subcat_embeddings.get(subcat, {}).get("main_category")
            if main_cat and main_cat in maincat_embeddings:
                info = maincat_embeddings[main_cat]
                cos_scores = util.cos_sim(ing_emb, info['emb']).cpu().numpy().flatten()

                adjusted_scores = []
                for j, prod_row in enumerate(info['df'].itertuples()):
                    overlap = token_overlap_score(ing_name_clean, prod_row.clean_name)
                    adjusted_scores.append(cos_scores[j] + 0.2 * overlap)

                idx_sorted = np.argsort(-np.array(adjusted_scores))
                for idx in idx_sorted:
                    if adjusted_scores[idx] >= tight_threshold:
                        prod_row = info['df'].iloc[idx]
                        if prod_row['product_name'] not in [m['product_name'] for m in top_matches]:
                            top_matches.append({
                                "product_name": prod_row['product_name'],
                                "unit": prod_row['unit'],
                                "category": prod_row['category'],
                                "score": adjusted_scores[idx]
                            })
                    if len(top_matches) >= top_n:
                        break

            if len(top_matches) >= top_n:
                break

        if len(top_matches) < top_n:
            cos_scores = util.cos_sim(ing_emb, all_prod_embs).cpu().numpy().flatten()
            adjusted_scores = []
            for j, prod_row in enumerate(info['df'].itertuples()):
                overlap = token_overlap_score(ing_name_clean, prod_row.clean_name)
                adjusted_scores.append(cos_scores[j] + 0.1 * overlap)

            idx_sorted = np.argsort(-np.array(adjusted_scores))
            for idx in idx_sorted:
                if adjusted_scores[idx] >= loose_threshold:
                    prod_row = all_prod_dfs.iloc[idx]
                    if prod_row['product_name'] not in [m['product_name'] for m in top_matches]:
                        top_matches.append({
                            "product_name": prod_row['product_name'],
                            "unit": prod_row['unit'],
                            "category": prod_row['category'],
                            "score": adjusted_scores[idx]
                        })
                if len(top_matches) >= top_n:
                    break

        if top_matches:
            fuzzy_scores = [
                fuzz.token_set_ratio(ing_name_clean.lower(), m['product_name'].lower())
                for m in top_matches
            ]
            top_matches = [
                m for _, m in sorted(zip(fuzzy_scores, top_matches), key=lambda x: x[0], reverse=True)
            ]

        matched_products.append("; ".join([m['product_name'] for m in top_matches]) if top_matches else np.nan)
        units_list.append("; ".join([u.lstrip('/') for u in [m['unit'] for m in top_matches]]) if top_matches else np.nan)
        categories_list.append("; ".join([m['category'] for m in top_matches]) if top_matches else np.nan)
        match_scores.append("; ".join([f"{m['score']:.3f}" for m in top_matches]) if top_matches else np.nan)

    ing_df['matched_products'] = matched_products
    ing_df['units'] = units_list
    ing_df['matched_categories'] = categories_list
    ing_df['match_scores'] = match_scores
    for idx, row in ing_df.iterrows():
        if pd.isna(row['matched_products']):
            similar_matches = []

            for _, mapped_row in ing_df.iterrows():
                if pd.notna(mapped_row['matched_products']):
                    similarity = token_overlap_score(clean_text(row['name']), clean_text(mapped_row['name']))
                    if similarity >= 0.66:
                        products = mapped_row['matched_products'].split("; ")
                        units = mapped_row['units'].split("; ") if pd.notna(mapped_row['units']) else [""]*len(products)
                        categories = mapped_row['matched_categories'].split("; ") if pd.notna(mapped_row['matched_categories']) else [""]*len(products)
                        scores = mapped_row['match_scores'].split("; ") if pd.notna(mapped_row['match_scores']) else ["0"]*len(products)
                        for p, u, c, s in zip(products, units, categories, scores):
                            similar_matches.append((p, u, c, s))

            if similar_matches:
                from collections import Counter
                prod_counter = Counter([p for p, _, _, _ in similar_matches])
                top_products = [p for p, _ in prod_counter.most_common(top_n)]

                final_matches = []
                final_units = []
                final_categories = []
                final_scores = []
                for p in top_products:
                    for mp, u, c, s in similar_matches:
                        if mp == p:
                            final_matches.append(mp)
                            final_units.append(u)
                            final_categories.append(c)
                            final_scores.append(s)
                            break

                ing_df.at[idx, 'matched_products'] = "; ".join(final_matches)
                ing_df.at[idx, 'units'] = "; ".join(final_units)
                ing_df.at[idx, 'matched_categories'] = "; ".join(final_categories)
                ing_df.at[idx, 'match_scores'] = "; ".join(final_scores)

    ing_df.to_csv(output_path, index=False)
    print(f"✅ Saved mapped file to: {output_path}")

if __name__ == '__main__':
    import os
    import pandas as pd
    import argparse

    parser = argparse.ArgumentParser(description='Map normalized ingredient names to product names with category filtering.')
    parser.add_argument('--ingredients', default=None,
                        help='Path to CSV file with normalized ingredient names (must have "norm_name" column).')
    parser.add_argument('--products', default=None,
                        help='Path to CSV file with product information (must have "product_name" and "unit" columns).')
    parser.add_argument('--output', default=None,
                        help='Path to save the mapped CSV file.')
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    ingredients_path = os.path.join(project_root, "parsed_raw_ingredients_all_mini_with_recipe_context_v2.csv")
    products_path = os.path.join(project_root, "data", "trader_joes_products_v3.csv")
    output_path = os.path.join(project_root, "data", "mapped_all_ingredients_mini_with_sub-context_brett_top_5_matches_with_enhanced-context_v3.csv")

    if args.ingredients:
        ingredients_path = args.ingredients
    if args.products:
        products_path = args.products
    if args.output:
        output_path = args.output

    ing_df = pd.read_csv(ingredients_path)
    prod_df = pd.read_csv(products_path)

    map_to_product_top_n_sub_main_expanded(ing_df, prod_df, output_path)
