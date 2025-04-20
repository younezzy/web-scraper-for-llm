import asyncio
import os
import re
import argparse
import sys
from urllib.parse import urlparse
from typing import List
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.content_filter_strategy import PruningContentFilter, BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy

# Fix encoding issues for Windows console
if sys.platform == "win32":
    # Force UTF-8 encoding for stdout and stderr
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ["PYTHONIOENCODING"] = "utf-8"

# =====================
# CONFIGURATION SECTION
# =====================

# List the URLs you want to scrape here:
URLS_TO_SCRAPE = [
    "https://botpress.com/docs/home",
    # Add more URLs here...
]

# Pruning filter parameters (adjust based on site content density)
PRUNING_THRESHOLD = 0.35  # 0.0 (keep more) to 1.0 (prune more)
PRUNING_TYPE = "dynamic"  # "fixed" or "dynamic"
MIN_WORD_THRESHOLD = 5   # Minimum words per block to keep

# =====================

def get_domain_folder(url: str) -> str:
    """Get a domain-specific folder for storing scraped content."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(script_dir, domain)
    os.makedirs(folder, exist_ok=True)
    return folder

def url_to_filename(url: str) -> str:
    """Convert URL to a valid filename."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    if not path:
        path = "index"
    path = re.sub(r'[^a-zA-Z0-9_\-]', '', path)
    return path + ".md"

async def scrape_urls(urls: List[str], pruning_threshold=PRUNING_THRESHOLD, pruning_type=PRUNING_TYPE, 
                     min_word_threshold=MIN_WORD_THRESHOLD, use_query=False, query=None, query_threshold=1.2):
    """Scrape a list of URLs and save the content as markdown files."""
    if not urls:
        print("[ERROR] No URLs provided.")
        return
    
    try:
        # Create the content filter based on parameters
        if use_query and query:
            content_filter = BM25ContentFilter(
                user_query=query,
                bm25_threshold=query_threshold
            )
            print(f"[INFO] Using BM25ContentFilter with query: '{query}' (threshold: {query_threshold})")
        else:
            content_filter = PruningContentFilter(
                threshold=pruning_threshold,
                threshold_type=pruning_type,
                min_word_threshold=min_word_threshold
            )
            print(f"[INFO] Using PruningContentFilter (threshold: {pruning_threshold}, type: {pruning_type}, min_words: {min_word_threshold})")
        
        # Create DefaultMarkdownGenerator with our filter
        md_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "ignore_links": False,
                "body_width": 0,  # No wrapping
                "escape_html": True
            }
        )
        
        # Set browser config for better crawling
        browser_config = BrowserConfig(
            headless=True,
            verbose=True,
            java_script_enabled=True,
            extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"]
        )
        
        # Set crawler config with proper markdown generator
        crawl_config = CrawlerRunConfig(
            markdown_generator=md_generator,
            scraping_strategy=LXMLWebScrapingStrategy(),
            cache_mode=None,
            process_iframes=True,
            remove_overlay_elements=True,
            excluded_tags=["nav", "footer", "header", "style", "script"],
            word_count_threshold=0,
            verbose=False  # Set to False to reduce Unicode output that might cause issues
        )
        
        # Use a single browser session for all URLs
        async with AsyncWebCrawler(config=browser_config) as crawler:
            session_id = "batch_session"  # Reuse session for better performance
            
            for url in urls:
                try:
                    print(f"\n[SCRAPE] {url}")
                    folder = get_domain_folder(url)
                    filename = url_to_filename(url)
                    out_path = os.path.join(folder, filename)
                    
                    # Crawl the URL with our configuration
                    result = await crawler.arun(
                        url=url, 
                        config=crawl_config,
                        session_id=session_id
                    )
                    
                    if not result.success:
                        print(f"[ERROR] Failed to crawl {url}: {getattr(result, 'error_message', 'Unknown error')}")
                        continue
                    
                    # Try to get the fit_markdown (filtered content)
                    if (hasattr(result, 'markdown') and 
                        hasattr(result.markdown, 'fit_markdown') and 
                        result.markdown.fit_markdown and 
                        len(result.markdown.fit_markdown.strip()) > 0):
                        
                        print(f"[INFO] Found fit_markdown ({len(result.markdown.fit_markdown)} chars)")
                        markdown_content = result.markdown.fit_markdown
                    
                    # Fallback to raw_markdown if fit_markdown is empty
                    elif (hasattr(result, 'markdown') and 
                          hasattr(result.markdown, 'raw_markdown') and 
                          result.markdown.raw_markdown):
                        
                        print(f"[INFO] Using raw_markdown ({len(result.markdown.raw_markdown)} chars)")
                        markdown_content = result.markdown.raw_markdown
                    
                    else:
                        print("[ERROR] No markdown content generated")
                        continue
                    
                    # Save markdown content to file
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    print(f"[SUCCESS] Saved to: {out_path}")
                
                except Exception as e:
                    print(f"[ERROR] Exception while processing {url}: {str(e)}")
                    
            # Clean up session when done
            try:
                await crawler.kill_session(session_id)
            except:
                pass
                
    except Exception as e:
        print(f"[ERROR] Crawler initialization failed: {str(e)}")

def parse_arguments():
    parser = argparse.ArgumentParser(description='Scrape specific URLs with Crawl4AI')
    
    # URL sources (choose one)
    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument('--url', help='Single URL to scrape')
    url_group.add_argument('--file', help='File containing URLs (one per line)')
    
    # Filtering parameters
    parser.add_argument('--pruning-threshold', type=float, default=PRUNING_THRESHOLD, 
                        help='Pruning threshold (0.0-1.0)')
    parser.add_argument('--pruning-type', choices=['dynamic', 'fixed'], default=PRUNING_TYPE,
                        help='Pruning threshold type')
    parser.add_argument('--min-word-threshold', type=int, default=MIN_WORD_THRESHOLD,
                        help='Minimum words per text block')
    
    # Query-based filtering
    parser.add_argument('--use-query', action='store_true', help='Use query-based filtering (BM25)')
    parser.add_argument('--query', help='Query for BM25 filtering')
    parser.add_argument('--query-threshold', type=float, default=1.2, help='BM25 threshold')
    
    return parser.parse_args()

async def main():
    try:
        args = parse_arguments()
        
        # Get URLs to scrape
        urls = []
        if args.url:
            urls = [args.url]
        elif args.file and os.path.exists(args.file):
            with open(args.file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
        else:
            urls = URLS_TO_SCRAPE
        
        if not urls:
            print("[ERROR] No URLs provided. Use --url, --file, or add URLs to URLS_TO_SCRAPE in the script.")
            return
        
        await scrape_urls(
            urls=urls,
            pruning_threshold=args.pruning_threshold,
            pruning_type=args.pruning_type,
            min_word_threshold=args.min_word_threshold,
            use_query=args.use_query,
            query=args.query,
            query_threshold=args.query_threshold
        )
    
    except Exception as e:
        print(f"[CRITICAL ERROR] {str(e)}")
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Scraping cancelled by user.")
    except Exception as e:
        print(f"[FATAL ERROR] {str(e)}")
