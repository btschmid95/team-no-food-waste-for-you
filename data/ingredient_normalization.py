import pandas as pd

import nltk
from nltk import word_tokenize, pos_tag
import inflect
import argparse



def normalize(text):
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')

    # Get pos for each word
    tokens = nltk.word_tokenize(text)
    pos_tags = nltk.pos_tag(tokens)

    # Get all nouns
    nouns = [word for word, pos in pos_tags if pos.startswith('NN')]

    # Make all nouns singular  
    p = inflect.engine()
    singular_nouns = [p.singular_noun(word) or word for word in nouns]

    # Pull out main noun
    main_noun = singular_nouns[-1].lower()
    
    return main_noun

def normalize_csv(input_path, output_path, column = 'name'):
    df = pd.read_csv(input_path)

    df['norm_name'] = df['name'].apply(lambda text: normalize(text))

    df.to_csv(output_path, index = False)
    print(f"Saved normalized CSV to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Normalize product names from any CSV file')
    parser.add_argument('input', help = 'Path to input CSV file')
    parser.add_argument('output', help = 'Path to save normalized CSV')
    parser.add_argument('--column', default = 'name', help = "Column to normalize (default: 'name')")
    args = parser.parse_args()

    normalize_csv(args.input, args.output, args.column)