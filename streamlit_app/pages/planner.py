import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session

from services.recipe_manager import RecipeManager
from services.pantry_manager import PantryManager
from recommender_system.recipe_recommender_sys import RecipeRecommender


# ------------------------------------------------------
# Base setup
# ------------------------------------------------------
apply_base_config()
render_sidebar()

session = get_session()  # should give you a SQLAlchemy Session

# Instantiate managers / services
rm = RecipeManager(session)
pm = PantryManager(session)
recommender = RecipeRecommender(session)

# ------------------------------------------------------
# Helper: rebuild virtual pantry from real pantry + planned recipes
# ------------------------------------------------------
def rebuild_virtual_pantry():
    """
    Start from the real pantry, then virtually consume ingredients
    for each planned recipe (in planned date order) to simulate
    future usage. This state feeds back into the recommender.
    """
    # 1) Start from real pantry
    items = recommender.pm.get_all_items()
    state = {
        int(item["product_id"]): {
            "amount": item["amount"],
            "expiration_date": item["expiration_date"],
        }
        for item in items
    }

    # 2) Apply planned recipes in date order (soonest first)
    sorted_planned = sorted(
        st.session_state.planned_recipes.items(),
        key=lambda kv: kv[1]["planned_for"] or "9999-99-99",
    )

    for sel_id, pdata in sorted_planned:
        rid = pdata["recipe_id"]
        recipe_obj = rm.get_recipe_by_id(rid)
        if recipe_obj:
            state = recommender._apply_recipe_to_virtual_state(recipe_obj, state)

    return state

def load_planned_recipes_from_db(session):
    """Load DB rows into session_state.planned_recipes."""
    from database.tables import RecipeSelected
    from services.recipe_manager import RecipeManager

    rm = RecipeManager(session)
    entries = rm.get_planning_queue()
    st.session_state.planned_recipes = {
        entry.sel_id: {
            "recipe_id": entry.recipe_id,
            "title": entry.recipe.title,
            "planned_for": entry.planned_for.date().isoformat() if entry.planned_for else None,
            "meal_slot": entry.meal_slot,
            "status": "confirmed" if entry.cooked_at else "planned",
            "added_at": entry.selected_at.isoformat(),
        }
        for entry in entries
    }


def sync_planned_recipes_to_db(session):
    from services.recipe_manager import RecipeManager
    rm = RecipeManager(session)

    # 1. Determine what exists in DB vs session_state
    existing_db_ids = {r.sel_id for r in rm.get_planning_queue()}
    current_ids = {
        sel_id for sel_id in st.session_state.planned_recipes.keys()
        if not (isinstance(sel_id, str) and sel_id.startswith("temp_"))
    }

    # 2. DB rows not present in session_state → delete them
    to_delete_db = existing_db_ids - current_ids
    for sel_id in to_delete_db:
        rm.delete_planned_recipe(sel_id)

    # 3. Add/update remaining items
    to_delete = []
    to_add = []

    for sel_id, pdata in st.session_state.planned_recipes.items():

        # TEMPORARY ENTRY → Create DB record
        if isinstance(sel_id, str) and sel_id.startswith("temp_"):
            raw_date = pdata.get("planned_for")

            planned_for = None
            if raw_date:
                try:
                    planned_for = datetime.fromisoformat(raw_date)
                except:
                    pass

            new = rm.add_recipe_to_planning_queue(
                pdata["recipe_id"],
                planned_for=planned_for
            )
            new_sel_id = new.sel_id
            to_add.append((new_sel_id, pdata))
            to_delete.append(sel_id)

        else:
            # EXISTING DB ROW → update
            rm.update_planned_date(sel_id, pdata["planned_for"])
            rm.update_meal_slot(sel_id, pdata["meal_slot"])

    # Apply changes
    for old_key in to_delete:
        del st.session_state.planned_recipes[old_key]
    for new_key, pdata in to_add:
        st.session_state.planned_recipes[new_key] = pdata

