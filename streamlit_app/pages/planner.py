import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from config.theme_config import apply_base_config
from components.sidebar import render_sidebar
from utils.session import get_session
from database.tables import TJInventory
from services.recipe_manager import RecipeManager
from services.pantry_manager import PantryManager
from recommender_system.recipe_recommender_sys import RecipeRecommender

apply_base_config()
render_sidebar()

session = get_session()


rm = RecipeManager(session)
pm = PantryManager(session)
recommender = RecipeRecommender(session)

def rebuild_virtual_pantry():
    """
    Start from the real pantry, then virtually consume ingredients
    for each planned recipe (in planned date order) to simulate
    future usage. This state feeds back into the recommender.
    """
    items = recommender.pm.get_all_items()
    state = {
        int(item["product_id"]): {
            "amount": item["amount"],
            "expiration_date": item["expiration_date"],
        }
        for item in items
    }

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

def virtual_pantry_to_df(session, vp_state):
    """
    Convert st.session_state.virtual_pantry to a full pantry DataFrame,
    matching the structure returned by PantryManager.get_pantry_items().
    """
    rows = []

    for pid, data in vp_state.items():
        product = session.query(TJInventory).get(pid)

        rows.append({
            "product_id": pid,
            "product_name": product.name if product else "Unknown",
            "category": product.category if product else "Other",
            "sub_category": product.sub_category if product else None,
            "amount": data.get("amount", 0),
            "unit": product.unit if product else None,
            "date_added": None,  # not relevant for virtual state
            "expiration_date": data.get("expiration_date"),
        })

    return pd.DataFrame(rows)

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

    existing_db_ids = {r.sel_id for r in rm.get_planning_queue()}
    current_ids = {
        sel_id for sel_id in st.session_state.planned_recipes.keys()
        if not (isinstance(sel_id, str) and sel_id.startswith("temp_"))
    }

    to_delete_db = existing_db_ids - current_ids
    for sel_id in to_delete_db:
        rm.delete_planned_recipe(sel_id)

    to_delete = []
    to_add = []

    for sel_id, pdata in st.session_state.planned_recipes.items():

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
            rm.update_planned_date(sel_id, pdata["planned_for"])
            rm.update_meal_slot(sel_id, pdata["meal_slot"])

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

    raw_day, raw_slot, earliest_exp = compute_optimal_date_for_recipe_no_override(
        recipe, virtual_state, planned_recipes
    )
    if current_day and current_slot and sel_id:

        if current_slot in allowed_slots:

            conflict = any(
                pdata.get("planned_for") == str(current_day)
                and pdata.get("meal_slot") == current_slot
                and other_sel_id != sel_id
                for other_sel_id, pdata in planned_recipes.items()
            )

            if not conflict:
                if current_day <= raw_day:
                    return current_day, current_slot, earliest_exp

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

def cleanup_past_planned_recipes(session):
    today = datetime.now().date()
    for sel_id, pdata in st.session_state.planned_recipes.items():
        if pdata["status"] == "planned" and pdata["planned_for"]:
            planned_day = datetime.fromisoformat(pdata["planned_for"]).date()

            if planned_day < today:
                pdata["status"] = "missed"

def cleanup_past_confirmed_recipes():
    today = datetime.now().date()

    to_delete = []
    for sel_id, pdata in st.session_state.planned_recipes.items():
        if pdata["status"] == "confirmed":
            planned_day = datetime.fromisoformat(pdata["planned_for"]).date()
            if planned_day < today:
                to_delete.append(sel_id)

    for sel_id in to_delete:
        del st.session_state.planned_recipes[sel_id]

def purge_missed_recipes():
    to_remove = [sel for sel, pdata in st.session_state.planned_recipes.items() if pdata["status"] == "missed"]
    for sel in to_remove:
        del st.session_state.planned_recipes[sel]


MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Beverage"]

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

st.session_state.setdefault("planned_recipes", None)
st.session_state.setdefault("virtual_pantry", None)

if st.session_state.planned_recipes is None:
    load_planned_recipes_from_db(session)

cleanup_past_planned_recipes(session)
cleanup_past_confirmed_recipes()
purge_missed_recipes()

sync_planned_recipes_to_db(session)
st.session_state.virtual_pantry = rebuild_virtual_pantry()

header_cols = st.columns([7, 1])
with header_cols[0]:
    st.title("📅 Planning Dashboard")
    st.caption("Plan meals, reduce waste, and optimize your pantry.")

