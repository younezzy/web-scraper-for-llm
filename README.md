# Crawl4AI Web Scraper

A powerful and flexible web scraping toolkit with multiple scraping methods and a user-friendly Streamlit interface.

![Scraper UI](https://raw.githubusercontent.com/LeBotFrancais/assets/main/web_scraper_ui.png)

## Features

- **Multiple Scraping Methods**:
  - Single URL scraping
  - Batch URL scraping from lists
  - Deep website crawling 
  - Sitemap detection and processing

- **Advanced Content Processing**:
  - Smart content filtering with adjustable pruning
  - Query-based content filtering using BM25
  - HTML cleaning and structuring
  
- **User-Friendly Interface**:
  - Beautiful Streamlit UI
  - Progress tracking
  - Results visualization
  - Preview scraped content

- **Output Options**:
  - Markdown file generation
  - Domain-specific organization
  - Clean, well-formatted content

## Installation

1. Clone this repository:
```bash
git clone https://github.com/LeBotFrancais/crawl4ai-web-scraper.git
cd crawl4ai-web-scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Streamlit UI

The easiest way to use the scraper is through the Streamlit interface:

```bash
streamlit run scraper_ui.py
```

This will open a web interface where you can:
- Enter URLs to scrape
- Configure scraping parameters
- Start scraping jobs
- View results

### Command Line Usage

#### Single URL Scraping

```bash
python scrape_specific_urls.py --url https://example.com --pruning-threshold 0.35 --pruning-type dynamic --min-word-threshold 5
```

#### Batch URL Scraping

```bash
python scrape_specific_urls.py --file urls.txt --pruning-threshold 0.35
```

#### Deep Website Crawling

Edit the configuration section in `website_scraper.py`:

```python
CRAWL_MODE = "deep"
TARGET_URL = "https://example.com"
MAX_DEPTH = 2
MAX_PAGES = 20
```

Then run:

```bash
python website_scraper.py
```

## Configuration Options

### Content Filtering Parameters

- **Pruning Threshold** (0.0-1.0): Control content density (lower keeps more)
- **Pruning Type**: "dynamic" or "fixed"
- **Min Word Threshold**: Minimum words per text block

### Deep Crawling Parameters

- **Max Depth**: How many links deep to crawl
- **Max Pages**: Maximum number of pages to crawl
- **Include External**: Whether to follow external links

### Query-Based Filtering

- **Query**: Search terms to filter content by relevance
- **Query Threshold**: Minimum relevance score (higher is more strict)

## Output

The scraped content is saved as Markdown files in domain-specific folders, with filenames based on the URL path.

Example:
```
example.com/
  index.md
  about.md
  products_item1.md
```

## Requirements

- Python 3.8+
- crawl4ai 
- streamlit
- playwright
- requests
- pandas

See `requirements.txt` for full dependencies.

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.