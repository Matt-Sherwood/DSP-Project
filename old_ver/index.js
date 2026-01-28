const express = require('express');
const path = require('path');
const app = express();
const port = 3000;

// Serve static files from templates directory
app.use(express.static(path.join(__dirname, 'templates')));

// Routes
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'home.html'));
});

app.get('/xss', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'xss.html'));
});

app.post('/xss', (req, res) => {
  res.redirect('/xss');
});

app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'login.html'));
});

app.post('/login', (req, res) => {
  res.redirect('/login');
});

app.get('/scraping', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'scraping.html'));
});

app.get('/scrape-content', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'scrape_content.html'));
});

app.get('/data', (req, res) => {
  res.json([
    { id: 1, name: "Alice", email: "alice@example.com" },
    { id: 2, name: "Bob", email: "bob@example.com" },
    { id: 3, name: "Charlie", email: "charlie@example.com" }
  ]);
});

app.listen(port, () => {
  console.log(`Old version server running at http://localhost:${port}`);
});