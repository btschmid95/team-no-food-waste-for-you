import numpy as np
import pandas as pd
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import StandardScaler

class HybridRecipeRecommender:
    def __init__(self, alpha=0.5, beta=0.3, gamma=0.2, random_state=42):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        
        self.model = SGDRegressor(random_state=random_state)
        self.scaler = StandardScaler()
        self._model_initialized = False

    def content_score(self, recipe, pantry):
        waste_score = 0
        for ing in recipe['ingredients']:
            if ing in pantry:
                days_to_exp = pantry[ing]['days_to_exp']
                waste_score += np.exp(-0.1 * days_to_exp)
        waste_score /= max(len(recipe['ingredients']), 1)
        
        ## gotta adjust that ##
        preference_score = 1.0 if recipe['category'] in ['Dinner', 'Lunch'] else 0.5
        
        target_calories = 2000
        calories = recipe.get('calories', 500)
        overproduction_risk = max(0, (calories - target_calories) / target_calories)
        
        score = self.alpha * waste_score + self.beta * preference_score - self.gamma * overproduction_risk
        return score

    def recommend(self, recipes_df, pantry, top_k=10):
        recipes_df['content_score'] = recipes_df.apply(lambda r: self.content_score(r, pantry), axis=1)
        
        if self._model_initialized:
            X = recipes_df[['content_score']].values
            X_scaled = self.scaler.transform(X)
            adjustment = self.model.predict(X_scaled)
            recipes_df['final_score'] = recipes_df['content_score'] + adjustment
        else:
            recipes_df['final_score'] = recipes_df['content_score']
        
        return recipes_df.sort_values('final_score', ascending=False).head(top_k)

    def update_feedback(self, recipes_df, feedback):
        """
        feedback: dict of recipe_id -> liked (1) / skipped (0)
        """
        X = recipes_df.loc[recipes_df.index.isin(feedback.keys()), ['content_score']].values
        y = np.array([feedback[rid] for rid in recipes_df.index if rid in feedback])
        
        X_scaled = self.scaler.fit_transform(X) if not self._model_initialized else self.scaler.transform(X)
        
        if not self._model_initialized:
            self.model.partial_fit(X_scaled, y)
            self._model_initialized = True
        else:
            self.model.partial_fit(X_scaled, y)