def compute_optimal_date_for_recipe(
    recipe,
    virtual_state,
    planned_recipes,
    current_day=None,
    current_slot=None,
    sel_id=None
):
    """Return optimal date/slot with no flip-flop and respecting user selections."""

    today = datetime.now().date()

    # ----------------------------------------------------
    # STEP A — Allowed meal slots
    # ----------------------------------------------------
    norm_cat = recommender.normalize_category_label(recipe).lower()

    allowed_slots = set()
    if "breakfast" in norm_cat: allowed_slots.add("Breakfast")
    if "lunch" in norm_cat: allowed_slots.add("Lunch")
    if "dinner" in norm_cat: allowed_slots.add("Dinner")
    if any(x in norm_cat for x in ["appetizer", "side", "snack"]):
        allowed_slots.add("Snack")
    if "dessert" in norm_cat:
        allowed_slots.add("Dessert")
    if any(x in norm_cat for x in ["beverage", "drink", "cocktail"]):
        allowed_slots.add("Beverage")
    if not allowed_slots:
        allowed_slots = set(MEAL_SLOTS)

    # ----------------------------------------------------
    # STEP B — Compute raw optimal (no override)
    # ----------------------------------------------------
    raw_day, raw_slot, earliest_exp = compute_optimal_date_for_recipe_no_override(
        recipe, virtual_state, planned_recipes
    )

    # ----------------------------------------------------
    # STEP C — If user picked something, keep it *only if*
    #          it is still optimal or better
    # ----------------------------------------------------
    if current_day and current_slot and sel_id:

        # Must still be an allowed slot
        if current_slot in allowed_slots:

            # Slot must not be taken by another recipe
            conflict = any(
                pdata.get("planned_for") == str(current_day)
                and pdata.get("meal_slot") == current_slot
                and other_sel_id != sel_id
                for other_sel_id, pdata in planned_recipes.items()
            )

            if not conflict:
                # RULE: keep user's choice if it is ≤ raw recommended day
                if current_day <= raw_day:
                    return current_day, current_slot, earliest_exp

    # ----------------------------------------------------
    # STEP D — Otherwise return the raw optimal
    # ----------------------------------------------------
    return raw_day, raw_slot, earliest_exp

def compute_optimal_date_for_recipe_no_override(recipe, virtual_state, planned_recipes):
    """Original version that computes best date/slot WITHOUT override logic."""

    today = datetime.now().date()
    SEARCH_RANGE = 14

    # find earliest expiration
    exp_dates = []
    for ing in recipe.ingredients:
        pid = getattr(ing, "matched_product_id", None)
        if not pid:
            continue

        item = virtual_state.get(pid)
        if not item:
            continue

        exp = item.get("expiration_date")
        if isinstance(exp, datetime):
            exp = exp.date()
        if exp:
            exp_dates.append(exp)

    earliest_exp = min(exp_dates) if exp_dates else today + timedelta(days=10)

    # allowed slots
    norm_cat = recommender.normalize_category_label(recipe).lower()
    slots = set()
    if "breakfast" in norm_cat: slots.add("Breakfast")
    if "lunch" in norm_cat: slots.add("Lunch")
    if "dinner" in norm_cat: slots.add("Dinner")
    if any(x in norm_cat for x in ["appetizer","side","snack"]): slots.add("Snack")
    if "dessert" in norm_cat: slots.add("Dessert")
    if any(x in norm_cat for x in ["beverage","drink","cocktail"]): slots.add("Beverage")
    if not slots:
        slots = set(MEAL_SLOTS)

    # search before expiration
    for offset in range(SEARCH_RANGE):
        d = today + timedelta(days=offset)
        if d > earliest_exp:
            break
        used = {
            pdata.get("meal_slot")
            for rid2, pdata in planned_recipes.items()
            if pdata.get("planned_for") == str(d)
        }
        for slot in slots:
            if slot not in used:
                return d, slot, earliest_exp

    # search after expiration
    for offset in range(SEARCH_RANGE):
        d = today + timedelta(days=offset)
        used = {
            pdata.get("meal_slot")
            for rid2, pdata in planned_recipes.items()
            if pdata.get("planned_for") == str(d)
        }
        for slot in slots:
            if slot not in used:
                return d, slot, earliest_exp

    return today + timedelta(days=1), list(slots)[0], earliest_exp



MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Beverage"]

# Which recipe categories are valid for which meal slot
ALLOWED_FOR_SLOT = {
    "Breakfast": ["breakfast", "breakfast & desserts"],
    "Lunch": ["lunch", "dinner & lunch", "breakfast, lunch & dinner"],
    "Dinner": ["dinner", "dinner & lunch", "breakfast, lunch & dinner"],
    "Snack": ["appetizer", "appetizers", "appetizers & sides", "side", "snack"],
    "Dessert": ["dessert", "breakfast & desserts", "appetizers & sides & desserts"],
    "Beverage": ["beverage"],
}

