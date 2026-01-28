import requests

base_url = 'http://localhost:5000'

# Test valid login
response = requests.post(f'{base_url}/login', data={'username': 'admin', 'password': 'password'})
print('Valid login:', response.text)

# Test invalid login
response = requests.post(f'{base_url}/login', data={'username': 'wrong', 'password': 'wrong'})
print('Invalid login:', response.text)

# Test SQL injection
response = requests.post(f'{base_url}/login', data={'username': "' OR '1'='1' --", 'password': 'anything'})
print('SQL injection:', response.text)