with header_cols[1]:
    if st.button("🔄 Refresh", help="Re-run recommendations"):
        st.rerun()

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

    # Controls
    col_1, col_2 = st.columns(2)
    with col_1:
        include_planned = st.checkbox(
            "Include planned meals in waste forecast", 
            value=True
        )

    with col_2:
        forecast_range = st.selectbox(
            "Forecast Range",
            ["1 Week", "2 Weeks"],
            index=0
        )

    # Days → numeric
    DAYS_TO_SHOW = 7 if forecast_range == "1 Week" else 14
    today = datetime.now().date()
    dates = [today + timedelta(days=i) for i in range(DAYS_TO_SHOW)]

    # Dataframe source
    if include_planned:
        df = virtual_pantry_to_df(session, st.session_state.virtual_pantry)
    else:
        df = pm.get_pantry_items()

    # Colors
    CATEGORY_COLORS = {
        "Fresh Fruits & Veggies": "#69e169",
        "Meat, Seafood & Plant-based": "#f0695a",
        "Cheese": "#e6da71",
        "Bakery": "#805d35",
        "For the Pantry": "#87a752",
        "From The Freezer": "#7adfeb",
        "Dairy & Eggs": "#999999",
        "Fresh Prepared Foods": "#57A444"
    }

    # Compute expiration timeline
    waste_data = {}
    for _, row in df.iterrows():
        exp = row["expiration_date"]
        if isinstance(exp, datetime): 
            exp = exp.date()
        if not exp:
            continue

        if today <= exp < today + timedelta(days=DAYS_TO_SHOW):
            idx = (exp - today).days
            cat = row.get("category") or "Other"
            amt = row.get("amount", 1)

            waste_data.setdefault(cat, [0]*DAYS_TO_SHOW)
            CATEGORY_COLORS.setdefault(cat, "#cccccc")
            waste_data[cat][idx] += amt

    # --- TOP CHART (stacked area, no x-labels) ---
    fig_waste = go.Figure()

    for cat, values in waste_data.items():
        if sum(values) > 0:
            fig_waste.add_trace(
                go.Scatter(
                    x=list(range(DAYS_TO_SHOW)),  # no date labels
                    y=values,
                    stackgroup="one",
                    name=cat,
                    mode="lines",
                    line=dict(width=1),
                    fillcolor=CATEGORY_COLORS.get(cat, "#cccccc"),
                )
            )

    fig_waste.update_layout(
        height=160,
        margin=dict(l=6, r=6, t=10, b=0),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.04),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(title="Expiring Qty", rangemode="tozero"),
    )

    st.plotly_chart(fig_waste, use_container_width=True)

    # ======= MEAL HEATMAP (bottom chart; with grid + labels) =======

    display_slots = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert"]
    matrix = []
    hover_text = []

    for slot in display_slots:
        row = []
        hover_row = []

        for d in dates:
            d_str = str(d)

            # Match recipe to date/slot
            entry = next(
                (pdata for sel_id, pdata in st.session_state.planned_recipes.items()
                 if pdata.get("planned_for") == d_str and pdata.get("meal_slot") == slot),
                None
            )

            if entry is None:
                row.append(0)
                hover_row.append(f"{slot}<br>{d}<br>No recipe")
            else:
                status = entry.get("status", "planned")
                rid = entry["recipe_id"]
                recipe_obj = rm.get_recipe_by_id(rid)

                expired_flag = False
                if recipe_obj:
                    for ing in recipe_obj.ingredients:
                        pid = getattr(ing, "matched_product_id", None)
                        if not pid: continue

                        vp_item = st.session_state.virtual_pantry.get(pid)
                        if not vp_item: continue

                        exp = vp_item.get("expiration_date")
                        if isinstance(exp, datetime): exp = exp.date()
                        if exp and exp < d:
                            expired_flag = True
                            break

                if expired_flag:
                    val = 3
                elif status == "confirmed":
                    val = 2
                else:
                    val = 1

                row.append(val)
                hover_row.append(
                    f"{slot}<br>{d}<br><b>{entry['title']}</b>"
                    f"<br>Status: {status}"
                    + ("<br><span style='color:red;'>⚠ Uses expired items</span>" if expired_flag else "")
                )

        matrix.append(row)
        hover_text.append(hover_row)

    # BOTTOM HEATMAP
    fig = go.Figure(
        data = go.Heatmap(
            z=matrix,
            x=[d.strftime("%a %m/%d") for d in dates],
            y=display_slots,
            text=hover_text,
            hoverinfo="text",
            colorscale=[
                [0/3, "#F5F5F5"],
                [1/3, "#FFF8C6"],
                [2/3, "#3CB371"],
                [3/3, "#FF4C4C"],
            ],
            zmin=0,
            zmax=3,
            showscale=False,
        )
    )

    fig.update_layout(
        height=200,
        margin=dict(l=6, r=6, t=6, b=6),
    )

    # **Gridlines for squares**
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#CCCCCC",
        gridwidth=1,
        ticks="outside",
        side="bottom"
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#CCCCCC",
        gridwidth=1,
        ticks="outside"
    )

    st.plotly_chart(fig, use_container_width=True)