CATEGORIES = {
    "Breakfast": "breakfast",
    "Lunch": "lunch",
    "Dinner": "dinner",
    "Appetizers & Sides": "appetizer",
    "Desserts": "dessert",
    "Beverages": "beverage",
}
# ------------------------------------------------------
# Initialize session_state keys ONLY ONCE
# ------------------------------------------------------
st.session_state.setdefault("planned_recipes", None)
st.session_state.setdefault("virtual_pantry", None)

# ------------------------------------------------------
# Load planned recipes from DB ONLY if not yet loaded
# ------------------------------------------------------
if st.session_state.planned_recipes is None:
    load_planned_recipes_from_db(session)

# ------------------------------------------------------
# Build virtual pantry ONLY if not yet built
# ------------------------------------------------------
if st.session_state.virtual_pantry is None:
    st.session_state.virtual_pantry = rebuild_virtual_pantry()
# ------------------------------------------------------
# PAGE HEADER
# ------------------------------------------------------
header_cols = st.columns([7, 1])
with header_cols[0]:
    st.title("📅 Planning Dashboard")
    st.caption("Plan meals, reduce waste, and optimize your pantry.")

with header_cols[1]:
    # Simple "refresh" that just reruns the app
    if st.button("🔄 Refresh", help="Re-run recommendations"):
        st.rerun()


# ------------------------------------------------------
# 🔎 Recommendation Filters
# ------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    st.subheader("Recommendation Filters")
    filter_cols = st.columns([2, 2, 6])
    with filter_cols[0]:
        max_missing = st.selectbox(
            "Max Missing Ingredients",
            [0, 1, 2, 3,4,5,10],
            index=1,
        )
        
with col2:
    st.subheader("📆 Meal Plan Overview")

    import plotly.graph_objects as go

    DAYS_TO_SHOW = 7
    today = datetime.now().date()
    dates = [today + timedelta(days=i) for i in range(DAYS_TO_SHOW)]
    display_slots = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert"]

    # Build matrix: 0 = empty, 1 = planned, 2 = confirmed
    matrix = []
    hover_text = []

    for slot in display_slots:
        row = []
        hover_row = []
        for d in dates:
            date_str = str(d)

            entry = None
            for sel_id, pdata in st.session_state.planned_recipes.items():
                rid = pdata["recipe_id"]
                if pdata.get("planned_for") == date_str and pdata.get("meal_slot") == slot:
                    entry = pdata
                    break

            if entry is None:
                row.append(0)
                hover_row.append(f"{slot}<br>{d}<br>No recipe")
            else:
                status = entry.get("status", "planned")

                # ------------------------------------------
                # 🔍 Check if any ingredient will be expired
                # ------------------------------------------
                sel_id = next(
                    sel for sel, pdata2 in st.session_state.planned_recipes.items()
                    if pdata2 is entry
                )
                rid = st.session_state.planned_recipes[sel_id]["recipe_id"]
                recipe_obj = rm.get_recipe_by_id(rid)
                planned_day = d

                expired_flag = False
                for ing in recipe_obj.ingredients:
                    pid = getattr(ing, "matched_product_id", None)
                    if not pid:
                        continue

                    state_item = st.session_state.virtual_pantry.get(pid)
                    if not state_item:
                        continue

                    exp = state_item.get("expiration_date")
                    if exp and isinstance(exp, datetime):
                        exp = exp.date()

                    if exp and exp < planned_day:
                        expired_flag = True
                        break

                # ------------------------------------------
                # Map state → z-value for heatmap
                # ------------------------------------------
                if expired_flag:
                    val = 3        # ❗ Red = expired
                elif status == "confirmed":
                    val = 2        # Green
                else:
                    val = 1        # Yellow

                row.append(val)

                # Hover text
                hover_row.append(
                    f"{slot}<br>{d}"
                    f"<br><b>{entry['title']}</b>"
                    f"<br>Status: {'Confirmed' if status=='confirmed' else 'Planned'}"
                    + ("<br><span style='color:red'>⚠ Uses expired items!</span>" if expired_flag else "")
                )

        matrix.append(row)
        hover_text.append(hover_row)

    # Fixed discrete mapping:
    # 0 -> gray, 1 -> yellow, 2 -> green

    fig = go.Figure(
        data = go.Heatmap(
            z=matrix,
            x=[d.strftime("%a %m/%d") for d in dates],
            y=display_slots,
            colorscale=[
                [0/3, "#F5F5F5"],  # 0 empty
                [1/3, "#FFF8C6"],  # 1 planned
                [2/3, "#3CB371"],  # 2 confirmed
                [3/3, "#FF4C4C"],  # 3 expired
            ],
            zmin=0,
            zmax=3,
            hoverinfo="text",
            text=hover_text,
            showscale=False,
        )
    )

    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#CCCCCC",
        ticks="",
        side="top",
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#CCCCCC",
        ticks="",
    )

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------
# Category-Based Recommendations
# ------------------------------------------------------
st.markdown("## 🍽️ Recommendations by Category")

