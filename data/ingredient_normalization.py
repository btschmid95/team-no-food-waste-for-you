import pandas as pd
import sqlite3
import re
import nltk
import argparse


def get_sql_table(input):
    conn = sqlite3.connect(input)
    df = pd.read_sql_query('SELECT * FROM ingredient', conn)
    df.to_csv('ingredients.csv', index = False)
    conn.close()


def normalize(text):
    units = r'\b(?:lb|lbs|pounds?|oz|ounces?|kg|g|grams?|tsp.|ct|count)\b|%'
    packaging = r'\b(?:concentrate|packet(?:s)?|pouch(?:es)?|bottle|jar|tub|container|bag|box|carton|pack(?:s)?)\b'
    fluff = r'\b(?:organic|favorite|fresh|freeze-dried|large|les|natural|petite|petites|raw|teeny|tiny)\b'
    allowed_tokens = {'?', '!', '&', 'with', 'and', 'or', 'in'}

    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')

    # Get rid of TJ's and any directions like ", divided"
    text = text.replace("TJ’s", "TJ's").replace("TJ's", "").replace("Joe's", "").replace("Joseph's", "").split(',')[0].strip()

    # Removes parentheses and contents
    text = re.sub(r'\([^)]*\)', '', text)

    # Remove standalone numbers
    text = re.sub(r'\b\d+(\.\d+)?\b', '', text)

    # Remove units
    text = re.sub(units, '', text, flags = re.I)

    # Remove packaging words
    text = re.sub(packaging, '', text, flags = re.I)

    # Remove words like 'organic' or 'fresh'
    text = re.sub(fluff, '', text, flags = re.I)

    # Collapse spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()

    # Get pos for each word
    tokens = nltk.word_tokenize(text)
    pos_tags = nltk.pos_tag(tokens)

    keep = []
    lower_tokens = [t.lower() for t in tokens]
    for i, (word, tag) in enumerate(pos_tags):
        if tag.startswith('NN'):
            keep.append(word.lower())

        # Keep adjective only if followed by a noun
        elif tag == 'JJ' and i + 1 < len(pos_tags) and pos_tags[i+1][1].startswith('NN'):
            keep.append(word.lower())

        # Keep things like ? or with
        elif word in allowed_tokens:
            keep.append(word.lower())

    if 'olive' in lower_tokens and 'oil' in lower_tokens and 'in' not in lower_tokens and 'popcorn' not in lower_tokens and len(lower_tokens) <= 5:
        if 'spray' in lower_tokens:
            return 'extra virgin olive oil spray'
        return 'extra virgin olive oil'
    
    if 'all' in lower_tokens and 'purpose' in lower_tokens and 'flour' in lower_tokens:
        return 'all purpose flour'

    return ' '.join(keep) if keep else text.lower()
    

def normalize_csv(ingredients_file, output_path, column = 'name'):
    df = pd.read_csv(ingredients_file)

    df['norm_name'] = df[column].apply(lambda text: normalize(text))

    df.to_csv(output_path, index = False)
    print(f"Saved normalized CSV to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Normalize product names from any CSV file')
    parser.add_argument('input', help = 'Path to input database')
    parser.add_argument('output', help = 'Path to save normalized CSV')
    parser.add_argument('--column', default = 'name', help = "Column to normalize (default: 'name')")
    args = parser.parse_args()

    get_sql_table(args.input)
    normalize_csv('trader_joes_products_v3.csv', args.output, args.column)