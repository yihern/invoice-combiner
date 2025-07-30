import os
import pandas as pd
import streamlit as st
import openai
import pdfplumber
import io
import re

# Ensure the new OpenAI client is used correctly (for openai>=1.0.0)
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def call_gpt_to_extract(text, filename):
    prompt = f"""
You are an intelligent document parser. Your task is to extract line items from an invoice.
Each line item typically includes a description and an amount. Carefully analyze the content,
and if necessary, combine multiple lines or fields to create a meaningful description.

Please extract each line item in this invoice as a row in a CSV table with the following columns:
- Item Description (summarize or combine as needed)
- Amount (numbers only, regardless of currency symbol)
- Source (set this value to the filename provided)

If there are totals or subtotals, skip them. Focus only on individual billable line items.
Respond only with valid CSV format — no extra commentary.

Invoice Filename: {filename}
Invoice Text:
{text}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a document parser that extracts structured invoice line items."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        csv_output = response.choices[0].message.content.strip()

        df = pd.read_csv(io.StringIO(csv_output))
        df.columns = [c.strip().lower() for c in df.columns]
        column_map = {
            'item': 'Item Description',
            'item description': 'Item Description',
            'description': 'Item Description',
            'amount': 'Amount',
            'value': 'Amount',
            'price': 'Amount',
            'source': 'Source'
        }
        df = df.rename(columns={c: column_map.get(c, c) for c in df.columns})

        required = {'Item Description', 'Amount', 'Source'}
        if not required.issubset(set(df.columns)):
            raise ValueError("Parsed but missing required columns.\n\nRaw GPT Output:\n" + csv_output)

        return df[['Item Description', 'Amount', 'Source']]

    except Exception as e:
        raise RuntimeError(f"OpenAI API failed or CSV parsing failed: {e}")

def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

def extract_text_from_excel(file):
    try:
        dfs = pd.read_excel(file, sheet_name=None, engine='openpyxl')
    except Exception:
        file.seek(0)
        dfs = pd.read_excel(io.BytesIO(file.read()), sheet_name=None, engine='openpyxl')

    text_lines = []
    for name, df in dfs.items():
        text_lines.extend(df.astype(str).fillna("").apply(lambda x: ' '.join(x), axis=1).tolist())
    return "\n".join(text_lines)

def main():
    st.title("AI-Powered Invoice Combiner")
    st.write("Upload PDFs or Excel files. The app uses GPT-4 to intelligently extract invoice line items.")

    uploaded_files = st.file_uploader("Upload invoice files", accept_multiple_files=True, type=["pdf", "xlsx", "xls"])

    if uploaded_files:
        all_data = []

        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            st.info(f"Processing: {filename}")

            try:
                if filename.endswith(".pdf"):
                    text = extract_text_from_pdf(uploaded_file)
                else:
                    text = extract_text_from_excel(uploaded_file)

                if len(text.strip()) < 30:
                    st.warning(f"Skipping {filename} — too little content.")
                    continue

                df = call_gpt_to_extract(text, filename)
                all_data.append(df)
            except Exception as e:
                st.error(f"Failed to process {filename}: {e}")

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            if "Amount" in combined_df.columns:
                total_row = pd.DataFrame({
                    "Item Description": ["TOTAL"],
                    "Amount": [combined_df["Amount"].sum()],
                    "Source": [""]
                })
                final_df = pd.concat([combined_df, total_row], ignore_index=True)
            else:
                final_df = combined_df

            st.success("Invoices extracted and combined successfully!")
            st.dataframe(final_df)

            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Combined CSV", csv, "combined_invoices.csv", "text/csv")
        else:
            st.warning("No data could be extracted.")

if __name__ == "__main__":
    main()
