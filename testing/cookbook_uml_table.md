```mermaid
classDiagram
  class Recipe {
    +INTEGER recipe_id PK
    +TEXT title
    +TEXT url
    +TEXT image_url
    +TEXT serves
    +TEXT time
    +TEXT category
  }

  class Usable_Ingredients {
    +INTEGER ingredient_id PK
    +TEXT raw_name
    +TEXT norm_name
  }

  class Quantity {
    +INTEGER quantity_id PK
    +TEXT amount_text
  }

  class Cookbook {
    +INTEGER recipe_id FK
    +INTEGER ingredient_id FK
    +INTEGER quantity_id FK
    --
    (PK) recipe_id, ingredient_id, quantity_id
  }

  class Pantry {
    +INTEGER pantry_id PK
    +INTEGER ingredient_id FK
    +REAL amount
    +TEXT unit
    +TEXT date_purchased
    +TEXT expiration_date
  }

  class TJ_Inventory {
    +INTEGER product_id PK
    +TEXT name
    +TEXT norm_name
    +TEXT unit
    +REAL price
    +TEXT url
    +TEXT category
  }

  class Sold_As {
    +INTEGER product_id FK
    +INTEGER ingredient_id FK
    --
    (PK) product_id, ingredient_id
  }

  class Ingredient_Recipe_Inverted_Index {
    +INTEGER ingredient_id FK
    +INTEGER recipe_id FK
  }

  class Recipe_Recommended {
    +INTEGER id PK
    +INTEGER recipe_id FK
    +TEXT date
    +TEXT recipe
  }

  class Recipe_Selected {
    +INTEGER sel_id PK
    +INTEGER recipe_id FK
    +TEXT sel_ts
  }

  Recipe "1" --o "0..*" Cookbook : recipe_id
  Usable_Ingredients "1" --o "0..*" Cookbook : ingredient_id
  Quantity "1" --o "0..*" Cookbook : quantity_id

  Usable_Ingredients "1" --o "0..*" Pantry : ingredient_id
  TJ_Inventory "1" --o "0..*" Sold_As : product_id
  Usable_Ingredients "1" --o "0..*" Sold_As : ingredient_id

  Usable_Ingredients "1" --o "0..*" Ingredient_Recipe_Inverted_Index
  Recipe "1" --o "0..*" Ingredient_Recipe_Inverted_Index

  Recipe "1" --o "0..*" Recipe_Recommended
  Recipe "1" --o "0..*" Recipe_Selected
```