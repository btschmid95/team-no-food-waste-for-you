import re
import nltk

# ensure nltk resources available
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

def normalize(text):
    units = r'\b(?:lb|lbs|pounds?|oz|ounces?|kg|g|grams?|tsp.|ct|count)\b|%'
    packaging = r'\b(?:concentrate|packet(?:s)?|pouch(?:es)?|bottle|jar|tub|container|bag|box|carton|pack(?:s)?)\b'
    fluff = r'\b(?:organic|favorite|fresh|freeze-dried|large|les|natural|petite|petites|raw|teeny|tiny)\b'
    allowed_tokens = {'?', '!', '&', 'with', 'and', 'or', 'in'}

    # Clean TJ branding + any parenthetical content
    text = re.sub(r"(TJ[’']?s|Joe[’']?s|Joseph[’']?s)", "", text, flags=re.I)
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\b\d+(\.\d+)?\b', '', text)
    text = re.sub(units, '', text, flags=re.I)
    text = re.sub(packaging, '', text, flags=re.I)
    text = re.sub(fluff, '', text, flags=re.I)
    text = re.sub(r'\s{2,}', ' ', text).strip()

    tokens = nltk.word_tokenize(text)
    pos_tags = nltk.pos_tag(tokens)

    keep = []
    lower_tokens = [t.lower() for t in tokens]

    for i, (word, tag) in enumerate(pos_tags):
        lw = word.lower()
        if tag.startswith('NN'): keep.append(lw)
        elif tag == 'JJ' and i + 1 < len(pos_tags) and pos_tags[i+1][1].startswith('NN'):
            keep.append(lw)
        elif lw in allowed_tokens: keep.append(lw)

    # Special cases
    if 'olive' in lower_tokens and 'oil' in lower_tokens and 'popcorn' not in lower_tokens:
        if 'spray' in lower_tokens:
            return 'extra virgin olive oil spray'
        return 'extra virgin olive oil'

    if {'all', 'purpose', 'flour'} <= set(lower_tokens):
        return 'all purpose flour'

    return ' '.join(keep) if keep else text.lower()
