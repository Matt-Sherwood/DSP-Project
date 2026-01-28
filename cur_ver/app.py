from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# Initialize database
with app.app_context():
    db.create_all()
    if not User.query.first():
        db.session.add(User(username='admin', password='password'))
        db.session.add(User(username='user', password='pass'))
        db.session.commit()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/xss', methods=['GET', 'POST'])
def xss_demo():
    user_input = ''
    if request.method == 'POST':
        user_input = request.form.get('input', '')
    
    return render_template('xss.html', user_input=user_input)

@app.route('/content')
def content():
    return render_template('content.html')

@app.route('/data')
def data():
    # Return JSON data that can be scraped
    from flask import jsonify
    json_data = {
        "users": ["admin", "user", "guest"],
        "sensitive_data": "This data could be scraped by bots",
        "api_version": "1.0",
        "endpoints": {
            "users": "/api/users",
            "products": "/api/products",
            "news": "/api/news"
        },
        "metadata": {
            "total_users": 3,
            "last_updated": "2024-01-24",
            "security_note": "This data is publicly accessible and could be scraped"
        }
    }
    return jsonify(json_data)

@app.route('/scraping')
def scraping_demo():
    return render_template('scraping.html')

@app.route('/scrape-content')
def scrape_content():
    # Simulate scraping by creating sample data directly
    # This avoids HTTP request issues in development
    
    try:
        # Create sample user data (simulating scraped data)
        users = [
            {'name': 'John Doe', 'email': 'john.doe@example.com', 'location': 'New York, NY'},
            {'name': 'Jane Smith', 'email': 'jane.smith@example.com', 'location': 'Los Angeles, CA'},
            {'name': 'Bob Johnson', 'email': 'bob.johnson@example.com', 'location': 'Chicago, IL'}
        ]
        
        # Create sample product data
        products = [
            {'name': 'Laptop Pro', 'price': '$1,299.99', 'description': 'High-performance laptop for professionals'},
            {'name': 'Wireless Headphones', 'price': '$199.99', 'description': 'Premium noise-canceling wireless headphones'},
            {'name': 'Smart Watch', 'price': '$349.99', 'description': 'Advanced fitness and health tracking smartwatch'}
        ]
        
        # Create sample news data
        news = [
            {'title': 'New Product Launch', 'date': 'January 15, 2024'},
            {'title': 'Company Expansion', 'date': 'December 20, 2023'},
            {'title': 'Holiday Sale', 'date': 'November 25, 2023'}
        ]
        
        # Extract code snippet for display
        scraping_code = '''def scrape_simulation():
    """Simulated scraping - creating sample data directly"""
    
    # In a real scenario, this would scrape from a website
    # For demo purposes, we're creating sample data
    
    users = [
        {'name': 'John Doe', 'email': 'john.doe@example.com', 'location': 'New York, NY'},
        {'name': 'Jane Smith', 'email': 'jane.smith@example.com', 'location': 'Los Angeles, CA'},
        {'name': 'Bob Johnson', 'email': 'bob.johnson@example.com', 'location': 'Chicago, IL'}
    ]
    
    products = [
        {'name': 'Laptop Pro', 'price': '$1,299.99', 'description': 'High-performance laptop'},
        {'name': 'Wireless Headphones', 'price': '$199.99', 'description': 'Noise-canceling headphones'},
        {'name': 'Smart Watch', 'price': '$349.99', 'description': 'Fitness tracking smartwatch'}
    ]
    
    # Process the scraped data
    print("Scraped User Data:")
    for user in users:
        print(f"Name: {user['name']}, Email: {user['email']}")
    
    print("\\nScraped Product Data:")
    for product in products:
        print(f"Product: {product['name']}, Price: {product['price']}")'''
        
        return render_template('scrape_content.html',
                             users=users,
                             products=products,
                             news=news,
                             scraping_code=scraping_code)
    except Exception as e:
        return render_template('scrape_content.html', error=str(e))

@app.route('/login', methods=['GET', 'POST'])
def login():
    username = ''
    password = ''
    result = None
    success = False
    query = ''
    users = []

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Vulnerable query: direct string concatenation
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        result = db.session.execute(text(query))
        users = result.fetchall()
        success = len(users) > 0
    
    return render_template('login.html',
                         username=username,
                         password=password,
                         result=result,
                         success=success,
                         query=query,
                         users=users)

if __name__ == '__main__':
    app.run(debug=True)