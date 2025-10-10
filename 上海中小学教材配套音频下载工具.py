#!/usr/bin/env python3

import argparse
import requests
import os
import re
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from urllib.parse import urljoin, unquote # <-- MODIFIED IMPORT
from tqdm import tqdm

def sanitize_filename(name):
    """Removes characters that are invalid in folder or file names."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    sanitized = re.sub(r'__+', '_', sanitized)
    sanitized = sanitized.strip(' _')
    return sanitized

def download_file(url, base_dir, folder_format, code, title, silent):
    """
    Downloads a file from a URL with a progress bar.
    """
    sub_folder = ""
    if folder_format == 'ct':
        sub_folder = f"{code}-{title}"
    elif folder_format == 'c':
        sub_folder = code
    elif folder_format == 't':
        sub_folder = title
    elif folder_format == 'tc':
        sub_folder = f"{title}-{code}"

    safe_sub_folder = sanitize_filename(sub_folder)
    download_path = os.path.join(base_dir, safe_sub_folder)
    os.makedirs(download_path, exist_ok=True)

    try:
        with requests.get(url, stream=True, timeout=20) as r:
            r.raise_for_status()
            
            filename = ""
            if "content-disposition" in r.headers:
                disp = r.headers['content-disposition']
                match = re.search(r'filename="?([^"]+)"?', disp)
                if match:
                    # --- FIX START ---
                    # Decode the filename from the header
                    filename = unquote(match.group(1))
                    # --- FIX END ---
            
            if not filename:
                # --- FIX START ---
                # Decode the filename from the URL as a fallback
                filename = unquote(url.split('/')[-1])
                # --- FIX END ---

            file_path = os.path.join(download_path, sanitize_filename(filename))
            total_size = int(r.headers.get('content-length', 0))

            with open(file_path, 'wb') as f, tqdm(
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                desc=f"  -> {filename}",
                disable=silent
            ) as bar:
                for chunk in r.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    bar.update(size)
            
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}  -> Download failed: {e}{Style.RESET_ALL}")
    except IOError as e:
        print(f"{Fore.RED}  -> File error: {e}{Style.RESET_ALL}")


def fetch_and_parse(code, args):
    """
    Posts a code, extracts title/links, and optionally downloads them.
    """
    base_url = "https://mp3.bookmall.com.cn"
    target_url = f"{base_url}/book/access.action"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko"}
    payload = {"code": code}

    try:
        response = requests.post(target_url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title_element = soup.select_one('dl.EnglishBox dd h5')
        title = title_element.get_text(strip=True) if title_element else "No title found"
        
        print(f"{Fore.LIGHTGREEN_EX}{code}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTGREEN_EX}{title}{Style.RESET_ALL}")

        shtml_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.shtml')]

        if not shtml_links:
            print(f"{Fore.YELLOW}No .shtml links found for this code.{Style.RESET_ALL}")
            return

        for link in shtml_links:
            full_url = urljoin(base_url, link)
            print(f"{Fore.CYAN}{full_url}{Style.RESET_ALL}")
            if args.download:
                download_file(full_url, args.target, args.folder_format, code, title, args.silent)

    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}An error occurred for code {code}: {e}{Style.RESET_ALL}")

def main():
    """Main function to parse command-line arguments and run the script."""
    init()
    parser = argparse.ArgumentParser(
        description="Fetch and download files from bookmall by posting access codes.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-c", "--codes", required=True, help="A comma-separated string of 8-digit codes.")
    parser.add_argument("-d", "--download", action="store_true", help="Trigger the download of all found files.")
    parser.add_argument("-t", "--target", default=".", help="Target directory for downloads (default: current directory).")
    parser.add_argument(
        "-f", "--folder-format",
        default="n",
        choices=['ct', 'c', 't', 'tc', 'n'],
        help="""Set the sub-folder format for downloaded files.
'ct': {code}-{title}
'c': {code}
't': {title}
'tc': {title}-{code}
'n': No sub-folder (default)"""
    )
    
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_false", dest="silent", help="Show download progress bar (default).")
    verbosity_group.add_argument("-s", "--silent", action="store_true", help="Do not show download progress bar.")

    args = parser.parse_args()
    
    unique_codes = sorted(list(set(code.strip() for code in args.codes.split(','))))

    for i, code in enumerate(unique_codes):
        if not (code.isdigit() and len(code) == 8):
            print(f"{Fore.YELLOW}Warning: '{code}' is not a valid 8-digit number. Skipping.{Style.RESET_ALL}")
            continue
        
        fetch_and_parse(code, args)
        
        if i < len(unique_codes) - 1:
             print(f"{Fore.LIGHTRED_EX}--------{Style.RESET_ALL}")

if __name__ == "__main__":
    main()