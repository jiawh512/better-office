#!/usr/bin/env python3
"""Comprehensive global market analysis for workspace-bench."""

import csv
import json
from collections import defaultdict

BASE = "/private/tmp/wb_task_107_manual/Global Business"
MARKETS = ["USCA", "Asia Pacific", "Europe", "LATAM", "Africa"]

def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def read_product_info():
    path = f"{BASE}/USCA/product_info.csv"
    products = {}
    for row in read_csv(path):
        products[row["Product ID"]] = {
            "Category": row["Category"],
            "Sub-Category": row["Sub-Category"],
            "Product Name": row["Product Name"],
        }
    return products

products = read_product_info()

# --- Load all orders ---
all_orders = []
for market in MARKETS:
    for row in read_csv(f"{BASE}/{market}/orders.csv"):
        row["Market"] = market
        row["Sales"] = float(row["Sales"])
        row["Profit"] = float(row["Profit"])
        row["Quantity"] = int(row["Quantity"])
        row["Discount"] = float(row["Discount"])
        row["Shipping Cost"] = float(row["Shipping Cost"])
        row["Category"] = products.get(row["Product ID"], {}).get("Category", "Unknown")
        row["Sub-Category"] = products.get(row["Product ID"], {}).get("Sub-Category", "Unknown")
        all_orders.append(row)

print(f"Total orders loaded: {len(all_orders)}")

# ===== (1) Market comparison =====
print("\n" + "="*80)
print("(1) MARKET SALES & PROFIT COMPARISON")
print("="*80)

market_stats = defaultdict(lambda: {"Sales": 0, "Profit": 0, "Orders": 0, "Cost": 0})
for o in all_orders:
    m = o["Market"]
    market_stats[m]["Sales"] += o["Sales"]
    market_stats[m]["Profit"] += o["Profit"]
    market_stats[m]["Orders"] += 1
    market_stats[m]["Cost"] += o["Shipping Cost"]

mkt_rows = []
for m in MARKETS:
    s = market_stats[m]
    margin = (s["Profit"] / s["Sales"] * 100) if s["Sales"] else 0
    print(f"{m:15s} | Orders: {s['Orders']:4d} | Sales: ${s['Sales']:>10.2f} | Profit: ${s['Profit']:>10.2f} | Margin: {margin:5.2f}%")
    mkt_rows.append((m, s["Orders"], s["Sales"], s["Profit"], margin))

# ===== (2) Category profitability by market =====
print("\n" + "="*80)
print("(2) CATEGORY PROFITABILITY BY MARKET")
print("="*80)

cat_market = defaultdict(lambda: defaultdict(lambda: {"Sales": 0, "Profit": 0, "Orders": 0}))
for o in all_orders:
    cat_market[o["Market"]][o["Category"]]["Sales"] += o["Sales"]
    cat_market[o["Market"]][o["Category"]]["Profit"] += o["Profit"]
    cat_market[o["Market"]][o["Category"]]["Orders"] += 1

# Also global categories
global_cat = defaultdict(lambda: {"Sales": 0, "Profit": 0, "Orders": 0})
for o in all_orders:
    global_cat[o["Category"]]["Sales"] += o["Sales"]
    global_cat[o["Category"]]["Profit"] += o["Profit"]
    global_cat[o["Category"]]["Orders"] += 1

categories = ["Furniture", "Office Supplies", "Technology"]
for cat in categories:
    print(f"\n--- {cat} ---")
    for m in MARKETS:
        d = cat_market[m][cat]
        margin = (d["Profit"] / d["Sales"] * 100) if d["Sales"] else 0
        print(f"  {m:15s} | Orders: {d['Orders']:3d} | Sales: ${d['Sales']:>9.2f} | Profit: ${d['Profit']:>9.2f} | Margin: {margin:6.2f}%")
    g = global_cat[cat]
    g_margin = (g["Profit"] / g["Sales"] * 100) if g["Sales"] else 0
    print(f"  {'GLOBAL':15s} | Orders: {g['Orders']:3d} | Sales: ${g['Sales']:>9.2f} | Profit: ${g['Profit']:>9.2f} | Margin: {g_margin:6.2f}%")

# Sub-category deep dive
print("\n--- Sub-Category Deep Dive (Global) ---")
subcat_global = defaultdict(lambda: {"Sales": 0, "Profit": 0, "Orders": 0})
for o in all_orders:
    sc = o["Sub-Category"]
    subcat_global[sc]["Sales"] += o["Sales"]
    subcat_global[sc]["Profit"] += o["Profit"]
    subcat_global[sc]["Orders"] += 1

for sc in sorted(subcat_global.keys()):
    d = subcat_global[sc]
    margin = (d["Profit"] / d["Sales"] * 100) if d["Sales"] else 0
    print(f"  {sc:25s} | Orders: {d['Orders']:3d} | Sales: ${d['Sales']:>9.2f} | Profit: ${d['Profit']:>9.2f} | Margin: {margin:6.2f}%")

