import pandas as pd
import json
import os

BASE = "/Users/zxc/deepagents/deepagents/workspace_bench_agent/Sales_Management"

# ===== Load Product Catalog =====
with open(f"{BASE}/Product_Information/product_catalog.json", "r") as f:
    prod_data = json.load(f)
products_df = pd.DataFrame(prod_data["products"])
print(f"Products loaded: {len(products_df)} products")
print(f"Categories: {products_df['Category'].unique()}")
print()

# ===== Load Customer Data =====
customers_df = pd.read_csv(f"{BASE}/Customer_Profiles/customer_list.csv")
print(f"Customers loaded: {len(customers_df)} customers")
print(f"Segments: {customers_df['Segment'].unique()}")
print()

# ===== Load Regional Sales Data =====
regions_files = {
    "Central": f"{BASE}/Regional_Sales_Data/Central_sales_2017.csv",
    "East": f"{BASE}/Regional_Sales_Data/East_sales_2017.csv",
    "South": f"{BASE}/Regional_Sales_Data/South_sales_2017.csv",
    "West": f"{BASE}/Regional_Sales_Data/West_sales_2017.csv",
}

all_sales = []
for region, filepath in regions_files.items():
    df = pd.read_csv(filepath)
    df["SourceRegion"] = region
    all_sales.append(df)
    print(f"{region}: {len(df)} orders")

sales_df = pd.concat(all_sales, ignore_index=True)
print(f"\nTotal sales records: {len(sales_df)}")
print(f"Columns: {list(sales_df.columns)}")
print()

# ===== Merge with product catalog for Category =====
# The sales data has Product ID - merge with products to get Category
sales_with_cat = sales_df.merge(products_df, on="Product ID", how="left")
print(f"After merge with products: {len(sales_with_cat)} records")
print(f"Categories found: {sales_with_cat['Category'].unique()}")
null_cat = sales_with_cat['Category'].isna().sum()
print(f"Records with no category match: {null_cat}")
print()

# ===== Merge with customers for Segment =====
sales_enriched = sales_with_cat.merge(customers_df[["Customer ID", "Segment"]], on="Customer ID", how="left")
print(f"After merge with customers: {len(sales_enriched)} records")
null_seg = sales_enriched['Segment'].isna().sum()
print(f"Records with no segment match: {null_seg}")
print()

# ===== Pivot Table 1: Category × Region =====
print("=" * 60)
print("CATEGORY × REGION SUMMARY")
print("=" * 60)

cat_region = sales_enriched.groupby(["Category", "SourceRegion"]).agg(
    Total_Sales=("Sales", "sum"),
    Total_Profit=("Profit", "sum"),
    Order_Count=("Order ID", "nunique")
).reset_index()

cat_region_pivot_sales = cat_region.pivot(index="Category", columns="SourceRegion", values="Total_Sales").fillna(0)
cat_region_pivot_profit = cat_region.pivot(index="Category", columns="SourceRegion", values="Total_Profit").fillna(0)
cat_region_pivot_orders = cat_region.pivot(index="Category", columns="SourceRegion", values="Order_Count").fillna(0).astype(int)

print("\nSales by Category × Region:")
print(cat_region_pivot_sales.to_string())
print("\nProfit by Category × Region:")
print(cat_region_pivot_profit.to_string())
print("\nOrder Count by Category × Region:")
print(cat_region_pivot_orders.to_string())

# Category totals across all regions
cat_totals = sales_enriched.groupby("Category").agg(
    Total_Sales=("Sales", "sum"),
    Total_Profit=("Profit", "sum"),
    Order_Count=("Order ID", "nunique")
).reset_index()
cat_totals["Profit_Margin"] = (cat_totals["Total_Profit"] / cat_totals["Total_Sales"] * 100).round(2)

print("\n\nCategory Totals (All Regions):")
print(cat_totals.to_string())

# ===== Pivot Table 2: Category × Segment =====
print("\n" + "=" * 60)
print("CATEGORY × SEGMENT SUMMARY")
print("=" * 60)

cat_segment = sales_enriched.groupby(["Category", "Segment"]).agg(
    Total_Sales=("Sales", "sum"),
    Total_Profit=("Profit", "sum"),
    Order_Count=("Order ID", "nunique")
).reset_index()

cat_seg_pivot_sales = cat_segment.pivot(index="Category", columns="Segment", values="Total_Sales").fillna(0)
cat_seg_pivot_profit = cat_segment.pivot(index="Category", columns="Segment", values="Total_Profit").fillna(0)
cat_seg_pivot_orders = cat_segment.pivot(index="Category", columns="Segment", values="Order_Count").fillna(0).astype(int)

