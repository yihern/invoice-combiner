import os
import pandas as pd
import streamlit as st
import pdfplumber
import re

def parse_excel_csv(file, filename):
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        # Try to identify item and amount columns heuristically
        item_col = next((col for col in df.columns if 'desc' in col.lower() or 'item' in col.lower()), df.columns[0])
        amount_col = next((col for col in df.columns if 'amount' in col.lower() or 'total' in col.lower()), None)
        if amount_col is None:
            return pd.DataFrame()
        return pd.DataFrame({
            "Item Description": df[item_col].astype(str),
            "Amount (SGD)": pd.to_numeric(df[amount_col], errors='coerce'),
            "Source": filename
        }).dropna(subset=["Amount (SGD)"])
    except:
        return pd.DataFrame()

def parse_pdf(file, filename):
    try:
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
        # Heuristic pattern to get rows with service and amount
        matches = re.findall(r"(?i)(.+?)\s+(?:SGD\s*)?(\d+[.,]?\d*)\s*", text)
        data = []
        for desc, amount in matches:
            amount = amount.replace(",", "")
            try:
                amount_val = float(amount)
                data.append({
                    "Item Description": desc.strip(),
                    "Amount (SGD)": amount_val,
                    "Source": filename
                })
            except:
                continue
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()


def main():
    st.title("Invoice Combiner & Extractor")
    st.write("Upload multiple invoices (CSV, Excel, PDF) to combine line items into a unified summary.")

    uploaded_files = st.file_uploader("Upload invoice files", accept_multiple_files=True, type=["csv", "xlsx", "xls", "pdf"])

    if uploaded_files:
        all_data = []
        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            if filename.endswith((".csv", ".xlsx", ".xls")):
                df = parse_excel_csv(uploaded_file, filename)
            elif filename.endswith(".pdf"):
                df = parse_pdf(uploaded_file, filename)
            else:
                df = pd.DataFrame()
            all_data.append(df)

        combined_df = pd.concat(all_data, ignore_index=True)

        if not combined_df.empty:
            total_row = pd.DataFrame({
                "Item Description": ["TOTAL"],
                "Amount (SGD)": [combined_df["Amount (SGD)"].sum()],
                "Source": [""]
            })
            final_df = pd.concat([combined_df, total_row], ignore_index=True)
            st.success("Invoices combined successfully!")
            st.dataframe(final_df)

            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Combined CSV", csv, "combined_invoices.csv", "text/csv")
        else:
            st.warning("No invoice data could be extracted from the uploaded files.")

if __name__ == "__main__":
    main()