st.markdown("## Recommendations by Category")

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

                    st.subheader(rec["title"])
                    st.caption("📂 " + recommender.normalize_category_label(recipe_obj))

                    matched_rows = []
                    missing_rows = []

                    vp = st.session_state.virtual_pantry

                    for ing in recipe_obj.ingredients:
                        name = getattr(ing, "name", None) \
                            or getattr(ing, "ingredient_name", None) \
                            or getattr(ing, "ingredient", None) \
                            or getattr(ing, "display_name", None) \
                            or "Unknown Ingredient"

                        needed = ing.pantry_amount or 0
                        unit = ing.pantry_unit or ""
                        pid = getattr(ing, "matched_product_id", None)


                        if not pid:
                            continue

                        if pid in vp and vp[pid]["amount"] > 0:
                            pantry_amount = vp[pid]["amount"] or 0
                            used = min(pantry_amount, needed)
                            remaining = max(pantry_amount - used, 0)
                            if remaining >0:
                                matched_rows.append(
                                    f"- **{name}** — needs **{needed} {unit}**, "
                                    f"uses **{used}**/**{round(pantry_amount,2)}**, remaining **{round(remaining,2)}**"
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

                        missing_rows.append(f"- **{name}**")

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
                        st.session_state.virtual_pantry = rebuild_virtual_pantry()
                        st.rerun()

                    st.write(f"Score: {rec['score']}")
                    if matched_rows:
                        st.markdown("## Matched Ingredients")
                        st.markdown("\n".join(matched_rows))

                    if missing_rows:
                        st.markdown("## Missing Ingredients")
                        st.markdown("\n".join(missing_rows))



st.markdown("## Planning Queue")

if st.session_state.planned_recipes is None:
    st.warning("No recipes added to the planner yet.")
else:
    CATEGORY_COLUMNS = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Beverage"]

    grouped = {c: [] for c in CATEGORY_COLUMNS}

    for sel_id, pdata in st.session_state.planned_recipes.items():
        rid = pdata["recipe_id"]
        recipe_obj = rm.get_recipe_by_id(rid)
        category = recommender.normalize_category_label(recipe_obj)

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
            matched = "Snack"

        grouped[matched].append((sel_id, pdata, recipe_obj))

    cols = st.columns(len(CATEGORY_COLUMNS))

    for col, category in zip(cols, CATEGORY_COLUMNS):
        with col:
            st.markdown(f"#### {category}")

            items = grouped.get(category, [])
            if not items:
                st.write("*(none)*")
                continue

            items = sorted(items, key=lambda x: x[1]["added_at"])

            for sel_id, pdata, recipe_obj in items:
                title = pdata["title"]
                
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
                    if status == "confirmed":
                        st.markdown(
                            f"""
                            <div style="padding: 6px 10px; background-color: #d6f5d6;
                                        border-radius: 6px; border-left: 5px solid #3CB371;">
                                <strong>Confirmed</strong><br>
                                <b>Date:</b> {pdata.get("planned_for")}<br>
                                <b>Meal Slot:</b> {pdata.get("meal_slot")}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        continue

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

                    taken_slots = {
                        pdata2.get("meal_slot")
                        for other_sel_id, pdata2 in st.session_state.planned_recipes.items()
                        if pdata2.get("planned_for") == chosen_date_str and other_sel_id != sel_id
                    }
                    available_slots = [s for s in allowed_slots if s not in taken_slots]

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

                    prev_date = pdata.get("planned_for")
                    prev_slot = pdata.get("meal_slot")

                    st.session_state.planned_recipes[sel_id]["planned_for"] = chosen_date_str
                    st.session_state.planned_recipes[sel_id]["meal_slot"] = slot

                    if chosen_date_str != prev_date or slot != prev_slot:
                        sync_planned_recipes_to_db(session)
                        st.session_state.virtual_pantry = rebuild_virtual_pantry()
                        st.rerun()

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🗑 Remove", key=f"remove_{sel_id}"):
                            del st.session_state.planned_recipes[sel_id]
                            sync_planned_recipes_to_db(session)
                            st.session_state.virtual_pantry = rebuild_virtual_pantry()
                            st.rerun()

                    with c2:
                        if st.button("✔️ Confirm", key=f"confirm_{sel_id}"):
                            st.session_state.planned_recipes[sel_id]["status"] = "confirmed"

                            rm.confirm_recipe(sel_id)

                            st.session_state.virtual_pantry = rebuild_virtual_pantry()
                            st.rerun()



with st.sidebar.expander("ℹHow Planning Works"):
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
