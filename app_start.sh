#!/bin/bash
## make this an executable  chmod +x app_start.sh ##
set -e

# === 1. Check if setup has been run ===
if [ -f setup_complete.flag ]; then
    echo "Setup already completed. Skipping initialization..."
else
    echo "Running first-time setup..."

    # === 2. Create virtual environment ===
    python3 -m venv venv

    # === 3. Activate virtual environment ===
    source venv/bin/activate

    # === 4. Install dependencies ===
    python3 -m pip install --upgrade pip
    pip install -r requirements.txt

    # === 5. Run initial setup scripts ===
    python3 database/init_db.py
    python3 data/pipeline/webscrape_to_database.py
    python3 data/pipeline/ingredient_parser_pipe.py
    # === python3 data/pipeline/run_product_mapping_pipe.py will not be run ===
    python3 data/pipeline/populate_mapped_ingredients.py
    python3 data/pipeline/unit_conversion_pipe.py

    # === 6. Mark setup complete ===
    echo "Setup complete" > setup_complete.flag

    echo "First-time setup complete."
fi

# === 7. Activate virtual environment ===
source .venv/bin/activate

# === 8. Run Streamlit app ===
streamlit run streamlit_app/streamlit_app.py
