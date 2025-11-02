import pandas as pd
import sqlite3
import re
import nltk
from nltk import word_tokenize, pos_tag
import inflect
import argparse


def get_sql_table(input):
    conn = sqlite3.connect(input)
    df = pd.read_sql_query('SELECT * FROM ingredient', conn)
    df.to_csv('ingredients.csv', index = False)
    conn.close()


def normalize(text):
    units = r'\b(?:lb|lbs|pounds?|oz|ounces?|kg|g|grams?|ct|count)\b|%'
    packaging = r'\b(?:concentrate|packet(?:s)?|pouch(?:es)?|bottle|jar|tub|container|bag|box|carton|pack(?:s)?)\b'
    fluff = r'\b(?:organic|favorite|fresh|freeze-dried|large|les|natural|petite|petites|raw|teeny|tiny)\b'

    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')

    original = str(text)

    # Get rid of TJ's and any directions like ", divided"
    text = text.replace("TJ’s", "TJ's").replace("TJ's", "").split(',')[0].strip()

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

    # ---- DEBUG: show state before tagging ----
    # (remove these prints when you’re satisfied)
    print(f"INPUT:   {original!r}")
    print(f"CLEANED: {text!r}")

    # Get pos for each word
    tokens = nltk.word_tokenize(text)
    pos_tags = nltk.pos_tag(tokens)
    
    # ---- DEBUG: show tokens/tags ----
    print("TAGS:", pos_tags)

    keep = []
    for i, (word, tag) in enumerate(pos_tags):
        if tag.startswith('NN'):
            keep.append(word)

        # Keep adjective only if followed by a noun
        elif tag == 'JJ' and i + 1 < len(pos_tags) and pos_tags[i+1][1].startswith('NN'):
            keep.append(word)

    # ---- DEBUG: what we decided to keep ----
    print("KEPT:", keep)

    return ' '.join(keep) if keep else text

    # # Get all nouns
    # nouns = [word for word, pos in pos_tags if pos.startswith('NN')]

    # Make all nouns singular  
    # p = inflect.engine()
    # singular_nouns = [p.singular_noun(word) or word for word in nouns]

    # # Pull out main noun
    # main_noun = singular_nouns[-1].lower()
    

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
    normalize_csv('ingredients.csv', args.output, args.column)