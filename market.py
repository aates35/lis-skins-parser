# -*- coding: utf-8 -*-
import json
import requests
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from skin_html_page_parser import SkinHtmlPageParser


def get_item_json_data(items_url: List[str], driver: 'undetected_chromedriver.Chrome') -> List[Dict]:
    items_json_data = []
    for url in items_url:
        try:
            driver.get(url)
            item_parser = SkinHtmlPageParser(driver.page_source)        
            items_json_data.append({
                'name': item_parser.name,
                'site_id': item_parser.site_id,
                'float_value': item_parser.float_value,
                'stickers': item_parser.stickers,
                'price': item_parser.price,
                'url': url,
            })
        except Exception as e:
            print(f"Error parsing item {url}: {e}")
            continue
    return items_json_data


def get_new_items_from_market(items_id_storage, driver: 'undetected_chromedriver.Chrome') -> Tuple[List[Dict], List[int]]:
    params = {
        'sort_by' : 'date_desc',
        'exterior' : '2,4,3,6,1,5',
        'ajax': '1',
    } 
    url = 'https://lis-skins.com/ru/market/csgo/?' 
    url += ''.join([
        f'{key}={value}&'
        for key, value in params.items()
        if value is not None
    ])
    
    # First try using requests (faster and less likely to be blocked)
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            parsed_json = response.json()
            print("Successfully fetched data using requests")
        else:
            raise Exception(f"HTTP {response.status_code}")
    except Exception as e:
        print(f"Requests method failed: {e}, falling back to Selenium")
        
        # Add headers to mimic AJAX request
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        driver.get(url)
        
        # Wait a bit for the page to load
        import time
        import random
        time.sleep(random.uniform(5, 10))  # Random delay between 5-10 seconds
        
        # Check for Cloudflare challenge
        if "Just a moment..." in driver.page_source or "challenge" in driver.page_source.lower():
            print("Cloudflare challenge detected, waiting...")
            # Wait for Cloudflare to finish
            time.sleep(10)
            
            # Check again
            if "Just a moment..." in driver.page_source:
                print("Cloudflare challenge still active, trying to refresh...")
                driver.refresh()
                time.sleep(5)
        
        # Try to find content in different ways
        try:
            # First try to find pre tag (original method)
            content = driver.find_element(By.TAG_NAME, 'pre').text
            parsed_json = json.loads(content)
            print("Found JSON in <pre> tag")
        except:
            try:
                # If no pre tag, try to get the page source and parse it
                page_source = driver.page_source
                print(f"Page source length: {len(page_source)}")
                print(f"Page source starts with: {page_source[:100]}")
                
                # Check if the page source contains JSON
                if page_source.strip().startswith('{') and page_source.strip().endswith('}'):
                    parsed_json = json.loads(page_source)
                    print("Found JSON in page source")
                else:
                    # If it's an HTML page, look for the skins container directly
                    soup = BeautifulSoup(page_source, 'html.parser')
                    
                    # Try to find the skins container
                    skins_container = soup.find('div', class_='skins-market-skins-list')
                    if skins_container:
                        parsed_json = {'skins': str(skins_container)}
                        print("Found skins container in HTML")
                    else:
                        # Try to find any element with market items
                        market_items = soup.find_all('div', class_='market_item')
                        if market_items:
                            # Create a container with the market items
                            container_html = '<div class="skins-market-skins-list">'
                            for item in market_items:
                                container_html += str(item)
                            container_html += '</div>'
                            parsed_json = {'skins': container_html}
                            print(f"Created container with {len(market_items)} market items")
                        else:
                            print("Page content preview:")
                            print(page_source[:500])
                            raise Exception("Could not find skins data on the page")
            except Exception as e:
                print(f"Error parsing page content: {e}")
                print(f"URL attempted: {url}")
                return [], items_id_storage
    
    items = BeautifulSoup(parsed_json.get('skins'), 'html.parser')
    items_url = [
        item['data-link'] 
        for item in items.find_all('div', attrs={'class': 'market_item'})
    ]
    
    if len(items_id_storage) == 0:
        return [], items_url
    
    items_url = list(set([ item_url for item_url in items_url if item_url not in items_id_storage ]))
    items_id_storage += items_url
    items_json_data = get_item_json_data(items_url, driver)

    return items_json_data, items_id_storage
