# 🥘 Team No Food Waste For You
### Streamlit Meal Planner • Pantry Tracker • Trader Joe’s Database

A full-stack system designed to **reduce household food waste** using Trader Joe’s products, structured recipes, and a virtual pantry system.

This project includes:

- 🗄️ A SQLite database containing Trader Joe’s product data, recipe ingredients, pantry stock, and usage logs
- 🥗 A Streamlit meal-planning and pantry-management application
- 🔄 A full ingredient-to-product matching pipeline
- 🧮 A recipe recommender system powered by waste-risk scoring
- 🤖 Supporting ML components (ingredient classifier, product classifier)

---

# 🚀 Running the Application

The application is self-contained and runs locally. Use the startup script for your operating system:

### **Windows**
```
team-no-food-waste-for-you\app_start.bat
```

### **Mac / Linux**
Before running:
```
chmod +x app_start.sh
```

Run:
```
./app_start.sh
```

Running the appropriate script will automatically:

- create a Python virtual environment
- install all required packages (first run: ~5–10 min)
- create the SQLite database (`team-no-food-waste-for-you.sqlite`)
- build tables defined in `database/tables.py`
- populate recipes, ingredients, and Trader Joe’s products
- execute all cleaning & parsing pipelines

After initial setup, future launches skip installation and start the Streamlit server immediately.

### **Startup Example**
<img src="images/Setup%20complete,%20launching%20streamlit.png" width="650">

---

# 🧭 Navigating the Streamlit App

The application is organized into **three main dashboards**, accessible from the left sidebar.

> 💡 *Tip: The Pantry Dashboard includes a **Sample Pantry** button that fills your pantry with realistic items and expiration dates for exploration.*

<img src="images/sidebar.png" width="280">

---

# 🏠 Home Dashboard

Provides a high-level overview of your current household food system.

## **Summary Statistics**
- **Total Pantry Items** — number of food items currently stored
- **Recipes Planned** — number of recipes scheduled
- **Next Meal Planned** — the next meal you're set to make
- **Meals Planned This Week** — weekly meal count

## **Waste & Pantry Analytics**

### Expiring Food Forecast
Highlights which items are approaching expiration by food group. Allows user to see what food group has already expired or will be expiring in 1-3 days, 4-7 days, 8-14 days, 15-30 days, orin 30+ days. 

<img width="544" height="376" alt="Expiring Food Forcast " src="https://github.com/user-attachments/assets/d61efe3e-3dc4-479b-b17b-ec5a5be4b999" />

### Consumption vs Waste Over Time
Compares planned meal usage with predicted food waste over the next thirty days. Allows user to compare forecasted waste with planned meals to help them see where meal-planning gaps need to be filled. 

<img width="535" height="329" alt="Consumption vs Food Over Time" src="https://github.com/user-attachments/assets/6c6dd851-d00f-4383-8412-180555fd4ab1" />

### Realized vs Avoided Waste
Shows actual waste vs. prevented waste. Complies over food pantry usage to give the user one big snapshot in how much waste they have generated (red) and avoided (green) by using the meal planning system. 

<img width="537" height="387" alt="Realized vs Avoided Waste" src="https://github.com/user-attachments/assets/2f8f0901-b126-4f5c-8793-c7843e0bf96e" />

### Recipe–Product Overlap Network
Visualizes how ingredients in recipes map to Trader Joe’s products. Allows user to see how ingredients and recipes overlap with one another. 

<img src="images/Recipe%20product%20overlap%20network%20graph.png" width="650">

---

# 🧺 Pantry Dashboard

Your central hub for managing a virtual pantry.

## **Pantry Controls**
- **Clear Pantry** — empty pantry (not counted as waste)
- **Trash Pantry** — empty pantry (counted as waste)
- **Trash Expired** — remove expired food, counted as waste
- **Sample Pantry** - generates random pantry sample to simulate weeks of use

<img src="images/pantry%20buttons%20to%20the%20side.png" width="250">

## **Pantry Overview**
View your items, quantities, and expiration timelines.

<img src="images/pantry%20contents%20and%20filtering.png" width="700">

## **Pantry Insights**
- **Expiration Forecast Histogram** Three histograms filtered by Category Totals or Product-Level Stacked View display:
    - Total Amount of Food Expiring by Category
    - Total Amount of Food Expiring in 1 Day
    - Total Amount of Food Expiring in 7 Days.  
