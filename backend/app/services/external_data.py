from __future__ import annotations

import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "external"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

ARCHIVE_PATHS = {
    "financials": r"E:\companyfinancials.zip",
    "filings": r"E:\companyfillings.zip",
    "acquisitions": r"E:\madeals.zip",
    "directory": r"E:\company name+location.zip",
}


def _normalize_currency(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text in {"-", "--", "nan", "NaN"}:
        return None
    text = text.replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _read_csv_from_zip(archive_path: str, filename: str, **kwargs: Any) -> pd.DataFrame:
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"External archive not found: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        if filename not in archive.namelist():
            raise FileNotFoundError(f"File {filename} not found in {archive_path}")
        with archive.open(filename) as handle:
            return pd.read_csv(handle, **kwargs)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_external_datasets() -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "ok", "sources": {}, "model_inputs": {}}

    # 1) Company financials -> transform into yearly M&A-friendly financials
    try:
        financials_df = _read_csv_from_zip(ARCHIVE_PATHS["financials"], "Financials.csv")
        financials_df.columns = [column.strip() for column in financials_df.columns]
        financials_df["Year"] = pd.to_numeric(financials_df.get("Year"), errors="coerce")
        financials_df["Revenue"] = financials_df.get("Sales").apply(_normalize_currency)
        financials_df["COGS"] = financials_df.get("COGS").apply(_normalize_currency)
        financials_df["Profit"] = financials_df.get("Profit").apply(_normalize_currency)
        financials_df = financials_df.dropna(subset=["Year", "Revenue", "COGS"])
        financials_df["Operating_Expenses"] = (
            financials_df["Revenue"] - financials_df["COGS"] - financials_df["Profit"]
        ).clip(lower=0)
        yearly = (
            financials_df.groupby("Year", as_index=False)
            .agg(
                Revenue=("Revenue", "sum"),
                COGS=("COGS", "sum"),
                Operating_Expenses=("Operating_Expenses", "sum"),
            )
            .sort_values("Year")
        )
        yearly["EBITDA"] = yearly["Revenue"] - yearly["COGS"] - yearly["Operating_Expenses"]
        yearly["EBITDA_Margin"] = yearly["EBITDA"] / yearly["Revenue"].replace(0, pd.NA)
        yearly = yearly.fillna({"EBITDA_Margin": 0.0})
        financials_summary = yearly.to_dict(orient="records")
        payload["sources"]["financials"] = {
            "archive": ARCHIVE_PATHS["financials"],
            "rows": int(len(financials_df)),
            "summary": financials_summary[-3:],
            "latest_year": int(yearly["Year"].max()) if not yearly.empty else None,
        }
        payload["model_inputs"]["company_a"] = {
            "name": "External Company A",
            "latest_revenue": float(yearly["Revenue"].iloc[-1]) if not yearly.empty else 0.0,
            "latest_ebitda_margin": float(yearly["EBITDA_Margin"].iloc[-1]) if not yearly.empty else 0.0,
        }
        payload["model_inputs"]["company_b"] = {
            "name": "External Company B",
            "latest_revenue": float(yearly["Revenue"].iloc[-2]) if len(yearly) > 1 else 0.0,
            "latest_ebitda_margin": float(yearly["EBITDA_Margin"].iloc[-2]) if len(yearly) > 1 else 0.0,
        }
        yearly.to_csv(DATA_ROOT / "financials_summary.csv", index=False)
    except Exception as exc:  # pragma: no cover - runtime guard
        payload["sources"]["financials"] = {"error": str(exc)}

    # 2) SEC filings -> counts by company and year
    try:
        filings_df = _read_csv_from_zip(
            ARCHIVE_PATHS["filings"],
            "lcf_annual.csv",
            usecols=["name", "period", "filingDate", "type"],
            nrows=5000,
        )
        filings_df = filings_df.rename(columns=str.strip)
        filings_df["name"] = filings_df["name"].fillna("Unknown")
        filings_df["period"] = pd.to_numeric(filings_df.get("period"), errors="coerce")
        filings_df["year"] = filings_df["filingDate"].astype(str).str.slice(0, 4).astype(str)
        filings_df["year"] = pd.to_numeric(filings_df["year"], errors="coerce")
        filing_counts = filings_df.groupby("name").size().sort_values(ascending=False).head(10)
        year_counts = filings_df.groupby("year").size().sort_values(ascending=False).head(10)
        filing_types = filings_df.groupby("type").size().sort_values(ascending=False).head(10)
        payload["sources"]["filings"] = {
            "archive": ARCHIVE_PATHS["filings"],
            "rows": int(len(filings_df)),
            "top_companies": [{"name": name, "filings": int(count)} for name, count in filing_counts.items()],
            "filings_by_year": [{"year": int(year), "filings": int(count)} for year, count in year_counts.items() if pd.notna(year)],
            "filing_types": [{"type": filing_type, "count": int(count)} for filing_type, count in filing_types.items()],
        }
        _write_json(
            DATA_ROOT / "filings_summary.json",
            {
                "top_companies": [{"name": name, "filings": int(count)} for name, count in filing_counts.items()],
                "filings_by_year": [{"year": int(year), "filings": int(count)} for year, count in year_counts.items() if pd.notna(year)],
            },
        )
    except Exception as exc:  # pragma: no cover - runtime guard
        payload["sources"]["filings"] = {"error": str(exc)}

    # 3) Acquisition activity -> M&A event context
    try:
        acquisitions_df = _read_csv_from_zip(
            ARCHIVE_PATHS["acquisitions"],
            "acquisitions_update_2021.csv",
            usecols=["Parent Company", "Acquisition Year", "Country", "Business"],
            nrows=1000,
        )
        acquisitions_df = acquisitions_df.rename(columns=str.strip)
        acquisitions_df["Acquisition Year"] = pd.to_numeric(acquisitions_df.get("Acquisition Year"), errors="coerce")
        parent_counts = acquisitions_df.groupby("Parent Company").size().sort_values(ascending=False).head(10)
        country_counts = acquisitions_df.groupby("Country").size().sort_values(ascending=False).head(10)
        year_counts = acquisitions_df.groupby("Acquisition Year").size().sort_values(ascending=False).head(10)
        payload["sources"]["acquisitions"] = {
            "archive": ARCHIVE_PATHS["acquisitions"],
            "rows": int(len(acquisitions_df)),
            "top_operators": [{"name": name, "deals": int(count)} for name, count in parent_counts.items()],
            "deals_by_country": [{"country": country, "deals": int(count)} for country, count in country_counts.items()],
            "deals_by_year": [{"year": int(year), "deals": int(count)} for year, count in year_counts.items() if pd.notna(year)],
        }
        _write_json(
            DATA_ROOT / "acquisitions_summary.json",
            {
                "top_operators": [{"name": name, "deals": int(count)} for name, count in parent_counts.items()],
                "deals_by_country": [{"country": country, "deals": int(count)} for country, count in country_counts.items()],
            },
        )
    except Exception as exc:  # pragma: no cover - runtime guard
        payload["sources"]["acquisitions"] = {"error": str(exc)}

    # 4) Company directory -> market context for target screening
    try:
        directory_df = _read_csv_from_zip(
            ARCHIVE_PATHS["directory"],
            "companies_sorted.csv",
            usecols=["name", "industry", "country", "year founded"],
            nrows=2000,
        )
        directory_df = directory_df.rename(columns=str.strip)
        industry_counts = directory_df.groupby("industry").size().sort_values(ascending=False).head(10)
        country_counts = directory_df.groupby("country").size().sort_values(ascending=False).head(10)
        payload["sources"]["directory"] = {
            "archive": ARCHIVE_PATHS["directory"],
            "rows": int(len(directory_df)),
            "top_industries": [{"industry": industry, "companies": int(count)} for industry, count in industry_counts.items()],
            "top_countries": [{"country": country, "companies": int(count)} for country, count in country_counts.items()],
        }
        _write_json(
            DATA_ROOT / "directory_summary.json",
            {
                "top_industries": [{"industry": industry, "companies": int(count)} for industry, count in industry_counts.items()],
                "top_countries": [{"country": country, "companies": int(count)} for country, count in country_counts.items()],
            },
        )
    except Exception as exc:  # pragma: no cover - runtime guard
        payload["sources"]["directory"] = {"error": str(exc)}

    payload["model_inputs"]["market_context"] = {
        "filings_signal": payload["sources"].get("filings", {}).get("top_companies", [])[:3],
        "acquisition_signal": payload["sources"].get("acquisitions", {}).get("top_operators", [])[:3],
        "industry_signal": payload["sources"].get("directory", {}).get("top_industries", [])[:3],
    }
    return payload