# ===== (3) Logistics Cost Impact =====
print("\n" + "="*80)
print("(3) LOGISTICS COST IMPACT ON PROFITS")
print("="*80)

market_logistics = defaultdict(lambda: {"Total_Shipping": 0, "Total_Profit": 0, "Total_Sales": 0, "Orders": 0, "Ship_Modes": defaultdict(lambda: {"Orders": 0, "Cost": 0, "Profit": 0, "Sales": 0})})
for o in all_orders:
    m = o["Market"]
    sm = o["Ship Mode"]
    market_logistics[m]["Total_Shipping"] += o["Shipping Cost"]
    market_logistics[m]["Total_Profit"] += o["Profit"]
    market_logistics[m]["Total_Sales"] += o["Sales"]
    market_logistics[m]["Orders"] += 1
    market_logistics[m]["Ship_Modes"][sm]["Orders"] += 1
    market_logistics[m]["Ship_Modes"][sm]["Cost"] += o["Shipping Cost"]
    market_logistics[m]["Ship_Modes"][sm]["Profit"] += o["Profit"]
    market_logistics[m]["Ship_Modes"][sm]["Sales"] += o["Sales"]

for m in MARKETS:
    d = market_logistics[m]
    ratio = (d["Total_Shipping"] / d["Total_Profit"] * 100) if d["Total_Profit"] else 0
    print(f"\n{m:15s}: Total Shipping=${d['Total_Shipping']:>8.2f}, Total Profit=${d['Total_Profit']:>8.2f}, Ship/Profit={ratio:5.1f}%")
    print(f"  {'Ship Mode':20s} | {'Orders':5s} | {'Shipping Cost':>12s} | {'Profit':>12s} | {'Cost/Profit':>10s}")
    for sm, sd in sorted(d["Ship_Modes"].items(), key=lambda x: -x[1]["Cost"]):
        spr = (sd["Cost"] / sd["Profit"] * 100) if sd["Profit"] else 0
        print(f"  {sm:20s} | {sd['Orders']:5d} | ${sd['Cost']:>9.2f} | ${sd['Profit']:>9.2f} | {spr:8.1f}%")

# Global logistics
print("\n--- Global Logistics Summary ---")
global_log = {"Total_Shipping": 0, "Total_Profit": 0, "Total_Sales": 0, "Orders": 0}
global_ship_mode = defaultdict(lambda: {"Orders": 0, "Cost": 0, "Profit": 0, "Sales": 0})
for o in all_orders:
    global_log["Total_Shipping"] += o["Shipping Cost"]
    global_log["Total_Profit"] += o["Profit"]
    global_log["Total_Sales"] += o["Sales"]
    global_log["Orders"] += 1
    sm = o["Ship Mode"]
    global_ship_mode[sm]["Orders"] += 1
    global_ship_mode[sm]["Cost"] += o["Shipping Cost"]
    global_ship_mode[sm]["Profit"] += o["Profit"]
    global_ship_mode[sm]["Sales"] += o["Sales"]

ratio = (global_log["Total_Shipping"] / global_log["Total_Profit"] * 100) if global_log["Total_Profit"] else 0
print(f"Total Shipping=${global_log['Total_Shipping']:>10.2f}, Total Profit=${global_log['Total_Profit']:>10.2f}, Ship/Profit={ratio:5.1f}%")
print(f"{'Ship Mode':20s} | {'Orders':5s} | {'Cost/Order':>10s} | {'Profit/Order':>12s} | {'Margin':>8s}")
for sm, sd in sorted(global_ship_mode.items(), key=lambda x: -x[1]["Cost"]):
    cost_po = sd["Cost"] / sd["Orders"] if sd["Orders"] else 0
    profit_po = sd["Profit"] / sd["Orders"] if sd["Orders"] else 0
    margin = (sd["Profit"] / sd["Sales"] * 100) if sd["Sales"] else 0
    print(f"  {sm:20s} | {sd['Orders']:5d} | ${cost_po:>7.2f} | ${profit_po:>9.2f} | {margin:6.2f}%")

# ===== (4) Customer Segment Contribution =====
print("\n" + "="*80)
print("(4) CUSTOMER SEGMENT CONTRIBUTION")
print("="*80)

segment_market = defaultdict(lambda: defaultdict(lambda: {"Sales": 0, "Profit": 0, "Orders": 0}))
global_segment = defaultdict(lambda: {"Sales": 0, "Profit": 0, "Orders": 0})
for o in all_orders:
    seg = o["Segment"]
    m = o["Market"]
    segment_market[m][seg]["Sales"] += o["Sales"]
    segment_market[m][seg]["Profit"] += o["Profit"]
    segment_market[m][seg]["Orders"] += 1
    global_segment[seg]["Sales"] += o["Sales"]
    global_segment[seg]["Profit"] += o["Profit"]
    global_segment[seg]["Orders"] += 1

