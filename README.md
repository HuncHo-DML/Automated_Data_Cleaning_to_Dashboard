# NovaMart Orders: From Messy CSV to Live Dashboard

Welcome! This project takes a deliberately messy e-commerce orders file from a fictional Nigerian retailer called NovaMart and turns it into something people can actually use: a clean dataset, a documented cleaning process, and a live, filterable dashboard that refreshes itself whenever new data lands on GitHub.

It started as a hands-on walkthrough in Google Colab, and it grew into a small end-to-end pipeline: **clean the data, explore it, deploy it, and automate it.** If you are learning data cleaning, or you want a practical template for a "drop a CSV on GitHub and the dashboard updates" workflow, you are in the right place.

> The NovaMart data is entirely fictional, so it is safe to keep in a public repository. Please never publish real customer data this way.

---

## What You Will Find Here

The raw file has 1,051 rows and 22 columns, packed with the kind of problems real analysts meet every week: inconsistent casing, misspelled categories (think "Fashon" and "Beuaty"), eight different ways of writing "missing", phone numbers in five formats, emails ending in ".con", duplicate orders, impossible ratings, and totals that do not add up.

The project walks through fixing all of it, then shows the result in an interactive dashboard with KPIs, charts, filters, and a downloadable PDF slide report.

![Raw messy data loaded in Google Colab showing the first 10 rows and df.info output](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d1.png)

---

## Technologies Used

| Tool | What it does here |
| :--- | :--- |
| **Python 3** | The language behind every step |
| **pandas** | Loading, cleaning, and reshaping the data |
| **NumPy** | Numeric handling and missing value placeholders |
| **re (regex)** | Fixing names, phone numbers, and column headers |
| **Plotly Express** | Interactive charts in the notebook and the dashboard |
| **ipywidgets** | The first dropdown filter prototype inside Colab |
| **Streamlit** | The live dashboard web app |
| **Matplotlib** | Building the multi page PDF slide report |
| **PyArrow / Parquet** | Saving the clean data with exact data types preserved |
| **Google Colab** | The notebook environment for cleaning and prototyping |
| **Cloudflare Tunnel** | A temporary public link while testing from Colab |
| **GitHub** | Version control and the live data source |
| **Streamlit Community Cloud** | Free, permanent hosting for the dashboard |

---

## Project Structure

![comprehensive project structure design](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d7.png)


A quick tour of the important pieces:

**novamart_cleaning.ipynb** is the learning notebook. It cleans the data one careful stage at a time and ends with a cleaning log.

**novamart_dashboard.ipynb** builds the first charts, adds a dropdown filter, and then writes out the Streamlit app.

**app.py** is the production version. It reads the messy CSV straight from GitHub, cleans it with the same rules as the notebook, and renders the dashboard.

**requirements.txt** lists `streamlit`, `pandas`, `plotly`, and `matplotlib`.

---

## Main Features

### A 14 stage cleaning pipeline

Each stage has one clear goal, so you always know why you are doing something.

1. Load everything as text (`dtype=str`) and keep an untouched backup copy
2. Inspect before changing anything
3. Standardize column names to lowercase snake_case
4. Remove blank rows and trim stray spaces
5. Convert eight different missing markers (`N/A`, `?`, `-`, `null` and friends) into real missing values
6. Map spelling variants into one label per real world thing
7. Validate emails and normalize Nigerian phone numbers to the 11 digit format
8. Convert currency text like ₦1,200 and percentages like 10% into real numbers
9. Parse dates written in five different formats
10. Remove duplicate orders using `order_id`
11. Validate ranges, flag outliers with the IQR rule, and cross check totals
12. Handle remaining gaps deliberately, column by column
13. Run final assertions and export to CSV and Parquet
14. Write a short cleaning log for your manager or client

![Output of the cleaning checks showing standardized categories and the All checks passed message](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d2.png)

### Smart handling of tricky data

Outliers are looked at before they are removed, because a ₦450,000 laptop is not an error. Totals that do not match quantity times price times discount are recalculated. A `rating_missing` flag keeps track of which ratings were gaps before any filling happened.

### An interactive Streamlit dashboard

Sidebar filters for state, product category, delivery status, payment method, membership, and order date range. Five headline KPIs: revenue, orders, average order value, average rating, and delivery rate. Six charts: revenue by month, revenue by category, orders by state, revenue by payment method, orders by delivery status, and the rating distribution.

![The live NovaMart Streamlit dashboard showing KPI cards, line chart, bar charts and pie chart](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d3.png)

### Live auto refresh

The dashboard re downloads the messy CSV from GitHub every 60 seconds and cleans it again. Swap in a new file with the same 22 columns and the dashboard updates itself, no redeploy needed.

### Transparent cleaning summary

