#!/usr/bin/env python3

import csv
import re
import base64
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def parse_date(date_str):
    date_obj = datetime.strptime(date_str.strip(), "%b %d, %Y")
    return date_obj.strftime("%Y-%m-%d")


def is_date_range(text):
    return bool(re.match(r'^\w{3} \d{1,2}, \d{4} - \w{3} \d{1,2}, \d{4}$', text.strip()))


def extract_item_name(item):
    title_elem = item.find('label', class_='pli-title') or item.find('div', class_='pli-title')
    if not title_elem:
        return None
    
    item_name_elem = title_elem.find('div', attrs={'aria-label': True})
    if item_name_elem:
        item_name = item_name_elem.get('aria-label', '').strip()
    else:
        item_name = ' '.join(title_elem.get_text().split()).strip()
    
    if not item_name:
        return None
    
    if is_date_range(item_name):
        publisher_div = item.find('div', class_='pli-publisher')
        if publisher_div:
            publisher_name = publisher_div.get_text(strip=True)
            if publisher_name:
                return publisher_name
    
    publisher_div = item.find('div', class_='pli-publisher')
    if publisher_div:
        publisher_name = publisher_div.get_text(strip=True)
        if publisher_name and publisher_name != item_name:
            return f"{publisher_name} - {item_name}"
    
    return item_name


def is_subscription_item(item):
    if item.find('div', class_='pli-subscription-info'):
        return True
    
    item_name = extract_item_name(item)
    if item_name and any(keyword in item_name for keyword in ['iCloud+', 'iCloud', 'subscription', 'Subscription']):
        return True
    
    return False


def extract_amount(price_element):
    if not price_element:
        return None
    
    free_span = price_element.find('span', attrs={'data-auto-test-id': lambda x: x and 'Label.Free' in x})
    if free_span:
        return None
    
    price_text = price_element.get_text(strip=True)
    if "Free" in price_text or price_text == "$0.00" or not price_text:
        return None
    
    amount_match = re.search(r'\$([0-9]+\.?[0-9]*)', price_text)
    if amount_match:
        amount = amount_match.group(1)
        if float(amount) > 0:
            return f"${amount}"
    
    return None


def extract_transactions(html_file):
    transactions = []
    
    print(f"Reading HTML file: {html_file}")
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    purchase_divs = soup.find_all('div', class_='purchase')
    print(f"Found {len(purchase_divs)} purchase entries")
    
    for purchase in purchase_divs:
        date_span = purchase.find('span', class_='invoice-date')
        if not date_span:
            continue
        
        formatted_date = parse_date(date_span.get_text(strip=True))
        
        items_list = purchase.find('ul', class_='pli-list applicable-items')
        if not items_list:
            continue
        
        items = items_list.find_all('li', class_='pli')
        
        for item in items:
            item_name = extract_item_name(item)
            if not item_name:
                continue
            
            price_div = item.find('div', class_='pli-price')
            if not price_div:
                continue
            
            amount = extract_amount(price_div)
            if amount is None:
                continue
            
            transactions.append({
                'date': formatted_date,
                'item_name': item_name,
                'amount': amount,
                'is_subscription': is_subscription_item(item)
            })
    
    return transactions


def write_csv(transactions, output_file):
    print(f"Writing {len(transactions)} transactions to {output_file}")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Date', 'Item Name', 'Amount', 'Subscription']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for transaction in transactions:
            writer.writerow({
                'Date': transaction['date'],
                'Item Name': transaction['item_name'],
                'Amount': transaction['amount'],
                'Subscription': 'Yes' if transaction['is_subscription'] else 'No'
            })
    
    print(f"Successfully wrote {len(transactions)} transactions to {output_file}")


def analyze_repeated_transactions(transactions):
    item_stats = defaultdict(lambda: {'count': 0, 'total_amount': 0.0})
    
    for transaction in transactions:
        item_name = transaction['item_name']
        amount = float(transaction['amount'].replace('$', ''))
        item_stats[item_name]['count'] += 1
        item_stats[item_name]['total_amount'] += amount
    
    repeated = [
        {
            'item_name': item_name,
            'count': stats['count'],
            'total_amount': stats['total_amount']
        }
        for item_name, stats in item_stats.items()
        if stats['count'] > 1
    ]
    
    repeated.sort(key=lambda x: x['total_amount'], reverse=True)
    return repeated


def analyze_yearly_transactions(transactions):
    yearly_stats = defaultdict(float)
    
    for transaction in transactions:
        year = transaction['date'][:4]
        amount = float(transaction['amount'].replace('$', ''))
        yearly_stats[year] += amount
    
    return dict(sorted(yearly_stats.items()))


