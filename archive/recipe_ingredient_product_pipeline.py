import re
from rapidfuzz import process, fuzz

# -------------------------
# 1️⃣ Normalization
# -------------------------
STOPWORDS = {
    'tjs',"tj's", 'tj', 'trader', 'joes', 'organic', 'fresh',
    'optional', 'favorite', 'your', 'own'
}

UNITS = [
    'tablespoon', 'tablespoons', 'tbsp', 'teaspoon', 'tsp',
    'cup', 'cups', 'package', 'pkg', 'stick', 'oz', 'ounce',
    'ounces', 'pound', 'lb', 'large', 'small', 'bag', 'box', 'container'
]

def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r".*?(tj[’']s|trader\s*joe[’']s)\s*", "", text)
    if ',' in text:
        text = text.split(',', 1)[0].strip()
    text = re.sub(r'^(?:\d+\s*/\s*\d+|\d+|½|¼|⅓|⅔|¾)\s*', '', text)
    for unit in UNITS:
        text = re.sub(r'\b' + unit + r'\b', '', text)
    text = re.sub(r'[^a-z0-9\s\'&]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r"^s\s+", "", text)
    tokens = [w for w in text.split() if w not in STOPWORDS]
    return ' '.join(tokens).strip()

def fuzzy_candidates_filtered(ingredient, candidates, limit=5, scorer=fuzz.token_set_ratio,
                              min_score=70, min_token_overlap=1):
    ingredient_norm = ingredient.lower().strip()
    ingredient_tokens = set(ingredient_norm.split())
    matches = process.extract(ingredient_norm, candidates, scorer=scorer, limit=limit)
    filtered = []
    for candidate, score, _ in matches:
        candidate_tokens = set(candidate.split())
        overlap = len(ingredient_tokens & candidate_tokens)
        if score >= min_score and overlap >= min_token_overlap:
            filtered.append((candidate, score, overlap))
    return filtered

def fuzzy_best_length(ingredient, candidates, limit=5, scorer=fuzz.token_set_ratio,
                      min_score=70, min_token_overlap=1):
    matches = fuzzy_candidates_filtered(ingredient, candidates, limit, scorer,
                                        min_score, min_token_overlap)
    if not matches:
        return []
    matches.sort(key=lambda x: (-x[1], abs(len(x[0]) - len(ingredient))))
    return matches

def fuzzy_match_best_filtered(ingredient, candidates, limit=5, scorer=fuzz.token_set_ratio,
                              min_score=70, min_token_overlap=1):
    matches = fuzzy_best_length(ingredient, candidates, limit, scorer, min_score, min_token_overlap)
    return matches[0][0] if matches else None

def process_ingredients(df, ingredient_col, products_list,
                        min_score=70, min_token_overlap=1):
    df['normalized_ingredients'] = df[ingredient_col].apply(
        lambda ing_list: [normalize_text(i) for i in ing_list]
    )
    df['base_ingredients'] = df[ingredient_col].apply(
        lambda ing_list: [i.split(',', 1)[0].strip() for i in ing_list]
    )
    df['preparation'] = df[ingredient_col].apply(
        lambda ing_list: [i.split(',', 1)[1].strip() if ',' in i else '' for i in ing_list]
    )
    df['fuzzy_candidates_list'] = df['normalized_ingredients'].apply(
        lambda ing_list: [
            fuzzy_best_length(i, products_list, min_score=min_score, min_token_overlap=min_token_overlap)
            for i in ing_list
        ]
    )
    df['matched_product'] = df['normalized_ingredients'].apply(
        lambda ing_list: [
            fuzzy_match_best_filtered(i, products_list, min_score=min_score, min_token_overlap=min_token_overlap)
            for i in ing_list
        ]
    )
    return df
