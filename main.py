import os
import re
import argparse
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from pymongo import MongoClient

from sii_scraper.sii_scraper import SiiScraper

load_dotenv()

def clean_and_normalize(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    df = df[[
        "supplier_id", "supplier_name", "number", "date", "date_accepted", 
        "type", "exent_total", "net_total", "iva", "other_tax", 
        "total", "rut_holding", "status", "doc_type"
    ]]

    cols = ["supplier_id", "supplier_name", "type", "status", "doc_type"]

    df[cols] = (
        df[cols]
        .fillna("")
        .apply(lambda s: s.str.replace(".", "", regex=False)
                        .str.lower())
    )

    df["supplier_id"] = df["supplier_id"].str.upper()

    df["other_tax"] = df["other_tax"].fillna(0)

    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")

    df["date_accepted"] =  pd.to_datetime(df["date_accepted"], format="%d/%m/%Y %H:%M:%S")

    df["date"] = (
        df["date"]
        .dt.tz_localize("America/Santiago")
        .dt.tz_convert("UTC")
    )

    df["date_accepted"] = (
        df["date_accepted"]
        .dt.tz_localize("America/Santiago")
        .dt.tz_convert("UTC")
    )
    
    df["type"] = df["type"].map({"p": "contado"}).fillna("")

    int_cols = ["exent_total", "net_total", "iva", "other_tax", "total"]

    for col in int_cols:
        df[col] = (
            df[col]
                .str.replace(".", "")
                .fillna("0")
                .replace("", "0")
                .astype("int64")
        )

    return df

def load_all_credentials() -> dict:
    """
    Scan os.environ for SII_USER_X / SII_PASS_X and return
    { user_email: password, … }
    """
    creds = {}
    for var, val in os.environ.items():
        m = re.match(r"SII_USER_(\d+)", var)
        if not m:
            continue
        idx = m.group(1)
        user = val
        pw_var = f"SII_PASS_{idx}"
        pw = os.getenv(pw_var)
        if pw:
            creds[user] = pw
    return creds

def main(): 

    atlas_uri = os.getenv("MONGODB_URI")
    client = MongoClient(atlas_uri)
    db = client.arrocera_erp_db
    inv_supplier = db.invoices_supplier
    print("Conectado a base de datos")

    creds = load_all_credentials()
    if not creds:
        raise RuntimeError("No SII_USER_N / SII_PASS_N found in environment.")

    all_dfs = []
    print("Obteniendo datos de facturas desde SII")
    for user, pw in creds.items():
        print(f"Scraping facturas para {user}…")
        scraper = SiiScraper(user, pw, headless=True)
        df = scraper.scrape_all()
        df["sii_user"] = user

        df_cleaned = clean_and_normalize(df)
        print("Limpiando datos")

        total = len(df_cleaned)
        inserted = 0
        updated = 0
        for _, row in tqdm(df_cleaned.iterrows(), total=total, 
                        desc="Sicronizando facturas", unit="inv"):
            
            # build your dedupe filter
            filt = {
                "supplier_id": row["supplier_id"],
                "number": row["number"],
            }

            data = row.to_dict()

            result = inv_supplier.update_one(
                filt,
                {"$set": {"status": data["status"]}}
            )

            if result.matched_count:
                # an existing document was found and updated
                updated += 1
            else:
                # no existing doc → insert it
                inv_supplier.insert_one(data)
                inserted += 1

        print(f"\nFinalizado: {inserted} nuevas facturas insertadas, {updated} facturas actualizadas")

def debug_scraper(): 

    atlas_uri = os.getenv("MONGODB_URI")
    client = MongoClient(atlas_uri)
    db = client.arrocera_erp_db
    inv_supplier = db.invoices_supplier
    print("Conectado a base de datos")

    creds = load_all_credentials()
    if not creds:
        raise RuntimeError("No SII_USER_N / SII_PASS_N found in environment.")

    all_dfs = []
    print("Obteniendo datos de facturas desde SII")

    scraper = SiiScraper(user="", pwd="", use_certificate=True, headless=False)
    df = scraper.scrape_all()
    df["sii_user"] = ""
    all_dfs.append(df)

    print(all_dfs)

    df = pd.concat(all_dfs, ignore_index=True)
    df.to_csv("compras_df.csv", sep=";")

    df_cleaned = clean_and_normalize(df)
    print("Limpiando datos")

    total = len(df_cleaned)
    inserted = 0
    updated = 0
    for _, row in tqdm(df_cleaned.iterrows(), total=total, 
                      desc="Sicronizando facturas", unit="inv"):
        
        # build your dedupe filter
        filt = {
            "supplier_id": row["supplier_id"],
            "number":      row["number"],
        }

        data = row.to_dict()

        result = inv_supplier.update_one(
            filt,
            {"$set": {"status": data["status"]}}
        )

        if result.matched_count:
            # an existing document was found and updated
            updated += 1
        else:
            # no existing doc → insert it
            inv_supplier.insert_one(data)
            inserted += 1

    print(f"\nFinalizado: {inserted} nuevas facturas insertadas, {updated} facturas actualizadas")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run the SII scraper")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="run the debug_scraper() instead of main()"
    )
    args = parser.parse_args()

    if args.debug:
        debug_scraper()
    else:
        main()