def create_repeated_transactions_chart(repeated_data, top_n=20):
    if not repeated_data:
        return None
    
    top_items = repeated_data[:top_n]
    item_names = [item['item_name'][:40] for item in top_items]
    amounts = [item['total_amount'] for item in top_items]
    
    plt.figure(figsize=(10, max(6, len(top_items) * 0.4)))
    plt.barh(range(len(item_names)), amounts, color='steelblue')
    plt.yticks(range(len(item_names)), item_names)
    plt.xlabel('Total Amount ($)')
    plt.title(f'Top {len(top_items)} Repeated Transactions by Total Amount')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64


def create_yearly_chart(yearly_data):
    if not yearly_data:
        return None
    
    years = list(yearly_data.keys())
    amounts = list(yearly_data.values())
    
    plt.figure(figsize=(10, 6))
    plt.bar(years, amounts, color='steelblue')
    plt.xlabel('Year')
    plt.ylabel('Total Amount ($)')
    plt.title('Total Spending by Year')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64


def generate_summary_report(transactions, output_file):
    repeated_data = analyze_repeated_transactions(transactions)
    yearly_data = analyze_yearly_transactions(transactions)
    
    total_transactions = len(transactions)
    total_amount = sum(float(t['amount'].replace('$', '')) for t in transactions)
    subscription_count = sum(1 for t in transactions if t['is_subscription'])
    one_time_count = total_transactions - subscription_count
    
    repeated_chart = create_repeated_transactions_chart(repeated_data)
    yearly_chart = create_yearly_chart(yearly_data)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Apple Transactions Summary</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid steelblue;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-box {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid steelblue;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: steelblue;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .chart-container {{
            margin: 30px 0;
            text-align: center;
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Apple Transactions Summary Report</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{total_transactions}</div>
                <div class="stat-label">Total Transactions</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">${total_amount:,.2f}</div>
                <div class="stat-label">Total Amount</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{subscription_count}</div>
                <div class="stat-label">Subscriptions</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{one_time_count}</div>
                <div class="stat-label">One-time Purchases</div>
            </div>
        </div>
        
        <h2>Repeated Transactions</h2>
        <p>Items purchased more than once, sorted by total amount spent.</p>
"""
    
    if repeated_data:
        html_content += """
        <table>
            <thead>
                <tr>
                    <th>Item Name</th>
                    <th>Count</th>
                    <th>Total Amount</th>
                </tr>
            </thead>
            <tbody>
"""
        for item in repeated_data:
            html_content += f"""
                <tr>
                    <td>{item['item_name']}</td>
                    <td>{item['count']}</td>
                    <td>${item['total_amount']:,.2f}</td>
                </tr>
"""
        html_content += """
            </tbody>
        </table>
"""
        
        if repeated_chart:
            html_content += f"""
        <div class="chart-container">
            <img src="data:image/png;base64,{repeated_chart}" alt="Repeated Transactions Chart">
        </div>
"""
    else:
        html_content += "<p>No repeated transactions found.</p>"
    
    html_content += """
        <h2>Yearly Spending</h2>
        <p>Total spending aggregated by year.</p>
"""
    
    if yearly_data:
        html_content += """
        <table>
            <thead>
                <tr>
                    <th>Year</th>
                    <th>Total Amount</th>
                </tr>
            </thead>
            <tbody>
"""
        for year, amount in yearly_data.items():
            html_content += f"""
                <tr>
                    <td>{year}</td>
                    <td>${amount:,.2f}</td>
                </tr>
"""
        html_content += """
            </tbody>
        </table>
"""
        
        if yearly_chart:
            html_content += f"""
        <div class="chart-container">
            <img src="data:image/png;base64,{yearly_chart}" alt="Yearly Spending Chart">
        </div>
"""
    
    html_content += """
    </div>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Summary report generated: {output_file}")


def main():
    html_file = 'apple.html'
    output_file = 'apple_transactions.csv'
    summary_file = 'apple_transactions_summary.html'
    
    transactions = extract_transactions(html_file)
    
    if not transactions:
        print("No paid transactions found.")
        return
    
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    write_csv(transactions, output_file)
    
    print(f"\nSummary:")
    print(f"  Total paid transactions: {len(transactions)}")
    total_amount = sum(float(t['amount'].replace('$', '')) for t in transactions)
    print(f"  Total amount: ${total_amount:.2f}")
    subscription_count = sum(1 for t in transactions if t['is_subscription'])
    print(f"  Subscriptions: {subscription_count}")
    print(f"  One-time purchases: {len(transactions) - subscription_count}")
    
    print(f"\nGenerating summary report...")
    generate_summary_report(transactions, summary_file)


if __name__ == '__main__':
    main()

