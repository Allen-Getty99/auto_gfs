
import pdfplumber
import pandas as pd
import re

# === CONFIGURATION ===
filename = input("Enter invoice filename: ")
pdf_file_path = filename
excel_file_path = "GFS_DATABASE.xlsx"

# Python 3 compatibility note:
# This script is written for Python 3 and requires these packages:
# - pandas: for Excel processing
# - openpyxl: for Excel file reading (used by pandas)
# - pdfplumber: for PDF processing
#
# Setup instructions:
# 1. Navigate to the project directory:
#    cd /Users/allengettyliquigan/Downloads/Project_Auto_GFS
#
# 2. Create a virtual environment:
#    python3 -m venv gfs_env
#
# 3. Activate the virtual environment:
#    - On Mac/Linux: source gfs_env/bin/activate
#    - On Windows: gfs_env\Scripts\activate
#
# 4. Install required packages:
#    pip install pandas openpyxl pdfplumber
#
# 5. Run the script:
#    python3 auto_gfs_v2.1_stable.py

# === LOAD DATABASE ===
db = pd.read_excel(excel_file_path)
db["Item Code"] = db["Item Code"].astype(str)

# === START ===
print("=== Reading Invoice ===")
items = []

with pdfplumber.open(pdf_file_path) as pdf:
    text = ""
    for page in pdf.pages:
        text += page.extract_text()

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        parts = line.split()

        if parts and len(parts) > 1 and parts[0].isdigit() and (6 <= len(parts[0]) <= 7):
            item_code = parts[0]
            quantity = int(parts[1]) if parts[1].isdigit() else 1

            match = db[db["Item Code"] == item_code]
            if not match.empty:
                gl_code = match.iloc[0]["GL Code"]
                gl_desc = match.iloc[0]["GL Description"]
            else:
                gl_code = "ASK BOSS"
                gl_desc = "ASK BOSS FOR PROPER GL"

            # Fix: robust price extraction from end of line
            nums = [float(p) for p in parts if re.match(r"^\d+\.\d{2}$", p)]
            if len(nums) >= 2:
                unit_price = nums[-2]
                line_total = nums[-1]
            else:
                unit_price = 0.0
                line_total = 0.0

            items.append({
                "Item Code": item_code,
                "Quantity": quantity,
                "Unit Price": unit_price,
                "Line Total": line_total,
                "GL Code": gl_code,
                "GL Description": gl_desc
            })

        # Check for extra fees
        if "CONTAINER DEPOSIT" in line and "TOTAL" not in line:
            match = re.search(r"CONTAINER DEPOSIT\s+(\d+\.\d{2})", line)
            if match:
                val = float(match.group(1))
                items.append({
                    "Item Code": "N/A-CD",
                    "Quantity": 1,
                    "Unit Price": val,
                    "Line Total": val,
                    "GL Code": "600265",
                    "GL Description": "Container Deposit"
                })

        if "ECOLOGY FEE" in line and "TOTAL" not in line:
            match = re.search(r"ECOLOGY FEE\s+\d+\.\d{2}\s+(\d+\.\d{2})", line)
            if match:
                val = float(match.group(1))
                items.append({
                    "Item Code": "N/A-EF",
                    "Quantity": 1,
                    "Unit Price": val,
                    "Line Total": val,
                    "GL Code": "600265",
                    "GL Description": "Ecology Fee"
                })

        i += 1

# === GST/HST Extraction ===
gst_hst = 0.00
try:
    with pdfplumber.open(pdf_file_path) as pdf:
        last_page = pdf.pages[-1].extract_text()
        gst_match = re.search(r"GST/HST\s+\$?(\d+\.\d{2})", last_page)
        if gst_match:
            gst_hst = float(gst_match.group(1))
except:
    pass

# === PRINT ===
print("\nItem Code  Quantity  Unit Price  Line Total  GL Code  GL Description")
print("-" * 80)
for item in items:
    print(f"{item['Item Code']:>8} {item['Quantity']:>10} {item['Unit Price']:>11.2f} {item['Line Total']:>11.2f} {str(item['GL Code']):>8} {item['GL Description']}")

# === SUMMARY ===
df = pd.DataFrame(items)
summary_raw = df.groupby("GL Description")["Line Total"].sum().to_dict()

# Merge container deposit and ecology fee into N/A BEV
na_bev_total = summary_raw.get("N/A BEV", 0.0) + summary_raw.get("Container Deposit", 0.0) + summary_raw.get("Ecology Fee", 0.0)

# Rebuild final summary dict
final_summary = {}
for k, v in summary_raw.items():
    if k in ["Container Deposit", "Ecology Fee"]:
        continue
    elif k == "N/A BEV":
        final_summary["N/A BEV"] = na_bev_total
    else:
        final_summary[k] = v

# Print final merged summary
print("\nSummary by GL Description:")
for k, v in final_summary.items():
    print(f"{k:30} ${v:.2f}")

print(f"\nGST/HST: ${gst_hst:.2f}")
print(f"\nGrand Total: ${sum(final_summary.values()) + gst_hst:.2f}")
print("\n=== DONE ===")