An expandable panel inside the dashboard shows exactly what the cleaning step did: rows in, blank rows removed, duplicates removed, invalid emails fixed, impossible values removed, totals recalculated, and rows kept.

### Downloads on demand

Download the filtered clean data as a CSV, or generate a polished multi slide PDF report that includes the filters you had active, key numbers, trend charts, and the cleaning summary.

![Sample page from the downloadable PDF summary report with revenue trend charts](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d4.png)

---

## Setup Instructions

### 1. Get the files

Clone the repository:

```bash
git clone https://github.com/HuncHo-DML/novamart_data_cleaning.git
cd novamart_data_cleaning
```

### 2. Run the cleaning notebook in Google Colab

1. Open [colab.research.google.com](https://colab.research.google.com) and sign in.
2. Create a new notebook and name it `novamart_cleaning`.
3. Click the folder icon on the left, then the upload icon, and upload `novamart_orders_messy.csv`.
4. Follow the 14 stages in order, adding a text cell title above each code cell.

Colab runtimes disconnect now and then. If your files vanish, upload the CSV again and rerun from Stage 1.

### 3. Run the dashboard locally (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local address Streamlit prints, usually `http://localhost:8501`.

### 4. Point the app at your own data

Open `app.py` and find the `DATA_URL` line near the top. Replace the link with the Raw GitHub URL of your own CSV. It should start with `https://raw.githubusercontent.com/`. To get it, open the CSV on GitHub and click the **Raw** button.

### 5. Deploy for free on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app** and choose **Deploy a public app from GitHub**.
3. Pick your repository, set the branch to `main`, and the main file path to `app.py`.
4. Click **Deploy** and wait one to three minutes.
5. Copy the link from your address bar. It works for anyone, even when your computer is off.

### 6. Pushing results to GitHub from Colab

Store your GitHub token in Colab Secrets instead of pasting it into code. Click the key icon in Colab's sidebar, add a secret named `GITHUB_TOKEN`, and switch on Notebook access. Then read it in code like this:

```python
from google.colab import userdata
TOKEN = userdata.get('GITHUB_TOKEN')
```

Give the token only the `repo` scope, set a short expiry, and delete it when you are done.

![GitHub repository page showing the messy CSV, clean CSV, Parquet file, app.py and requirements.txt](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d5.png)

---

## Workflow Usage Guide

Here is the day to day flow once everything is set up.

**Step one: clean and learn.** Work through the Colab notebook to understand every transformation. Finish with the assertions cell. When you see "All checks passed", your data is trustworthy.

**Step two: prototype.** In the dashboard notebook, load the clean CSV, draw your first bar chart, then add the state dropdown. This is a great way to see how filters and charts connect.

**Step three: share a quick preview.** Install Streamlit and the Cloudflare tunnel in Colab, write `app.py`, and run the launch cell. After up to a minute you get a temporary public link. It only works while your notebook stays connected.

![Colab output showing the temporary trycloudflare link for the dashboard](https://github.com/HuncHo-DML/Automated_Data_Cleaning_to_Dashboard/blob/main/d6.png)

**Step four: go permanent and automatic.** Replace the prototype `app.py` with the live version that cleans data straight from GitHub, commit it, and deploy on Streamlit Community Cloud.

**Step five: update the data.** Whenever you have a new export:

1. Make sure it has the same 22 column names as the practice file.
2. Rename it to exactly `novamart_orders_messy.csv`.
3. On GitHub, choose **Add file**, then **Upload files**, drop it in, and commit.
4. Wait about a minute. The dashboard refreshes on its own. GitHub keeps the old version in the file history, so nothing is lost.

**Step six: after changing code.** If you edit `app.py` or `requirements.txt` (for example, when `matplotlib` was added for the PDF report), open your app on share.streamlit.io and reboot it from the menu so the changes take effect.

---

## Reusable Cleaning Checklist

Tick these off on every new dataset:

☐ I made a backup copy and never edited the original

☐ I loaded the data as text first, then converted columns deliberately

☐ Column names are lowercase snake_case with no symbols

☐ Every missing value marker became a real missing value

☐ Categories have one spelling per real value

☐ Dates are real dates in one format

☐ Duplicates are removed using a chosen key, and the count is recorded

☐ Impossible values are removed or flagged, and cross column rules are checked

☐ Remaining missing values have a documented decision

☐ Final assertions pass and before and after row counts are explained

☐ I saved the clean file and wrote the cleaning log

---

## Good to Know

Button names on Colab, GitHub, and Streamlit change from time to time. If a label looks slightly different, pick the button that does the same job.

A CSV only stores text, so when you reload the clean file, use `parse_dates=['date_of_birth', 'signup_date', 'order_date']`. If you want types preserved exactly, use the Parquet file.

---

## Author

Built by **HuncHo-DML** as part of a data cleaning and dashboarding learning project. Feedback, questions, and pull requests are very welcome.
