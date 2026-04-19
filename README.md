# 📊 AI Expense Assistant & Financial Dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fuwei-ai-expense-dashboard.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![TiDB](https://img.shields.io/badge/Database-TiDB_Cloud-4A72DA.svg)](https://en.pingcap.com/tidb-cloud/)

**Live Demo:** [Click here to view the Interactive Dashboard](https://fuwei-ai-expense-dashboard.streamlit.app/)

## 🚀 About The Project

This project is an **End-to-End AI-powered Personal Finance Management System** designed to bridge the gap between daily habit tracking and high-level data visualization. 

Architected for seamless user experience, it integrates a **LINE messaging chatbot** with Google's **Gemini LLM** to process natural language accounting inputs. The parsed data is persistently stored in a cloud-based **TiDB (MySQL)** database and visualized through an interactive, Morandi-themed **Streamlit** dashboard.

This tool goes beyond simple expense logging by offering **AI-driven burn rate projections**, multi-currency dynamic budgeting, and dual-axis financial modeling.

### 📸 Dashboard Preview
> Released soon!!

---

## ✨ Key Features & Business Value

* 🧠 **Natural Language Processing (NLP) Entry:** Users can input daily expenses via LINE casually (e.g., "Bought a coffee for 5 CAD"). The Gemini LLM automatically categorizes the item, extracts the amount, and identifies the currency.
* 📈 **Dynamic Burn Rate Projection:** Uses real-time data to calculate the daily burn rate and project month-end expenses, providing early warnings if the projected spend exceeds the budget threshold.
* 💱 **Multi-Currency Budgeting System:** Implemented a stateful architecture allowing users to set, save, and retrieve specific budgets for different currencies (e.g., CAD, TWD, EUR) persistently from the database.
* 🎨 **Interactive Dual-Axis Combo Charts:** Designed professional, Morandi-themed Plotly charts that overlay discrete daily events (Bar chart) against continuous cumulative trends (Line chart) to prevent visual distortion and scaling issues.

---

## 🏗️ System Architecture & Tech Stack

The data pipeline follows a robust ETL and visualization process:

1. **Frontend / UI:** Streamlit, Plotly Express, Plotly Graph Objects
2. **Backend Logic:** Python, Pandas (for data manipulation and styling)
3. **Database:** TiDB Cloud (MySQL distributed database)
4. **AI & Integrations:** Google Gemini API (LLM parsing), LINE Messaging API

---

## 💻 How to Run Locally

For developers or professors who wish to run this project locally:

### 1. Clone the repository
```bash
git clone [https://github.com/YourUsername/ai-expense-dashboard.git](https://github.com/YourUsername/ai-expense-dashboard.git)
cd ai-expense-dashboard

### 2. Install dependencies
```Bash
pip install -r requirements.txt

### 3. Configure Secrets
Create a .streamlit/secrets.toml file in the root directory and add your database credentials:

[mysql]
host = "your_tidb_host"
user = "your_username"
password = "your_password"
database = "test"
port = 4000

### 4. Run the application
``` Bash
streamlit run web_app.py






