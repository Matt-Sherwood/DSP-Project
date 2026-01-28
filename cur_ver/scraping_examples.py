# Example scraping scripts

def scrape_html_example():
    """Example of scraping HTML content"""
    import requests
    from bs4 import BeautifulSoup

    # Scrape the HTML page
    response = requests.get('http://localhost:5000/content')
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract user emails
    users = soup.find_all('div', class_='user-card')
    for user in users:
        name = user.find('h3').text
        email = user.find('p').text.replace('Email: ', '')
        print(f"{name}: {email}")

    # Extract product prices
    products = soup.find_all('div', class_='product')
    for product in products:
        name = product.find('h3').text
        price = product.find('p').text.replace('Price: ', '')
        print(f"{name}: {price}")

def scrape_json_example():
    """Example of scraping JSON API"""
    import requests

    response = requests.get('http://localhost:5000/data')
    data = response.json()
    print("Scraped users:", data['users'])
    print("Sensitive data:", data['sensitive_data'])