segments = ["Consumer", "Corporate", "Home Office"]
print(f"\n{'Market':15s} | {'Segment':15s} | {'Orders':5s} | {'Sales':>10s} | {'Profit':>10s} | {'Margin':>8s} | {'% of Mkt Sales':>14s}")
for m in MARKETS:
    mkt_total_sales = sum(segment_market[m][s]["Sales"] for s in segments)
    for seg in segments:
        d = segment_market[m][seg]
        margin = (d["Profit"] / d["Sales"] * 100) if d["Sales"] else 0
        pct = (d["Sales"] / mkt_total_sales * 100) if mkt_total_sales else 0
        print(f"{m:15s} | {seg:15s} | {d['Orders']:5d} | ${d['Sales']:>8.2f} | ${d['Profit']:>8.2f} | {margin:6.2f}% | {pct:12.1f}%")

print(f"\n{'GLOBAL':15s} | {'Segment':15s} | {'Orders':5s} | {'Sales':>10s} | {'Profit':>10s} | {'Margin':>8s} | {'% of Global Sales':>16s}")
global_total_sales = sum(global_segment[s]["Sales"] for s in segments)
for seg in segments:
    d = global_segment[seg]
    margin = (d["Profit"] / d["Sales"] * 100) if d["Sales"] else 0
    pct = (d["Sales"] / global_total_sales * 100) if global_total_sales else 0
    print(f"{'GLOBAL':15s} | {seg:15s} | {d['Orders']:5d} | ${d['Sales']:>8.2f} | ${d['Profit']:>8.2f} | {margin:6.2f}% | {pct:14.1f}%")

# ===== (5) Recommendations =====
print("\n" + "="*80)
print("(5) KEY INSIGHTS & RECOMMENDATIONS")
print("="*80)

# Best/worst markets by profit margin
sorted_markets = sorted(mkt_rows, key=lambda x: x[4], reverse=True)
print(f"\nMarket Ranking by Profit Margin:")
for i, (m, o, sa, p, mg) in enumerate(sorted_markets, 1):
    print(f"  {i}. {m:15s} - Margin: {mg:5.2f}% | Sales: ${sa:>8.2f} | Profit: ${p:>8.2f}")

# Best categories per market
print(f"\nBest Performing Category per Market:")
for m in MARKETS:
    best_cat = max(categories, key=lambda c: cat_market[m][c]["Profit"])
    best_margin = (cat_market[m][best_cat]["Profit"] / cat_market[m][best_cat]["Sales"] * 100) if cat_market[m][best_cat]["Sales"] else 0
    print(f"  {m:15s} -> {best_cat:20s} (Profit: ${cat_market[m][best_cat]['Profit']:>8.2f}, Margin: {best_margin:5.2f}%)")

# Worst categories per market
print(f"\nWorst (or Lowest) Performing Category per Market:")
for m in MARKETS:
    worst_cat = min(categories, key=lambda c: cat_market[m][c]["Profit"])
    worst_margin = (cat_market[m][worst_cat]["Profit"] / cat_market[m][worst_cat]["Sales"] * 100) if cat_market[m][worst_cat]["Sales"] else 0
    print(f"  {m:15s} -> {worst_cat:20s} (Profit: ${cat_market[m][worst_cat]['Profit']:>8.2f}, Margin: {worst_margin:5.2f}%)")

# Logistics - shipping cost ratio
print(f"\nLogistics Cost Impact (Shipping as % of Profit):")
for m in MARKETS:
    d = market_logistics[m]
    ratio = (d["Total_Shipping"] / d["Total_Profit"] * 100) if d["Total_Profit"] else 0
    print(f"  {m:15s}: Ship/Profit = {ratio:5.1f}% ({'CRITICAL' if ratio > 100 else 'HIGH' if ratio > 70 else 'MODERATE' if ratio > 45 else 'LOW'})")

# Customer segment ranking
print(f"\nCustomer Segment Ranking (by Global Profit):")
sorted_segs = sorted(segments, key=lambda s: global_segment[s]["Profit"], reverse=True)
for seg in sorted_segs:
    d = global_segment[seg]
    margin = (d["Profit"] / d["Sales"] * 100) if d["Sales"] else 0
    print(f"  {seg:15s}: Sales=${d['Sales']:>8.2f}, Profit=${d['Profit']:>8.2f}, Margin={margin:5.2f}%")

# Print total global figures
print(f"\n--- Global Totals ---")
total_sales = sum(market_stats[m]["Sales"] for m in MARKETS)
total_profit = sum(market_stats[m]["Profit"] for m in MARKETS)
total_orders = sum(market_stats[m]["Orders"] for m in MARKETS)
total_shipping = sum(market_stats[m]["Cost"] for m in MARKETS)
print(f"Total Orders: {total_orders}")
print(f"Total Sales: ${total_sales:,.2f}")
print(f"Total Profit: ${total_profit:,.2f}")
print(f"Total Shipping Cost: ${total_shipping:,.2f}")
print(f"Overall Profit Margin: {(total_profit/total_sales*100):.2f}%")
print(f"Shipping as % of Profit: {(total_shipping/total_profit*100):.1f}%")

print("\n\n=== ANALYSIS COMPLETE ===")