tabs = st.tabs(list(CATEGORIES.keys()))

for tab, (label, keyword) in zip(tabs, CATEGORIES.items()):
    with tab:
        category_recs = recommender.recommend_by_category(
            keyword,
            limit=10,
            max_missing=max_missing,
            virtual_pantry_state=st.session_state.virtual_pantry,
        )

        if not category_recs:
            st.info("No recommendations available for this category.")
            continue

        cols = st.columns(5)

        for i, (col, rec) in enumerate(zip(cols, category_recs)):
            recipe_id = rec["recipe_id"]
            recipe_obj = rm.get_recipe_by_id(recipe_id)
            is_added = any(pdata["recipe_id"] == recipe_id for pdata in st.session_state.planned_recipes.values())


            with col:
                with st.container(border=True):

                    # -------------------------------
                    # Title + Category Badge
                    # -------------------------------
                    st.subheader(rec["title"])
                    st.caption("📂 " + recommender.normalize_category_label(recipe_obj))

                    # -------------------------------
                    # 🧂 Ingredient Breakdown
                    # -------------------------------
                    matched_rows = []
                    missing_rows = []

                    vp = st.session_state.virtual_pantry  # virtual pantry state

                    for ing in recipe_obj.ingredients:
                        name = getattr(ing, "name", None) \
                            or getattr(ing, "ingredient_name", None) \
                            or getattr(ing, "ingredient", None) \
                            or getattr(ing, "display_name", None) \
                            or "Unknown Ingredient"

                        needed = ing.pantry_amount or 0
                        unit = ing.pantry_unit or ""
                        pid = getattr(ing, "matched_product_id", None)

                        # -------------------------------------------------------
                        # CASE 1 — No matched product → ignore completely
                        # -------------------------------------------------------
                        if not pid:
                            continue  # external ingredient, do not show it

                        # -------------------------------------------------------
                        # CASE 2 — Matched product exists in pantry → matched
                        # -------------------------------------------------------
                        if pid in vp and vp[pid]["amount"] > 0:
                            pantry_amount = vp[pid]["amount"] or 0
                            used = min(pantry_amount, needed)
                            remaining = max(pantry_amount - used, 0)
                            if remaining >0:
                                matched_rows.append(
                                    f"- **{name}** — needs **{needed} {unit}**, "
                                    f"uses **{used}**, remaining **{round(remaining,2)}**"
                                )
                            else:
                                if pantry_amount == 0:
                                    matched_rows.append(
                                        f"- **{name}** — needs **{needed} {unit}**, "
                                        f"Pantry contains **{pantry_amount}** "
                                    )
                                else:
                                    matched_rows.append(
                                        f"- **{name}** — needs **{needed} {unit}**, "
                                        f"uses **{used}**, Nothing Left!"
                                    )
                            continue

                        # -------------------------------------------------------
                        # CASE 3 — Matched product but NOT in pantry → missing
                        # -------------------------------------------------------
                        missing_rows.append(f"- **{name}**")
                    # -------------------------------
                    # Add / Already in plan
                    # -------------------------------
                    if not is_added:
                        if st.button("➕ Add", key=f"catadd_{recipe_id}_{label}_{i}"):

                            optimal_day, optimal_slot, _ = compute_optimal_date_for_recipe(
                                recipe_obj,
                                st.session_state.virtual_pantry,
                                st.session_state.planned_recipes,
                            )

                            temp_sel = f"temp_{datetime.now().timestamp()}"
                            st.session_state.planned_recipes[temp_sel] = {
                                "recipe_id": recipe_id,
                                "title": rec["title"],
                                "added_at": datetime.now().isoformat(),
                                "planned_for": str(optimal_day),
                                "meal_slot": optimal_slot,
                                "status": "planned",
                            }
                            sync_planned_recipes_to_db(session)
                            #load_planned_recipes_from_db(session)    # ← ADD THIS
                            st.session_state.virtual_pantry = rebuild_virtual_pantry()
                            st.rerun()

                    else:
                        st.markdown("✔️ Already in plan")

                    # -------------------------------
                    # Meta info
                    # -------------------------------
                    st.write(f"Score: {rec['score']}")
                    if matched_rows:
                        st.markdown("## Matched Ingredients")
                        st.markdown("\n".join(matched_rows))

                    if missing_rows:
                        st.markdown("## Missing Ingredients")
                        st.markdown("\n".join(missing_rows))