print("\nSales by Category × Segment:")
print(cat_seg_pivot_sales.to_string())
print("\nProfit by Category × Segment:")
print(cat_seg_pivot_profit.to_string())
print("\nOrder Count by Category × Segment:")
print(cat_seg_pivot_orders.to_string())

# ===== Highest and Lowest Profit Margin Categories =====
print("\n" + "=" * 60)
print("PROFIT MARGIN ANALYSIS BY CATEGORY")
print("=" * 60)

cat_margins = cat_totals.sort_values("Profit_Margin", ascending=False)
print(cat_margins[["Category", "Total_Sales", "Total_Profit", "Profit_Margin"]].to_string())

highest = cat_margins.iloc[0]
lowest = cat_margins.iloc[-1]
print(f"\n=== Highest Profit Margin: {highest['Category']} ({highest['Profit_Margin']:.2f}%) ===")
print(f"   Total Sales: ${highest['Total_Sales']:.2f}, Total Profit: ${highest['Total_Profit']:.2f}")
print(f"\n=== Lowest Profit Margin: {lowest['Category']} ({lowest['Profit_Margin']:.2f}%) ===")
print(f"   Total Sales: ${lowest['Total_Sales']:.2f}, Total Profit: ${lowest['Total_Profit']:.2f}")

# ===== Analysis of Orders with Discount ≥ 50% =====
print("\n" + "=" * 60)
print("DISCOUNT ≥ 50% ORDER ANALYSIS")
print("=" * 60)

# Load high discount orders from the dedicated file
high_discount_df = pd.read_csv(f"{BASE}/Regional_Sales_Data/high_discount_orders.csv")
print(f"\nHigh discount orders file records: {len(high_discount_df)}")

# Also filter from the full merged dataset
discount_50plus = sales_enriched[sales_enriched["Discount"] >= 0.5].copy()
print(f"Orders with discount >= 50% (from full data): {len(discount_50plus)}")

discount_summary = discount_50plus.groupby("Category").agg(
    Order_Count=("Order ID", "nunique"),
    Total_Sales=("Sales", "sum"),
    Total_Profit=("Profit", "sum"),
    Avg_Discount=("Discount", "mean")
).reset_index()
discount_summary["Avg_Discount"] = (discount_summary["Avg_Discount"] * 100).round(2)

print("\nDiscount ≥ 50% Orders by Category:")
print(discount_summary.to_string())

total_discount_sales = discount_50plus["Sales"].sum()
total_discount_profit = discount_50plus["Profit"].sum()
print(f"\nTotal Sales (Discount >= 50%): ${total_discount_sales:.2f}")
print(f"Total Profit (Discount >= 50%): ${total_discount_profit:.2f}")
if total_discount_profit < 0:
    print("CONCLUSION: Orders with discounts >= 50% are OVERALL LOSING money (net loss).")
else:
    print("CONCLUSION: Orders with discounts >= 50% are overall PROFITABLE.")

# Check how many are profitable vs loss-making
profitable_high_discount = (discount_50plus["Profit"] > 0).sum()
loss_high_discount = (discount_50plus["Profit"] < 0).sum()
print(f"Profitable high-discount orders: {profitable_high_discount}")
print(f"Loss-making high-discount orders: {loss_high_discount}")

# Save intermediate results for report generation
results = {
    "cat_region_sales": cat_region_pivot_sales.to_dict(),
    "cat_region_profit": cat_region_pivot_profit.to_dict(),
    "cat_region_orders": cat_region_pivot_orders.to_dict(),
    "cat_segment_sales": cat_seg_pivot_sales.to_dict(),
    "cat_segment_profit": cat_seg_pivot_profit.to_dict(),
    "cat_segment_orders": cat_seg_pivot_orders.to_dict(),
    "category_margins": cat_margins.to_dict("records"),
    "highest_margin": {"category": highest["Category"], "margin": round(highest["Profit_Margin"], 2)},
    "lowest_margin": {"category": lowest["Category"], "margin": round(lowest["Profit_Margin"], 2)},
    "discount_50plus": discount_summary.to_dict("records"),
    "discount_50plus_total_sales": round(total_discount_sales, 2),
    "discount_50plus_total_profit": round(total_discount_profit, 2),
    "discount_50plus_profitable": int(profitable_high_discount),
    "discount_50plus_loss": int(loss_high_discount),
}

with open(f"{BASE}/analysis_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print("\n\nAnalysis complete. Results saved.")
