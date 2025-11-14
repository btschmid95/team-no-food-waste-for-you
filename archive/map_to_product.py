import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import argparse


def map_to_product(ing_df, prod_df, output_path):
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L12-v2')

    ing_texts = ing_df['norm_name']
    prod_texts = prod_df['norm_name']

    ing_emb = model.encode(ing_texts, convert_to_tensor = True)
    prod_emb = model.encode(prod_texts, convert_to_tensor = True)

    cos_scores = util.cos_sim(ing_emb, prod_emb)
    cos_scores = cos_scores.cpu().numpy()

    best_match_idx = np.argmax(cos_scores, axis = 1)
    best_score = cos_scores[np.arange(len(ing_df)), best_match_idx]

    matched_products = []
    for ing_name, idx, score in zip(ing_df['norm_name'], best_match_idx, best_score):
        prod_name = prod_df.iloc[idx]['product_name']
        unit = prod_df.iloc[idx]['unit']
        category = prod_df.iloc[idx]['category']

        if score > 0.80:
            matched_products.append((prod_name, unit, category))
        # elif len(ing_name.split()) == 1:
        #     matched_products.append((ing_name, '1 Each', np.nan))
        else:
            matched_products.append((ing_name, np.nan, np.nan))

    ing_df['matched_product'] = [x[0] for x in matched_products]
    ing_df['match_score'] = best_score

    ing_df['unit'] = [x[1] for x in matched_products]
    ing_df['unit'] = ing_df['unit'].str.lstrip('/')

    ing_df['category'] = [x[2] for x in matched_products]

    ing_df.to_csv(output_path, index = False)
    print(f"Saved normalized CSV to {output_path}")   


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Map normalized ingredient names to product names and save the result.')
    parser.add_argument('ingredients', help = 'Path to CSV file with normalized ingredient names (must have "norm_name" column).')
    parser.add_argument('products', help = 'Path to CSV file with product information (must have "product_name" and "unit" columns).')
    parser.add_argument('output', help = 'Path to save the mapped CSV file.')
    args = parser.parse_args()

    ing_df = pd.read_csv(args.ingredients)
    prod_df = pd.read_csv(args.products)

    map_to_product(ing_df, prod_df, args.output)