import pandas as pd

from thefuzz import fuzz
from thefuzz import process

import argparse


def map_to_product(ing_df, prod_df, output_path):
    choices = prod_df['product_name'].to_dict()

    mapped_products = []
    for ing in ing_df['norm_name']:
        choice, score, idx = process.extractOne(ing, choices)
        unit = prod_df.loc[idx, 'unit']
        mapped_products.append((choice, score, unit))

    ing_df['product'] = [x[0] for x in mapped_products]

    ing_df['match_score'] = [x[1] for x in mapped_products]

    ing_df['unit'] = [x[2] for x in mapped_products]
    ing_df['unit'] = ing_df['unit'].str.lstrip('/')

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