import streamlit as st
import os
import re
import sys
import time
import pandas as pd
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Union
import requests
from xml.etree import ElementTree
import tempfile

# Set page configuration
st.set_page_config(
    page_title="Advanced Web Scraper",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        background: linear-gradient(45deg, #3498db, #8e44ad);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2c3e50;
        font-weight: 600;
        margin-top: 1.5rem;
    }
    .card {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }
    .success-text {
        color: #2ecc71;
        font-weight: 600;
    }
    .warning-text {
        color: #f39c12;
        font-weight: 600;
    }
    .error-text {
        color: #e74c3c;
        font-weight: 600;
    }
    .info-box {
        background-color: #eef8ff;
        padding: 1rem;
        border-left: 4px solid #3498db;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
    .result-box {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        max-height: 400px;
        overflow-y: auto;
    }
    .url-preview {
        font-family: monospace;
        padding: 0.25rem 0.5rem;
        background-color: #f1f1f1;
        border-radius: 4px;
        margin: 0.1rem 0;
        font-size: 0.9rem;
        word-break: break-all;
    }
    .stButton>button {
        background-color: #3498db;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #2980b9;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .metrics-container {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
    }
    .metric-card {
        background-color: #ffffff;
        border-radius: 0.5rem;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        text-align: center;
        flex: 1;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #3498db;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #7f8c8d;
        margin-top: 0.25rem;
    }
    footer {
        margin-top: 3rem;
        text-align: center;
        color: #7f8c8d;
        font-size: 0.8rem;
    }
    .tab-content {
        padding: 1.5rem 0;
    }
    .progress-container {
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ========================
# HELPER FUNCTIONS
# ========================

def get_domain_folder(url: str) -> str:
    """Get or create a domain-specific folder for storing scraped content using relative paths."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")
    # Use relative path based on the script's location
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
    # Remove query/fragment and other invalid characters
    path = re.sub(r'[^a-zA-Z0-9_\-]', '', path)
    return path + ".md"

def fetch_sitemap_urls(base_url: str):
    """
    Find sitemap URLs from common locations.
    Returns a list of discovered URLs and the sitemap URL if found.
    """
    # Common sitemap locations
    sitemap_locations = [
        "/sitemap.xml", 
        "/sitemap_index.xml", 
        "/sitemap.txt",
        "/sitemap/sitemap.xml", 
        "/sitemapindex.xml",
        "/wp-sitemap.xml",
        "/sitemap_news.xml"
    ]
    
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    
    found_urls = set()
    found_sitemap = None
    
    with st.spinner("Searching for sitemap..."):
        progress_text = st.empty()
        
        for sitemap_path in sitemap_locations:
            sitemap_url = f"{root}{sitemap_path}"
            progress_text.text(f"Checking {sitemap_url}")
            
            try:
                resp = requests.get(sitemap_url, timeout=10)
                if resp.status_code != 200:
                    continue
                
                found_sitemap = sitemap_url
                content_type = resp.headers.get('Content-Type', '')
                text = resp.text
                
                # Handle XML sitemaps
                if 'xml' in content_type or text.strip().startswith('<?xml'):
                    try:
                        root_element = ElementTree.fromstring(resp.content)
                        
                        # Check if this is a sitemap index
                        sitemap_tags = root_element.findall('.//{*}sitemap')
                        if sitemap_tags:
                            progress_text.text(f"Found sitemap index with {len(sitemap_tags)} sitemaps")
                            for sitemap in sitemap_tags:
                                loc = sitemap.find('.//{*}loc')
                                if loc is not None and loc.text:
                                    sub_sitemap_url = loc.text.strip()
                                    progress_text.text(f"Fetching sub-sitemap: {sub_sitemap_url}")
                                    try:
                                        sub_resp = requests.get(sub_sitemap_url, timeout=10)
                                        if sub_resp.status_code == 200:
                                            sub_root = ElementTree.fromstring(sub_resp.content)
                                            for url in sub_root.findall('.//{*}url'):
                                                loc = url.find('.//{*}loc')
                                                if loc is not None and loc.text:
                                                    found_urls.add(loc.text.strip())
                                    except Exception as e:
                                        st.warning(f"Failed to parse sub-sitemap: {e}")
                        
                        # Find individual URLs
                        for loc in root_element.findall('.//{*}loc'):
                            if loc.text:
                                found_urls.add(loc.text.strip())
                    except Exception as e:
                        st.warning(f"XML parsing error: {e}")
                        continue
                
                # Handle text sitemaps
                elif 'text/plain' in content_type or sitemap_url.endswith('.txt'):
                    for line in text.splitlines():
                        line = line.strip()
                        if line.startswith('http'):
                            found_urls.add(line)
                
                if found_urls:
                    progress_text.text(f"Found {len(found_urls)} URLs in {sitemap_url}")
                    break
                    
            except Exception as e:
                continue
                
    return list(found_urls), found_sitemap

def is_valid_url(url):
    """Check if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


# ========================
# SCRAPING FUNCTIONS USING SUBPROCESS
# ========================

def scrape_single_url(url: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Scrape a single URL using subprocess to run the scrape_specific_urls.py script"""
    result = {
        "success": False,
        "error": None,
        "url": url,
        "saved_path": None,
        "markdown_type": None,
        "content_length": 0,
        "content_preview": None,
        "domain": urlparse(url).netloc
    }
    
    try:
        # Get path to the scrape_specific_urls.py script (in the same directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "scrape_specific_urls.py")
        
        # Calculate expected output path to use as fallback
        folder = get_domain_folder(url)
        filename = url_to_filename(url)
        expected_path = os.path.join(folder, filename)
        
        # Build command with all settings
        cmd = [
            sys.executable,  # Current Python interpreter
            script_path,
            "--url", url,
            "--pruning-threshold", str(settings.get("pruning_threshold", 0.35)),
            "--pruning-type", settings.get("pruning_type", "dynamic"),
            "--min-word-threshold", str(settings.get("min_word_threshold", 5))
        ]
        
        # Add query-based filtering if enabled
        if settings.get("use_query", False) and settings.get("query", ""):
            cmd.extend([
                "--use-query",
                "--query", settings.get("query", ""),
                "--query-threshold", str(settings.get("query_threshold", 1.2))
            ])
        
        # Run the command with proper encoding
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8'
        )
        
        # More debugging if enabled
        if st.session_state.get("detailed_logs", False):
            st.write(f"Command: {' '.join(cmd)}")
            st.write(f"Exit code: {process.returncode}")
            st.write(f"Stdout: {process.stdout[:500]}...")
            st.write(f"Stderr: {process.stderr}")
        
        # Check both standard output and standard error
        output_text = process.stdout + "\n" + process.stderr
        
        # Check if successful by examining both exit code and output text
        if process.returncode == 0 or "[SUCCESS]" in output_text:
            # Check both methods to find the output path
            # Method 1: Look for the explicit success message
            saved_line = [line for line in output_text.splitlines() if "[SUCCESS] Saved to:" in line]
            output_path = None
            
            if saved_line:
                # Extract path from success message
                output_path = saved_line[0].split("[SUCCESS] Saved to:")[1].strip()
            
            # Method 2: If no success message found, try the expected path
            if not output_path or not os.path.exists(output_path):
                output_path = expected_path
            
            # Final check for file existence
            if os.path.exists(output_path):
                # Get the file content
                with open(output_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                result["success"] = True
                result["saved_path"] = output_path
                result["content_length"] = len(content)
                result["content_preview"] = content[:500] + "..." if len(content) > 500 else content
                result["markdown_type"] = "fit_markdown"
            else:
                # Look for clues in the output for why the file wasn't created
                info_lines = [line for line in output_text.splitlines() if "[INFO]" in line]
                error_lines = [line for line in output_text.splitlines() if "[ERROR]" in line]
                
                # Check if it found content but failed to save
                content_found = any("Found fit_markdown" in line for line in info_lines)
                
                if content_found:
                    result["error"] = "Content was extracted but file wasn't saved properly"
                elif error_lines:
                    result["error"] = error_lines[0].replace("[ERROR]", "").strip()
                else:
                    result["error"] = "File was not saved and no error was reported"
        else:
            # Extract error from stderr or stdout if any
            error_lines = [line for line in output_text.splitlines() if "[ERROR]" in line]
            if error_lines:
                result["error"] = error_lines[0].replace("[ERROR]", "").strip()
            else:
                result["error"] = process.stderr or "Unknown error during scraping"
        
    except Exception as e:
        result["error"] = str(e)
    
    return result

def scrape_multiple_urls(urls: List[str], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Scrape multiple URLs using subprocess to run the scrape_specific_urls.py script"""
    results = []
    
    # Create a temporary file with all URLs
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as temp:
        temp_path = temp.name
        for url in urls:
            temp.write(f"{url}\n")
    
    try:
        # Get path to the scrape_specific_urls.py script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "scrape_specific_urls.py")
        
        # Build command with all settings
        cmd = [
            sys.executable,  # Current Python interpreter
            script_path,
            "--file", temp_path,
            "--pruning-threshold", str(settings.get("pruning_threshold", 0.35)),
            "--pruning-type", settings.get("pruning_type", "dynamic"),
            "--min-word-threshold", str(settings.get("min_word_threshold", 5))
        ]
        
        # Add query-based filtering if enabled
        if settings.get("use_query", False) and settings.get("query", ""):
            cmd.extend([
                "--use-query",
                "--query", settings.get("query", ""),
                "--query-threshold", str(settings.get("query_threshold", 1.2))
            ])
        
        # Run the command with proper encoding
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8'
        )
        
        # More debugging if enabled
        if st.session_state.get("detailed_logs", False):
            st.write(f"Command: {' '.join(cmd)}")
            st.write(f"Exit code: {process.returncode}")
            st.write(f"Stdout (first 500 chars): {process.stdout[:500]}...")
            if process.stderr:
                st.write(f"Stderr: {process.stderr}")
        
        # Combine stdout and stderr for parsing
        output_text = process.stdout + "\n" + process.stderr
        output_lines = output_text.splitlines()
        
        # Track URLs being processed
        url_status_map = {url: {
            "success": False,
            "error": None,
            "url": url,
            "saved_path": None, 
            "markdown_type": None,
            "content_length": 0,
            "content_preview": None,
            "domain": urlparse(url).netloc
        } for url in urls}
        
        current_url = None
        
        # Parse the output line by line
        for line in output_lines:
            if line.startswith("[SCRAPE]"):
                # New URL being processed
                url = line.replace("[SCRAPE]", "").strip()
                current_url = url if url in url_status_map else None
            
            elif line.startswith("[SUCCESS]") and "Saved to:" in line and current_url:
                # File was saved successfully
                output_path = line.split("[SUCCESS] Saved to:")[1].strip()
                
                if os.path.exists(output_path):
                    # Get the file content
                    try:
                        with open(output_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        url_status_map[current_url]["success"] = True
                        url_status_map[current_url]["saved_path"] = output_path
                        url_status_map[current_url]["content_length"] = len(content)
                        url_status_map[current_url]["content_preview"] = content[:500] + "..." if len(content) > 500 else content
                        url_status_map[current_url]["markdown_type"] = "fit_markdown"
                    except Exception as e:
                        url_status_map[current_url]["error"] = f"Error reading file: {str(e)}"
                else:
                    # For cases where the path was reported but file not found
                    folder = get_domain_folder(current_url)
                    filename = url_to_filename(current_url)
                    expected_path = os.path.join(folder, filename)
                    
                    if os.path.exists(expected_path):
                        try:
                            with open(expected_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            url_status_map[current_url]["success"] = True
                            url_status_map[current_url]["saved_path"] = expected_path
                            url_status_map[current_url]["content_length"] = len(content)
                            url_status_map[current_url]["content_preview"] = content[:500] + "..." if len(content) > 500 else content
                            url_status_map[current_url]["markdown_type"] = "fit_markdown"
                        except Exception as e:
                            url_status_map[current_url]["error"] = f"Error reading file: {str(e)}"
                    else:
                        url_status_map[current_url]["error"] = "Reported path not found"
            
            elif line.startswith("[ERROR]") and current_url:
                # Error processing URL
                error_msg = line.replace("[ERROR]", "").strip()
                if current_url in url_status_map:
                    url_status_map[current_url]["error"] = error_msg
        
        # Convert map to list of results
        results = list(url_status_map.values())
        
        # Fall back to checking by expected path for any URLs not found in output
        for result in results:
            if not result["success"] and not result["saved_path"]:
                url = result["url"]
                folder = get_domain_folder(url)
                filename = url_to_filename(url)
                expected_path = os.path.join(folder, filename)
                
                if os.path.exists(expected_path):
                    try:
                        with open(expected_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        result["success"] = True
                        result["saved_path"] = expected_path
                        result["content_length"] = len(content)
                        result["content_preview"] = content[:500] + "..." if len(content) > 500 else content
                        result["markdown_type"] = "fit_markdown"
                        result["error"] = None
                    except Exception as e:
                        result["error"] = f"Error reading file: {str(e)}"
        
    except Exception as e:
        # Add error result for each URL
        for url in urls:
            results.append({
                "success": False,
                "error": str(e),
                "url": url,
                "saved_path": None,
                "markdown_type": None,
                "content_length": 0,
                "content_preview": None,
                "domain": urlparse(url).netloc
            })
    
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
    
    return results

def deep_crawl_website(base_url: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Perform a deep crawl of a website using subprocess to run the website_scraper.py script"""
    results = []
    
    try:
        # Get path to the website_scraper.py script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "website_scraper.py")
        
        # Create a temporary config file to override settings
        temp_config = f"""
# =====================
# CONFIGURATION SECTION
# =====================

# --- User Parameters ---
CRAWL_MODE = "deep"  # "single" or "deep"
TARGET_URL = "{base_url}"
# For deep crawl only:
MAX_DEPTH = {settings.get("deep_crawl_settings", {}).get("max_depth", 2)}
MAX_PAGES = {settings.get("deep_crawl_settings", {}).get("max_pages", 20)}
INCLUDE_EXTERNAL = {str(settings.get("deep_crawl_settings", {}).get("include_external", False))}

# Pruning filter parameters
PRUNING_THRESHOLD = {settings.get("pruning_threshold", 0.35)}  # 0.0 (keep more) to 1.0 (prune more)
PRUNING_TYPE = "{settings.get("pruning_type", "dynamic")}"  # "fixed" or "dynamic"
MIN_WORD_THRESHOLD = {settings.get("min_word_threshold", 5)}

# =====================
"""
        # Write to temp file
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as temp:
            temp_config_path = temp.name
            temp.write(temp_config)
        
        # Setup environment variables to override config
        env = os.environ.copy()
        env["PYTHONPATH"] = script_dir + os.pathsep + env.get("PYTHONPATH", "")
        
        # Run the script with the temp config
        process = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            check=False,
            env=env
        )
        
        # Process the output to gather results
        output_lines = process.stdout.splitlines()
        current_url = None
        domain_folder = None
        
        for line in output_lines:
            if "[OK]" in line and "->" in line:
                # Extract URL and file path
                parts = line.split("[OK]")[1].strip().split("->")
                if len(parts) == 2:
                    url = parts[0].strip()
                    output_path = parts[1].strip()
                    
                    if os.path.exists(output_path):
                        # Get the file content
                        with open(output_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        results.append({
                            "success": True,
                            "error": None,
                            "url": url,
                            "saved_path": output_path,
                            "content_length": len(content),
                            "content_preview": content[:500] + "..." if len(content) > 500 else content,
                            "markdown_type": "fit_markdown",
                            "domain": urlparse(url).netloc
                        })
            
            elif "[DONE] Crawled" in line and "pages" in line:
                # Get the domain folder
                folder_match = re.search(r"saved in: (.+)", line)
                if folder_match:
                    domain_folder = folder_match.group(1)
            
            elif "[ERROR]" in line and ":" in line:
                # Error processing URL
                parts = line.split("[ERROR]")[1].strip().split(":", 1)
                if len(parts) == 2:
                    url = parts[0].strip()
                    error = parts[1].strip()
                    
                    results.append({
                        "success": False,
                        "error": error,
                        "url": url,
                        "saved_path": None,
                        "markdown_type": None,
                        "content_length": 0,
                        "content_preview": None,
                        "domain": urlparse(url).netloc
                    })
        
        # If no results were processed from output but domain folder was found,
        # check for any markdown files in the domain folder
        if not results and domain_folder and os.path.exists(domain_folder):
            for file in os.listdir(domain_folder):
                if file.endswith(".md"):
                    filepath = os.path.join(domain_folder, file)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Reconstruct URL from filename (approximate)
                    filename = os.path.splitext(file)[0]
                    path = filename.replace("_", "/")
                    if path == "index":
                        path = ""
                    reconstructed_url = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}/{path}"
                    
                    results.append({
                        "success": True,
                        "error": None,
                        "url": reconstructed_url,
                        "saved_path": filepath,
                        "content_length": len(content),
                        "content_preview": content[:500] + "..." if len(content) > 500 else content,
                        "markdown_type": "fit_markdown",
                        "domain": urlparse(base_url).netloc
                    })
        
        # If still no results, add an error result
        if not results:
            results.append({
                "success": False,
                "error": "No pages were successfully crawled" if process.returncode != 0 else "No output from crawler",
                "url": base_url,
                "saved_path": None,
                "markdown_type": None,
                "content_length": 0,
                "content_preview": None,
                "domain": urlparse(base_url).netloc
            })
        
    except Exception as e:
        results.append({
            "success": False,
            "error": str(e),
            "url": base_url,
            "saved_path": None,
            "markdown_type": None,
            "content_length": 0,
            "content_preview": None,
            "domain": urlparse(base_url).netloc
        })
    
    finally:
        # Clean up temp file
        if 'temp_config_path' in locals() and os.path.exists(temp_config_path):
            os.unlink(temp_config_path)
    
    return results


# ========================
# UI COMPONENTS
# ========================

def render_header():
    """Render the application header."""
    st.markdown('<div style="text-align: center;"><h1 class="main-header">Advanced Web Scraper</h1></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center;"><p>Extract, filter, and save web content with precision</p></div>', unsafe_allow_html=True)
    st.markdown("---")

def render_input_section():
    """Render the URL input section."""
    st.markdown('<h2 class="sub-header">Specify Target URLs</h2>', unsafe_allow_html=True)
    
    with st.container():
        input_type = st.radio(
            "Select scraping mode:",
            ["Single URL", "Multiple URLs", "Website Crawl"],
            horizontal=True
        )
        
        urls = []
        base_url = ""
        
        if input_type == "Single URL":
            url = st.text_input("Enter URL to scrape:", placeholder="https://example.com/page")
            if url and is_valid_url(url):
                urls = [url]
                base_url = url
            elif url:
                st.warning("Please enter a valid URL (including http:// or https://)")
        
        elif input_type == "Multiple URLs":
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    urls_input = st.text_area(
                        "Enter URLs (one per line):",
                        height=150,
                        placeholder="https://example.com/page1\nhttps://example.com/page2\nhttps://example.com/page3"
                    )
                
                with col2:
                    st.markdown('<div style="height: 50px"></div>', unsafe_allow_html=True)
                    upload_file = st.file_uploader("Or upload a text file:", type=["txt"])
                    
                    if upload_file is not None:
                        urls_from_file = upload_file.getvalue().decode("utf-8")
                        urls_input = urls_from_file
                        st.success(f"Loaded {len(urls_input.strip().split())} URLs from file")
                
                if urls_input:
                    urls = []
                    for line in urls_input.strip().split("\n"):
                        url = line.strip()
                        if url and is_valid_url(url):
                            urls.append(url)
                    
                    if urls:
                        base_url = urls[0]
                        st.info(f"Found {len(urls)} valid URLs")
                        if len(urls) < len(urls_input.strip().split("\n")):
                            st.warning(f"{len(urls_input.strip().split()) - len(urls)} URLs were invalid and will be skipped")
                            
                        # Show URL preview
                        with st.expander("Preview URLs"):
                            for url in urls[:10]:
                                st.markdown(f'<div class="url-preview">{url}</div>', unsafe_allow_html=True)
                            if len(urls) > 10:
                                st.write(f"...and {len(urls) - 10} more")
                    elif urls_input:
                        st.error("No valid URLs found. Make sure URLs include http:// or https://")
        
        else:  # Website Crawl
            base_url = st.text_input("Enter website URL:", placeholder="https://example.com")
            if base_url and not is_valid_url(base_url):
                st.warning("Please enter a valid URL (including http:// or https://)")
    
    return input_type, urls, base_url

def render_crawler_settings(input_type: str):
    """Render appropriate settings based on input type."""
    st.markdown('<h2 class="sub-header">Configuration</h2>', unsafe_allow_html=True)
    
    with st.expander("Content Processing Settings", expanded=True):
        # Core filtering parameters
        st.markdown("#### Content Filtering Parameters")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pruning_threshold = st.slider(
                "Pruning Threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.35,
                step=0.05,
                help="Lower values keep more content, higher values prune more aggressively"
            )
        
        with col2:
            pruning_type = st.selectbox(
                "Pruning Type",
                options=["dynamic", "fixed"],
                index=0,
                help="Dynamic adjusts threshold based on content, fixed uses exact threshold"
            )
        
        with col3:
            min_word_threshold = st.number_input(
                "Minimum Words per Block",
                min_value=0,
                max_value=100,
                value=5,
                help="Text blocks with fewer words than this will be pruned"
            )
        
        # HTML processing options
        st.markdown("#### HTML Processing")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            process_iframes = st.checkbox(
                "Process iframes", 
                value=True,
                help="Extract content from iframes"
            )
        
        with col2:
            remove_overlays = st.checkbox(
                "Remove overlay elements", 
                value=True,
                help="Remove cookie notices, popups, etc."
            )
        
        with col3:
            escape_html = st.checkbox(
                "Escape HTML", 
                value=True,
                help="Convert HTML entities to safe representations"
            )
        
        # Tags to keep/exclude
        st.markdown("#### HTML Tags to Keep")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            keep_nav = st.checkbox("Keep navigation", value=False)
        
        with col2:
            keep_header = st.checkbox("Keep headers", value=False)
        
        with col3:
            keep_footer = st.checkbox("Keep footers", value=False)
        
        keep_tags = []
        if keep_nav:
            keep_tags.append("nav")
        if keep_header:
            keep_tags.append("header")
        if keep_footer:
            keep_tags.append("footer")
        
        # Link processing
        st.markdown("#### Link Processing")
        ignore_links = st.checkbox(
            "Ignore links", 
            value=False,
            help="Don't include links in the markdown output"
        )
    
    # Query-based filtering (BM25) - for all modes
    with st.expander("Query-Based Filtering (Optional)"):
        use_query = st.checkbox(
            "Filter content by relevance to query", 
            value=False,
            help="Use BM25 algorithm to keep only content relevant to your query"
        )
        
        query = ""
        query_threshold = 1.2
        
        if use_query:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                query = st.text_input(
                    "Query", 
                    placeholder="Enter search terms",
                    help="Content will be filtered based on relevance to these terms"
                )
            
            with col2:
                query_threshold = st.slider(
                    "Relevance Threshold",
                    min_value=0.1,
                    max_value=5.0,
                    value=1.2,
                    step=0.1,
                    help="Higher values require stronger relevance to query"
                )
    
    # Deep crawl settings (only for website crawl)
    deep_crawl_settings = {}
    if input_type == "Website Crawl":
        with st.expander("Crawler Behavior", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                deep_crawl_settings["max_depth"] = st.number_input(
                    "Maximum Crawl Depth",
                    min_value=1,
                    max_value=10,
                    value=2,
                    help="How many clicks/links deep to crawl from the starting page"
                )
            
            with col2:
                deep_crawl_settings["max_pages"] = st.number_input(
                    "Maximum Pages",
                    min_value=1,
                    max_value=500,
                    value=20,
                    help="Maximum number of pages to crawl"
                )
            
            deep_crawl_settings["include_external"] = st.checkbox(
                "Include External Links",
                value=False,
                help="Follow links to external domains (may increase crawl time significantly)"
            )
            
            deep_crawl_settings["try_sitemap"] = st.checkbox(
                "Try to find sitemap first",
                value=True,
                help="Attempt to locate and use the website's sitemap before falling back to deep crawling"
            )
    
    # Combine all settings
    settings = {
        "pruning_threshold": pruning_threshold,
        "pruning_type": pruning_type,
        "min_word_threshold": min_word_threshold,
        "process_iframes": process_iframes,
        "remove_overlays": remove_overlays,
        "escape_html": escape_html,
        "keep_tags": keep_tags,
        "ignore_links": ignore_links,
        "use_query": use_query,
        "query": query,
        "query_threshold": query_threshold,
        "deep_crawl_settings": deep_crawl_settings
    }
    
    return settings

def start_scraping(input_type: str, urls: List[str], base_url: str, settings: Dict[str, Any]):
    """Start the scraping process based on user input."""
    if not urls and not base_url:
        st.error("Please enter at least one valid URL to scrape.")
        return None
    
    with st.container():
        progress_container = st.empty()
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        # Create a results placeholder
        results_placeholder = st.empty()
        
        if input_type == "Single URL" and urls:
            with progress_container.container():
                st.markdown(f"<h3>Scraping {urls[0]}</h3>", unsafe_allow_html=True)
            
            progress_text.text("Initializing scraper...")
            progress_bar.progress(10)
            
            # Run the scraper using subprocess
            result = scrape_single_url(urls[0], settings)
            
            progress_bar.progress(100)
            progress_text.text("Scraping completed!")
            
            return [result]
        
        elif input_type == "Multiple URLs" and urls:
            with progress_container.container():
                st.markdown(f"<h3>Scraping {len(urls)} URLs</h3>", unsafe_allow_html=True)
            
            # Set up progress tracking
            progress_text.text(f"Preparing to scrape {len(urls)} URLs...")
            progress_bar.progress(10)
            
            # Start the scraping process
            results = scrape_multiple_urls(urls, settings)
            
            # Update progress
            progress_bar.progress(100)
            progress_text.text(f"Completed scraping {len(urls)} URLs!")
            
            return results
        
        elif input_type == "Website Crawl" and base_url:
            # First check if we should try to find a sitemap
            sitemap_urls = []
            if settings.get("deep_crawl_settings", {}).get("try_sitemap", True):
                with progress_container.container():
                    st.markdown(f"<h3>Checking for sitemap at {base_url}</h3>", unsafe_allow_html=True)
                
                progress_text.text("Looking for sitemap...")
                progress_bar.progress(10)
                
                sitemap_urls, found_sitemap = fetch_sitemap_urls(base_url)
                
                if sitemap_urls:
                    progress_bar.progress(20)
                    progress_text.text(f"Found sitemap with {len(sitemap_urls)} URLs!")
                    
                    # Let user decide if they want to use the sitemap
                    with progress_container.container():
                        st.success(f"Found sitemap with {len(sitemap_urls)} URLs! How would you like to proceed?")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            use_sitemap = st.radio(
                                "Use sitemap?",
                                ["Yes", "No (use deep crawl instead)"],
                                index=0
                            )
                        
                        with col2:
                            if len(sitemap_urls) > 10:
                                max_urls = st.number_input(
                                    "Maximum URLs to scrape from sitemap",
                                    min_value=1,
                                    max_value=len(sitemap_urls),
                                    value=min(20, len(sitemap_urls))
                                )
                                sitemap_urls = sitemap_urls[:max_urls]
                    
                    if use_sitemap == "Yes":
                        # Use sitemap URLs for scraping
                        with progress_container.container():
                            st.markdown(f"<h3>Scraping {len(sitemap_urls)} URLs from sitemap</h3>", unsafe_allow_html=True)
                        
                        progress_text.text(f"Preparing to scrape {len(sitemap_urls)} URLs from sitemap...")
                        progress_bar.progress(30)
                        
                        # Start the scraping process
                        results = scrape_multiple_urls(sitemap_urls, settings)
                        
                        # Update progress
                        progress_bar.progress(100)
                        progress_text.text(f"Completed scraping {len(sitemap_urls)} URLs from sitemap!")
                        
                        return results
            
            # If no sitemap or user chose deep crawl
            with progress_container.container():
                st.markdown(f"<h3>Deep crawling {base_url}</h3>", unsafe_allow_html=True)
            
            progress_text.text(f"Preparing deep crawl...")
            progress_bar.progress(10)
            
            # Start deep crawl
            results = deep_crawl_website(base_url, settings)
            
            # Update progress
            progress_bar.progress(100)
            progress_text.text(f"Completed deep crawl of {base_url}!")
            
            return results
    
    return None

def render_results(results: List[Dict[str, Any]]):
    """Render the scraping results nicely."""
    if not results:
        return
    
    # Count successes and failures
    successes = sum(1 for r in results if r.get("success", False))
    failures = len(results) - successes
    total_content = sum(r.get("content_length", 0) for r in results if r.get("success", False))
    
    # Show metrics
    st.markdown("---")
    st.markdown('<h2 class="sub-header">Scraping Results</h2>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="metrics-container">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{len(results)}</div>
                <div class="metric-label">Total URLs</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{successes}</div>
                <div class="metric-label">Successful</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{failures}</div>
                <div class="metric-label">Failed</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            size_display = f"{total_content/1000:.1f}K" if total_content < 1000000 else f"{total_content/1000000:.1f}M"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{size_display}</div>
                <div class="metric-label">Content Size</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Create a DataFrame for easier display
    results_data = []
    
    for i, result in enumerate(results):
        url = result.get("url", "Unknown URL")
        status = "✅ Success" if result.get("success", False) else "❌ Failed"
        markdown_type = result.get("markdown_type", "None")
        content_length = result.get("content_length", 0)
        content_size = f"{content_length/1000:.1f} KB" if content_length else "0 KB"
        error = result.get("error", "")
        saved_path = result.get("saved_path", "")
        domain = result.get("domain", "unknown")
        
        results_data.append({
            "№": i+1,
            "URL": url,
            "Status": status,
            "Content Type": markdown_type,
            "Size": content_size,
            "Domain": domain,
            "Error": error,
            "Saved Path": saved_path
        })
    
    # Display results as a dataframe with option to download
    if results_data:
        df = pd.DataFrame(results_data)
        
        # Option to download results as CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download results as CSV",
            data=csv,
            file_name="scraping_results.csv",
            mime="text/csv",
        )
        
        # Show the results table
        st.dataframe(df, use_container_width=True)
        
        # Group files by domain folder
        domain_folders = {}
        for result in results:
            if result.get("success") and result.get("saved_path"):
                domain = result.get("domain", "unknown")
                if domain not in domain_folders:
                    domain_folders[domain] = []
                domain_folders[domain].append(result)
        
        # Show saved files by domain
        if domain_folders:
            st.markdown("### Saved Files by Domain")
            
            tabs = st.tabs(list(domain_folders.keys()))
            
            for i, (domain, domain_results) in enumerate(domain_folders.items()):
                with tabs[i]:
                    st.markdown(f"Found {len(domain_results)} files for **{domain}**")
                    
                    for j, result in enumerate(domain_results):
                        if j < 10:  # Limit the number of expandable previews
                            with st.expander(f"{j+1}. {Path(result['url']).name}"):
                                st.markdown(f"**URL:** {result['url']}")
                                st.markdown(f"**Saved to:** {result['saved_path']}")
                                st.markdown("**Content Preview:**")
                                st.markdown(result["content_preview"])
                        elif j == 10:
                            st.write("... and more files (preview limited to 10 files)")
                            break
        
        # Show error summary if there were failures
        if failures > 0:
            st.markdown("### Error Summary")
            
            error_data = []
            for result in results:
                if not result.get("success", False) and result.get("error"):
                    error_data.append({
                        "URL": result.get("url", "Unknown"),
                        "Error": result.get("error", "Unknown error")
                    })
            
            if error_data:
                st.dataframe(pd.DataFrame(error_data), use_container_width=True)


def main():
    """Main application function."""
    # Apply configurations and set theme
    render_header()
    
    # Sidebar with app information
    with st.sidebar:
        st.markdown('<h2 class="sub-header">About</h2>', unsafe_allow_html=True)
        st.markdown("""
        This tool lets you scrape websites and save the content as markdown files, with advanced 
        filtering and processing options.
        
        ### Features
        - Single URL scraping
        - Batch URL scraping
        - Deep website crawling
        - Sitemap detection and processing
        - Content filtering and pruning
        - Query-based content extraction
        - Beautiful markdown output
        
        ### How it works
        1. Enter a URL or multiple URLs
        2. Configure scraping parameters
        3. Start scraping
        4. View results and access saved files
        """)
        
        st.markdown('<h2 class="sub-header">Advanced Options</h2>', unsafe_allow_html=True)
        st.checkbox("Show detailed logs", key="detailed_logs", value=False)
        
        st.markdown("---")
        st.markdown("""
        <footer>
            <p>© 2025 Le Bot Français</p>
            <p>Built with Streamlit and Crawl4AI</p>
        </footer>
        """, unsafe_allow_html=True)
    
    # Main app flow
    input_type, urls, base_url = render_input_section()
    settings = render_crawler_settings(input_type)
    
    # Store results in session state
    if 'scrape_results' not in st.session_state:
        st.session_state.scrape_results = None
    
    # Start button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Start Scraping", use_container_width=True):
            with st.spinner("Scraping in progress..."):
                results = start_scraping(input_type, urls, base_url, settings)
                st.session_state.scrape_results = results
    
    # Display results if available
    if st.session_state.scrape_results:
        render_results(st.session_state.scrape_results)

if __name__ == "__main__":
    main()