# ------------------------------------------------------
# 📝 Planning Queue — Column Layout by Category
# ------------------------------------------------------
st.markdown("## 📝 Your Planning Queue")

if st.session_state.planned_recipes is None:
    st.warning("No recipes added to the planner yet.")
else:
    # Known order for columns
    CATEGORY_COLUMNS = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Beverage"]

    # Build grouping by inferred normalized category
    grouped = {c: [] for c in CATEGORY_COLUMNS}

    for sel_id, pdata in st.session_state.planned_recipes.items():
        rid = pdata["recipe_id"]
        recipe_obj = rm.get_recipe_by_id(rid)
        category = recommender.normalize_category_label(recipe_obj)

        # Match into one of our 6 buckets
        matched = None
        lc = category.lower()
        if "breakfast" in lc:
            matched = "Breakfast"
        elif "lunch" in lc:
            matched = "Lunch"
        elif "dinner" in lc:
            matched = "Dinner"
        elif any(x in lc for x in ["appetizer", "side", "snack"]):
            matched = "Snack"
        elif "dessert" in lc:
            matched = "Dessert"
        elif any(x in lc for x in ["beverage", "drink", "cocktail"]):
            matched = "Beverage"
        else:
            # fallback: stick in Snack column or another default
            matched = "Snack"

        grouped[matched].append((sel_id, pdata, recipe_obj))

    # Create 6 columns
    cols = st.columns(len(CATEGORY_COLUMNS))

    # Render each column
    for col, category in zip(cols, CATEGORY_COLUMNS):
        with col:
            st.markdown(f"#### {category}")

            items = grouped.get(category, [])
            if not items:
                st.write("*(none)*")
                continue

            # Sort recipes by added_at for consistency
            items = sorted(items, key=lambda x: x[1]["added_at"])

            for sel_id, pdata, recipe_obj in items:
                title = pdata["title"]
                
                # Determine expired flag
                planned_day = (
                    datetime.fromisoformat(pdata["planned_for"]).date()
                    if pdata.get("planned_for")
                    else None
                )

                expired_flag = False
                if planned_day:
                    for ing in recipe_obj.ingredients:
                        pid = getattr(ing, "matched_product_id", None)
                        if not pid:
                            continue

                        item = st.session_state.virtual_pantry.get(pid)
                        if not item:
                            continue

                        exp = item.get("expiration_date")
                        if isinstance(exp, datetime):
                            exp = exp.date()

                        if exp and exp < planned_day:
                            expired_flag = True
                            break
                status = pdata.get("status", "planned")

                if status == "confirmed":
                    prefix = "🟩"
                elif expired_flag:
                    prefix = "🟥"
                else:
                    prefix = "🟨"   

                with st.expander(f"{prefix} {title}"):

                    # -------------------------------
                    # Compute recommended date & slot
                    # -------------------------------
                    current_day = (
                        datetime.fromisoformat(pdata.get("planned_for")).date()
                        if pdata.get("planned_for") else None
                    )
                    current_slot = pdata.get("meal_slot")

                    optimal_day, optimal_slot, earliest_exp = compute_optimal_date_for_recipe(
                        recipe_obj,
                        st.session_state.virtual_pantry,
                        st.session_state.planned_recipes,
                        current_day=current_day,
                        current_slot=current_slot,
                        sel_id=sel_id,
                    )

                    # -------------------------------
                    # Show recommendation
                    # -------------------------------
                    if earliest_exp:
                        days_before_exp = (earliest_exp - optimal_day).days
                        st.markdown(
                            f"**Suggested Date:** `{optimal_day}` <br>{days_before_exp} day(s) before expiration"
                            f"<br>**Suggested Meal Slot:** `{optimal_slot}`",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"**Suggested Date:** `{optimal_day}`"
                            f"<br>**Suggested Meal Slot:** `{optimal_slot}`",
                            unsafe_allow_html=True,
                        )

                    # -------------------------------
                    # DATE INPUT
                    # -------------------------------
                    stored_date_str = pdata.get("planned_for")
                    if stored_date_str:
                        try:
                            default_date = datetime.fromisoformat(stored_date_str).date()
                        except Exception:
                            default_date = optimal_day
                    else:
                        default_date = optimal_day

                    date = st.date_input(
                        "Choose a cooking date:",
                        default_date,
                        key=f"date_picker_{sel_id}",
                    )
                    chosen_date_str = str(date)

                    # -------------------------------
                    # Determine allowed meal slots
                    # -------------------------------
                    norm_cat = recommender.normalize_category_label(recipe_obj).lower()

                    allowed_slots = set()
                    if "breakfast" in norm_cat:
                        allowed_slots.add("Breakfast")
                    if "lunch" in norm_cat:
                        allowed_slots.add("Lunch")
                    if "dinner" in norm_cat:
                        allowed_slots.add("Dinner")
                    if any(x in norm_cat for x in ["appetizer", "side", "snack"]):
                        allowed_slots.add("Snack")
                    if "dessert" in norm_cat:
                        allowed_slots.add("Dessert")
                    if any(x in norm_cat for x in ["beverage", "drink", "cocktail"]):
                        allowed_slots.add("Beverage")
                    if not allowed_slots:
                        allowed_slots = set(MEAL_SLOTS)

                    # Remove slots already taken on that date
                    taken_slots = {
                        pdata2.get("meal_slot")
                        for other_sel_id, pdata2 in st.session_state.planned_recipes.items()
                        if pdata2.get("planned_for") == chosen_date_str and other_sel_id != sel_id
                    }
                    available_slots = [s for s in allowed_slots if s not in taken_slots]

                    # Default slot
                    stored_slot = pdata.get("meal_slot")
                    if stored_slot in available_slots:
                        default_slot = stored_slot
                    elif optimal_slot in available_slots:
                        default_slot = optimal_slot
                    elif available_slots:
                        default_slot = available_slots[0]
                    else:
                        default_slot = None

                    if not available_slots:
                        st.error("❌ No valid meal slots on this date.")
                        slot = None
                    else:
                        slot = st.selectbox(
                            "Meal Slot",
                            available_slots,
                            index=available_slots.index(default_slot),
                            key=f"slot_picker_{sel_id}",
                        )

                    # Store changes + rerun
                    prev_date = pdata.get("planned_for")
                    prev_slot = pdata.get("meal_slot")

                    st.session_state.planned_recipes[sel_id]["planned_for"] = chosen_date_str
                    st.session_state.planned_recipes[sel_id]["meal_slot"] = slot

                    if chosen_date_str != prev_date or slot != prev_slot:
                        sync_planned_recipes_to_db(session)
                        st.session_state.virtual_pantry = rebuild_virtual_pantry()
                        st.rerun()

                    # -------------------------------
                    # ACTION BUTTONS
                    # -------------------------------
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🗑 Remove", key=f"remove_{sel_id}"):
                            del st.session_state.planned_recipes[sel_id]
                            sync_planned_recipes_to_db(session)
                            st.session_state.virtual_pantry = rebuild_virtual_pantry()
                            st.rerun()

                    with c2:
                        #confirm_key = f"confirm_btn_{rid}"
                        #confirm_state_key = f"confirm_state_{rid}"
                        if st.button("✔️ Confirm", key=f"confirm_{sel_id}"):
                            st.session_state.planned_recipes[sel_id]["status"] = "confirmed"

                            rm.confirm_recipe(sel_id)

                            st.session_state.virtual_pantry = rebuild_virtual_pantry()
                            st.rerun()



# ------------------------------------------------------
# Sidebar help text
# ------------------------------------------------------
with st.sidebar.expander("ℹ️ How Planning Works"):
    st.write(
        """
        **Planning Dashboard Workflow**
        - View top personalized recipe recommendations  
        - Filter recommendations by missing ingredient count  
        - Browse the full list of recipes  
        - Add recipes to your planning queue  
        - Assign a date to make each recipe  
        - “Confirm” a recipe to lock it in  
        - Confirmation will:
          - Deduct ingredients that will be used  
          - Feed into waste-forecasting and future recommendations  
        """
    )