- **Pantry Roll-Up** Table showing the pantry's food products and their standardized amounts. 
- **Items Expiring Soon** Table showing the pantry's food products, their amount and unit, days left until expired, and expiration date. 
- **Category Consumption Insights** This treemap gives users an at-a-glance view of how much of each food category and product they’ve actually consumed. 

<img src="images/treemap%20visual%20for%20consumption%20by%20category%20and%20product.png" width="700">

## **Add Items**
Choose a category, select a product, choose quantity.

<img width="283" height="563" alt="add_items" src="https://github.com/user-attachments/assets/e73529dc-cb7d-4619-abfc-d3135d136c23" />

## **Manage Items**
Remove (no waste penalty) or trash (waste penalty) pantry items.

<img width="288" height="262" alt="manage_items" src="https://github.com/user-attachments/assets/886cf5e5-eafd-4f98-b68b-b9f0209cdaa4" />

---

# 📅 Planning Dashboard

The central location for scheduling recipes and forecasting usage.

> 💡 *Tip: “How Planning Works” guide appears on the sidebar for quick reference.*

## **Refresh Recommendations**
Updates recommendations when pantry contents change.

<img width="129" height="78" alt="Screenshot 2025-12-02 at 9 58 58 PM" src="https://github.com/user-attachments/assets/b5a19c09-d69e-4388-bc79-48de02064696" />

## **Recommendation Filters**
Control how many missing ingredients you’re willing to purchase.

<img width="310" height="158" alt="rec_filters" src="https://github.com/user-attachments/assets/ee50f0af-a523-4349-a311-4720501560dc" />

## **Meal Plan Overview**
Visualizes what types of meals are planned throughout the week.

<img src="images/Food%20Waste%20Forecast%20and%20Meals%20Planned.png" width="700">
---

# 🍽️ Recommendation by Category

Browse personalized recipe recommendations. "Highly Recommended" and "Encoraged" recipes are based on:

- Pantry contents
- Allowed missing ingredients
- Ingredient expiration timelines
- Product overlap

Recipes are grouped by:

**Breakfast • Lunch • Dinner • Appetizers & Sides • Desserts • Beverages**

Example recommended recipe:

<img src="images/Single%20Recommended%20Recipe.png" width="325">

---

# 📋 Planning Queue

- Color-coded squares indicate recipe status:
   - 🟩 Green Square = recipe planned before food expires
   - 🟨 Yellow Square = recipe not planned
   - 🟥 Red Square = recipe planned for after food expires.
     
- Click **+ Add** to add a recipe to its category
- Select a day & meal time, then confirm
- The weekly overview updates automatically

<img src="images/planning%20queue.png" width="700">

---

# 🤖 Recipe Recommender Logic

A core focus of the project is computing a **Waste-Risk Score** for each recipe. Each item in the pantry has a live waste risk score associated with it based on its category and its time until expiration.

## **1. Item-Level Scoring**
```
0 if expired OR if no shelf life exists
urgency = 1 / num_hours_remaining
pantry_item_score = urgency * category_multiplier

```
This prioritizes items closer to expiring and categories with higher waste impact.

## **2. Recipe-Level Scoring**
For each ingredient in a recipe:

1. If no matched product → mark as external
2. If matched but not in pantry → mark as missing
3. If multiple pantry items exist → use items expiring soonest first
4. Check if pantry quantities satisfy ingredient requirements
5. Compute per-unit waste-risk contribution

Ingredients accumulate to form a **Total Waste-Risk Score**.

Recipes are sorted and returned by score.

---

# 🧠 Logic Pipeline Overview

### **1. Parse Recipe Ingredients**
Convert raw ingredient text into structured fields.

### **2. Match Ingredients to Trader Joe’s Products**
Using fuzzy matching & NLP similarity → stored as `matched_product_id`.

### **3. Convert Quantities to Pantry Units**
Standardizes recipe units into comparable pantry units.

### **4. Generate Recipe Recommendations**
Computed using pantry inventory and ingredient mapping.

### **5. Record User Selections**
Logged in `RecipeSelected`.

### **6. Continuous Updates & Visualization**
Real-time updates as users modify pantry items or plan meals.

---

# 📊 Visual System Updates

The interface always reflects the most current state of the: 
- Pantry
- Recipe plans
- Ingredient availability
- Waste forecasts

Including interactive Altair + Plotly charts.

