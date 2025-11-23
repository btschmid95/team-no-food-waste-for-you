```mermaid
classDiagram
  class recipe {
    +INTEGER recipe_id
    +TEXT title
    +TEXT url
    +TEXT image_url
    +TEXT serves
    +TEXT time
    +TEXT category
  }

  class usable_ingredients {
    +INTEGER ingredient_id
    +TEXT raw_name
    +TEXT norm_name
  }

  class cookbook {
    +INTEGER recipe_id
    +INTEGER ingredient_id
    +REAL amount
    +TEXT unit
  }

  class pantry {
    +INTEGER pantry_id
    +INTEGER ingredient_id
    +REAL amount
    +TEXT unit
    +TEXT date_purchased
    +TEXT expiration_date
  }

  class tj_inventory {
    +INTEGER product_id
    +TEXT name
    +TEXT norm_name
    +REAL amount
    +TEXT unit
    +REAL price
    +TEXT url
    +TEXT category
  }

  class sold_as {
    +INTEGER product_id
    +INTEGER ingredient_id
  }

  class ingredient_recipe_inverted_index {
    +INTEGER ingredient_id
    +INTEGER recipe_id
  }

  class recipe_recommended {
    +INTEGER id
    +INTEGER recipe_id
    +TEXT date
    +TEXT recipe
  }

  class recipe_selected {
    +INTEGER sel_id
    +INTEGER recipe_id
    +TEXT sel_ts
  }

  %% Relationships
  recipe --> cookbook : recipe_id
  usable_ingredients --> cookbook : ingredient_id

  usable_ingredients --> pantry : ingredient_id

  tj_inventory --> sold_as : product_id
  usable_ingredients --> sold_as : ingredient_id

  usable_ingredients --> ingredient_recipe_inverted_index : ingredient_id
  recipe --> ingredient_recipe_inverted_index : recipe_id

  recipe --> recipe_recommended : recipe_id
  recipe --> recipe_selected : recipe_id
```g