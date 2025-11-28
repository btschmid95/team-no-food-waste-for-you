classDiagram

  class recipe {
    +INTEGER recipe_id PK
    +TEXT title
    +TEXT url
    +TEXT image_url
    +TEXT serves
    +TEXT time
    +TEXT category
  }

  class ingredient {
    +INTEGER ingredient_id PK
    +INTEGER recipe_id FK
    +TEXT raw_text
    +TEXT name
    +TEXT norm_name
    +FLOAT amount
    +TEXT unit
    +INTEGER matched_product_id FK
    +FLOAT pantry_amount
    +TEXT pantry_unit
  }

  class tj_inventory {
    +INTEGER product_id PK
    +TEXT name
    +TEXT norm_name
    +TEXT unit
    +FLOAT quantity
    +FLOAT price
    +TEXT url
    +TEXT category
    +TEXT sub_category
    +INTEGER shelf_life_days
  }

  class pantry {
    +INTEGER pantry_id PK
    +INTEGER product_id FK
    +FLOAT amount
    +TEXT unit
    +DATETIME date_added
    +DATETIME expiration_date
  }

  class pantry_event {
    +INTEGER id PK
    +INTEGER pantry_id FK
    +DATETIME timestamp
    +TEXT event_type
    +FLOAT amount
    +TEXT unit
    +INTEGER recipe_selection_id FK
  }

  class recipe_recommended {
    +INTEGER id PK
    +INTEGER recipe_id FK
    +DATETIME recommended_at
    +FLOAT score
  }

  class recipe_selected {
    +INTEGER sel_id PK
    +INTEGER recipe_id FK
    +DATETIME selected_at
    +DATETIME planned_for
    +DATETIME cooked_at
    +TEXT meal_slot
  }

  class ingredient_parse_meta {
    +INTEGER id PK
    +INTEGER ingredient_id FK
    +TEXT raw_text
    +TEXT parsed_name
    +FLOAT amount
    +TEXT amount_unit
    +TEXT subcat_1
    +FLOAT subcat_1_score
    +TEXT maincat_1
    +TEXT subcat_2
    +FLOAT subcat_2_score
    +TEXT maincat_2
    +TEXT subcat_3
    +FLOAT subcat_3_score
    +TEXT maincat_3
    +TEXT preparation
    +FLOAT preparation_confidence
    +TEXT recipe_title
    +TEXT recipe_category
    +DATETIME created_at
  }

  %% Relationships
  recipe "1" --> "many" ingredient : has
  ingredient "many" --> "1" tj_inventory : matches
  pantry "many" --> "1" tj_inventory : contains
  pantry_event "many" --> "1" pantry : event_for
  pantry_event "many" --> "1" recipe_selected : caused_by
  recipe_selected "many" --> "1" recipe : selects
  recipe_recommended "many" --> "1" recipe : recommends
  ingredient_parse_meta "many" --> "1" ingredient : parses
