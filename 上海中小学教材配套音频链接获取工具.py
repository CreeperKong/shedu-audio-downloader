import argparse
import requests
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from urllib.parse import urljoin # <-- NEW IMPORT

def fetch_and_parse(code):
    """
    Posts a code to the URL, extracts the title and all .shtml links from the response.

    Args:
        code (str): The 8-digit code to post.
    """
    base_url = "https://mp3.bookmall.com.cn"
    target_url = f"{base_url}/book/access.action"
    
    # Set the User-Agent header to mimic IE 11 on Windows 8.1
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko"
    }
    
    # The data payload for the POST request
    payload = {
        "code": code
    }

    try:
        # Make the POST request
        response = requests.post(target_url, headers=headers, data=payload, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the title using the specified CSS selector
        title_element = soup.select_one('dl.EnglishBox dd h5')
        title = title_element.get_text(strip=True) if title_element else "No title found."
        
        # Print the code and the extracted title
        print(f"{Fore.LIGHTGREEN_EX}{code}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTGREEN_EX}{title}{Style.RESET_ALL}")

        # Find all anchor (<a>) tags that have an 'href' attribute ending in '.shtml'
        shtml_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.shtml')]

        if shtml_links:
            for link in shtml_links:
                # --- MODIFICATION START ---
                # Convert the relative link to an absolute URL
                full_url = urljoin(base_url, link)
                print(f"{Fore.CYAN}{full_url}{Style.RESET_ALL}")
                # --- MODIFICATION END ---
        else:
            print(f"{Fore.YELLOW}No .shtml links found for this code.{Style.RESET_ALL}")

    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}An error occurred for code {code}: {e}{Style.RESET_ALL}")

def main():
    """
    Main function to parse command-line arguments and run the script.
    """
    # Initialize colorama for cross-platform colored output
    init()

    parser = argparse.ArgumentParser(
        description="Fetch titles and .shtml links from bookmall by posting access codes.",
        epilog="Example: python get_links.py -c \"12345678,87654321\""
    )
    parser.add_argument(
        "-c", "--codes",
        required=True,
        help="A comma-separated string of 8-digit codes (e.g., 'no1,no2,no3')."
    )

    args = parser.parse_args()
    
    # Split the comma-separated string of codes into a list
    codes = [code.strip() for code in args.codes.split(',')]
    
    # Use a set to avoid processing duplicate codes
    unique_codes = sorted(list(set(codes)))

    for i, code in enumerate(unique_codes):
        if not (code.isdigit() and len(code) == 8):
            print(f"{Fore.YELLOW}Warning: '{code}' is not a valid 8-digit number. Skipping.{Style.RESET_ALL}")
            continue
        
        fetch_and_parse(code)
        
        # Print the separator after each code's results
        if i < len(unique_codes) - 1:
             print(f"{Fore.LIGHTRED_EX}--------{Style.RESET_ALL}")


if __name__ == "__main__":
    main()