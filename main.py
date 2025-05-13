import os
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from pymongo import MongoClient

from sii_scraper.sii_scraper import SiiScraper

load_dotenv()

def clean_and_normalize(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    df = df[["supplier_id", "supplier_name", "number", "date", "date_accepted", "type", "exent_total", "net_total", "iva", "other_tax", "total", "rut_holding"]]

    cols = ["supplier_id", "supplier_name", "type"]

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

def main(): 

    atlas_uri = os.getenv("MONGODB_URI")
    client = MongoClient(atlas_uri)
    db = client.arrocera_erp_db
    inv_supplier = db.invoices_supplier
    print("Conectado a base de datos")

    scraper = SiiScraper()
    print("Obteniendo datos de facturas desde SII")
    df = scraper.scrape_all()
    #For debug
    df.to_csv("compras_df.csv", sep=";")

    df_cleaned = clean_and_normalize(df)
    print("Limpiando datos")

    total = len(df_cleaned)
    inserted = 0

    for _, row in tqdm(df_cleaned.iterrows(), total=total, 
                      desc="Agregando facturas a BBDD", unit="inv"):
        
        # build your dedupe filter
        filt = {
            "supplier_id": row["supplier_id"],
            "number":      row["number"],
        }

        # if no existing document matches…
        if inv_supplier.count_documents(filt, limit=1) == 0:
            # convert the pandas Series → dict and insert
            inv_supplier.insert_one(row.to_dict())
            inserted += 1

    print(f"\nFinalizado: {inserted} nuevas facturas insertadas")

if __name__ == "__main__":
    main()
