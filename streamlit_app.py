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
You are a helpful assistant that extracts invoice line items from raw text.
Extract all individual line items into a table with columns: Item Description, Amount (SGD), and Source.

Text:
{text}

Respond only in CSV format. The 'Source' column should be '{filename}'.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a document parser."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )

    csv_output = response.choices[0].message.content
    return pd.read_csv(io.StringIO(csv_output))

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
    st.write("Upload PDFs or Excel files. The app uses GPT-4 to extract invoice line items.")

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
            total_row = pd.DataFrame({
                "Item Description": ["TOTAL"],
                "Amount (SGD)": [combined_df["Amount (SGD)"].sum()],
                "Source": [""]
            })
            final_df = pd.concat([combined_df, total_row], ignore_index=True)

            st.success("Invoices extracted and combined successfully!")
            st.dataframe(final_df)

            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Combined CSV", csv, "combined_invoices.csv", "text/csv")
        else:
            st.warning("No data could be extracted.")

if __name__ == "__main__":
    main()
