import asyncio
import os
import re
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
import requests
from xml.etree import ElementTree

# =====================
# CONFIGURATION SECTION
# =====================

# --- User Parameters ---
CRAWL_MODE = "single"  # "single" or "deep"
TARGET_URL = "https://lebotfrancais.framer.website"  # Change to your target
# For deep crawl only:
MAX_DEPTH = 2
MAX_PAGES = 20
INCLUDE_EXTERNAL = False

# Pruning filter parameters
PRUNING_THRESHOLD = 0.48  # 0.0 (keep more) to 1.0 (prune more)
PRUNING_TYPE = "dynamic"  # "fixed" or "dynamic"
MIN_WORD_THRESHOLD = 10

# =====================


def get_domain_folder(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")
    folder = os.path.join(os.getcwd(), domain)
    os.makedirs(folder, exist_ok=True)
    return folder

def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    # Use path, remove slashes, fallback to 'index' if empty
    path = parsed.path.strip("/").replace("/", "_")
    if not path:
        path = "index"
    # Remove query/fragment
    path = re.sub(r'[^a-zA-Z0-9_\-]', '', path)
    return path + ".md"

def guess_sitemap_urls(base_url: str):
    """
    Try common sitemap locations for a given base URL.
    Returns a list of sitemap URLs to try.
    """
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    return [
        f"{root}/sitemap.xml",
        f"{root}/sitemap_index.xml",
        f"{root}/sitemap.txt",
        f"{root}/sitemap/sitemap.xml",
        f"{root}/sitemapindex.xml",
    ]

def fetch_sitemap_urls(base_url: str):
    """
    Attempts to fetch and parse sitemap URLs from common locations.
    Returns a list of discovered URLs, or an empty list if none found.
    """
    sitemap_urls = guess_sitemap_urls(base_url)
    found_urls = set()
    for sitemap_url in sitemap_urls:
        try:
            resp = requests.get(sitemap_url, timeout=10)
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get('Content-Type', '')
            text = resp.text
            # XML sitemap
            if 'xml' in content_type or text.strip().startswith('<?xml'):
                try:
                    root = ElementTree.fromstring(resp.content)
                    # Try <loc> tags (standard sitemap)
                    for loc in root.findall('.//{*}loc'):
                        if loc.text:
                            found_urls.add(loc.text.strip())
                except Exception:
                    continue
            # Plain text sitemap
            elif 'text/plain' in content_type or sitemap_url.endswith('.txt'):
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith('http'):
                        found_urls.add(line)
        except Exception:
            continue
    return list(found_urls)

async def crawl_single(url: str):
    print(f"[Single Crawl] {url}")
    folder = get_domain_folder(url)
    filename = url_to_filename(url)
    out_path = os.path.join(folder, filename)

    prune_filter = PruningContentFilter(
        threshold=PRUNING_THRESHOLD,
        threshold_type=PRUNING_TYPE,
        min_word_threshold=MIN_WORD_THRESHOLD
    )
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        cache_mode=None  # Always fresh
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)
        if result.success and result.markdown and result.markdown.fit_markdown:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result.markdown.fit_markdown)
            print(f"[OK] Saved fit markdown to: {out_path}")
        else:
            print(f"[ERROR] Failed to crawl {url}: {getattr(result, 'error_message', 'Unknown error')}")

async def crawl_deep(url: str):
    print(f"[Deep Crawl] {url}")
    folder = get_domain_folder(url)
    prune_filter = PruningContentFilter(
        threshold=PRUNING_THRESHOLD,
        threshold_type=PRUNING_TYPE,
        min_word_threshold=MIN_WORD_THRESHOLD
    )
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=MAX_DEPTH,
            include_external=INCLUDE_EXTERNAL,
            max_pages=MAX_PAGES
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        markdown_generator=md_generator,
        cache_mode=None,
        stream=True,
        verbose=True
    )
    async with AsyncWebCrawler() as crawler:
        results = []
        async for result in await crawler.arun(url, config=config):
            results.append(result)
            if result.success and result.markdown and result.markdown.fit_markdown:
                filename = url_to_filename(result.url)
                out_path = os.path.join(folder, filename)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(result.markdown.fit_markdown)
                print(f"[OK] {result.url} -> {out_path}")
            else:
                print(f"[ERROR] {getattr(result, 'url', url)}: {getattr(result, 'error_message', 'Unknown error')}")
        print(f"[DONE] Crawled {len(results)} pages. Markdown saved in: {folder}")

async def crawl_urls_from_sitemap(urls):
    print(f"[Sitemap] Crawling {len(urls)} URLs from sitemap...")
    if not urls:
        print("[Sitemap] No URLs found in sitemap.")
        return
    folder = get_domain_folder(urls[0])
    prune_filter = PruningContentFilter(
        threshold=PRUNING_THRESHOLD,
        threshold_type=PRUNING_TYPE,
        min_word_threshold=MIN_WORD_THRESHOLD
    )
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        cache_mode=None,
        verbose=True
    )
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            result = await crawler.arun(url=url, config=config)
            if result.success and result.markdown and result.markdown.fit_markdown:
                filename = url_to_filename(result.url)
                out_path = os.path.join(folder, filename)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(result.markdown.fit_markdown)
                print(f"[OK] {result.url} -> {out_path}")
            else:
                print(f"[ERROR] {getattr(result, 'url', url)}: {getattr(result, 'error_message', 'Unknown error')}")
    print(f"[DONE] Crawled {len(urls)} sitemap URLs. Markdown saved in: {folder}")

async def main():
    # Try to get sitemap URLs first
    sitemap_urls = fetch_sitemap_urls(TARGET_URL)
    if sitemap_urls:
        print(f"[INFO] Discovered {len(sitemap_urls)} pages in sitemap.")
        try:
            user_input = input(f"How many pages do you want to scrape? (1-{len(sitemap_urls)}, Enter for all): ")
            if user_input.strip():
                n_pages = int(user_input)
                sitemap_urls = sitemap_urls[:n_pages]
        except Exception:
            print("[WARN] Invalid input, scraping all pages.")
        print(f"[INFO] Scraping {len(sitemap_urls)} pages...")
        await crawl_urls_from_sitemap(sitemap_urls)
    else:
        print("[WARN] No sitemap found, falling back to deep crawl.")
        if CRAWL_MODE == "single":
            await crawl_single(TARGET_URL)
        elif CRAWL_MODE == "deep":
            await crawl_deep(TARGET_URL)
        else:
            print("[ERROR] Unknown CRAWL_MODE. Use 'single' or 'deep'.")

if __name__ == "__main__":
    asyncio.run(main())
