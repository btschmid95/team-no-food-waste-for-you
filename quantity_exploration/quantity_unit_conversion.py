import pandas as pd


FIRST_UNITS = [
    "cup", "cups",
    "tablespoon", "tablespoons",
    "teaspoon", "teaspoons",
    "ounce", "ounces"
]

DOES_NOT_WORK = [
    "slices", "slice",
    "clove", "cloves",
    "handful", "sprig", "sprigs",
    "loaf", "pound", "scoops", "bar", "pint",
    "heads"
]

UNIT_TO_OZ = {
    "cup": 8, "cups": 8,
    "tablespoon": 0.5, "tablespoons": 0.5,
    "teaspoon": 0.1667, "teaspoons": 0.1667,
    "ounce": 1, "ounces": 1
}


def prep_tj(tj_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and split TJ 'unit' column into numeric amount + unit text.
    Returns a new DataFrame.
    """
    df = tj_df.copy()
    df["unit"] = df["unit"].str.strip().str.replace("/", "", regex=False)

    unit_split = df["unit"].str.extract(
        r"(?P<store_amount>[\d\.]+)\s*(?P<store_unit>[A-Za-z\s]+)"
    )

    df = pd.concat([df, unit_split], axis=1)
    return df


def convert_to_oz(amount, unit):
    """Converts a recipe's quantity + unit to ounces."""
    try:
        return float(amount) * UNIT_TO_OZ[unit]
    except (TypeError, ValueError, KeyError):
        return None


def units_to_store_units2(cookbook_df: pd.DataFrame,
                          tj_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Given a cookbook ingredient table + prepped TJ inventory,
    create pantry_amount/pantry_unit and mark converted_to_store.
    """
    final_df = cookbook_df.copy()

    def explore_ingredients(unit_name: str) -> pd.DataFrame:
        """Merges cookbook ingredients with TJ inventory by name."""
        # use final_df here so it reflects any previous steps if needed
        unit_df = final_df[final_df["unit"] == unit_name].copy()
        unit_reduced = unit_df[["name", "amount", "unit"]]

        tj_reduced = tj_inventory[["product_name", "store_amount", "store_unit"]]

        matches = unit_reduced.merge(
            tj_reduced,
            left_on="name",
            right_on="product_name",
            how="inner"
        )

        matches["amount"] = pd.to_numeric(matches["amount"], errors="coerce")
        matches["store_amount"] = pd.to_numeric(matches["store_amount"], errors="coerce")

        matches["amount_to_store"] = matches["amount"] * matches["store_amount"]

        matches.rename(
            columns={
                "amount_to_store": "pantry_amount",
                "store_unit": "pantry_unit"
            },
            inplace=True
        )

        return matches[["name", "pantry_amount", "pantry_unit", "unit"]]

    # ---- 1) handle FIRST_UNITS (direct conversion to Oz) ----
    mask_first = final_df["unit"].isin(FIRST_UNITS)
    final_df.loc[mask_first, "pantry_amount"] = final_df.loc[mask_first].apply(
        lambda r: convert_to_oz(r["amount"], r["unit"]), axis=1
    )
    final_df.loc[mask_first, "pantry_unit"] = "Oz"

    # ---- 2) skip DOES_NOT_WORK ----
    mask_skip = final_df["unit"].isin(DOES_NOT_WORK)
    final_df.loc[mask_skip, ["pantry_amount", "pantry_unit"]] = [None, None]

    # ---- 3) everything else ----
    mask_other = ~(mask_first | mask_skip)
    unique_units = final_df.loc[mask_other, "unit"].dropna().unique()

    for unit_name in unique_units:
        matches = explore_ingredients(unit_name)
        if not matches.empty:
            for _, row in matches.iterrows():
                final_df.loc[
                    (final_df["name"] == row["name"]) &
                    (final_df["unit"] == row["unit"]),
                    ["pantry_amount", "pantry_unit"]
                ] = [row["pantry_amount"], row["pantry_unit"]]

    # ---- 4) mark converted_to_store ----
    final_df["converted_to_store"] = (
        final_df["pantry_amount"].notna() & final_df["pantry_unit"].notna()
    )

    # ---- 5) fallback: if not converted, copy original unit + amount ----
    not_converted = ~final_df["converted_to_store"]
    final_df.loc[not_converted, "pantry_amount"] = final_df.loc[not_converted, "amount"]
    final_df.loc[not_converted, "pantry_unit"] = final_df.loc[not_converted, "unit"]

    return final_df


def run_pipeline(cookbook_file_path: str,
                 tj_file_path: str) -> pd.DataFrame:
    """
    High-level pipeline:
    1) read both CSVs
    2) prep TJ inventory
    3) convert cookbook units to store-aligned pantry units
    """
    cookbook = pd.read_csv(cookbook_file_path)
    tj = pd.read_csv(tj_file_path)

    tj_inventory = prep_tj(tj)
    cookbook_revised = units_to_store_units2(cookbook, tj_inventory)

    return cookbook_revised


if __name__ == "__main__":
    cookbook_path = "data/all_ingredients_mapped_to_products_original.csv"
    tj_path = "data/trader_joes_products_v3.csv"

    result = run_pipeline(cookbook_path, tj_path)
    print(result.head())