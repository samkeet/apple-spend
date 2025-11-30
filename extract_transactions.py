#!/usr/bin/env python3

import csv
import re
from datetime import datetime
from bs4 import BeautifulSoup


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
        soup = BeautifulSoup(f, 'html.parser')
    
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


def main():
    html_file = 'apple.html'
    output_file = 'apple_transactions.csv'
    
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


if __name__ == '__main__':
    main()

