# %% [markdown]
# ## Accessing API

# %%
import requests
import json
from IPython.display import HTML
from base64 import b64encode

# %%
#optional: use Congress API Agent
#set up method wrapper and CDG Client classes

"""
    CDG Client - An example client for the Congress.gov API.

    @copyright: 2022, Library of Congress
    @license: CC0 1.0
"""
from urllib.parse import urljoin

import requests
import logging
import time
import random
from urllib.parse import urlparse

API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"
LIMIT = "20"
OFFSET = 0

class _MethodWrapper:
    """ Wrap request method to facilitate queries.  Supports requests signature. """

    def __init__(self, parent, http_method):
        self._parent = parent
        self._method = getattr(parent._session, http_method)

    def __call__(self, endpoint, *args, **kwargs):  # full signature passed here
        response = self._method(
            urljoin(self._parent.base_url, endpoint), *args, **kwargs
        )
        # unpack
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json(), response.status_code
        else:
            return response.content, response.status_code


class CDGClient:
    """ A sample client to interface with Congress.gov. """

    def __init__(
        self,
        api_key,
        api_version=API_VERSION,
        response_format=RESPONSE_FORMAT,
        limit=LIMIT,
        offset= str(OFFSET),
        raise_on_error=True,
        max_requests_per_hour: int = 4900
    ):
        """
        Initialize the scraper with rate limiting parameters

        Args:
            max_requests_per_hour: Maximum number of requests to make per hour
        """
        self.max_requests_per_hour = max_requests_per_hour
        self.request_interval = 3600 / max_requests_per_hour  # Time between requests in seconds
        self.last_request_time = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',  # Do Not Track
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("scraper.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("RateLimitedScraper")

        # Track domains and their request counts to be extra cautious
        self.domain_requests = {}
        self.domain_last_request = {}
        
        #Client 
        self.base_url = urljoin(ROOT_URL, api_version) + "/"
        self._session = requests.Session()

        # do not use url parameters, even if offered, use headers
        self._session.params = {"format": response_format, "limit": limit, "offset": offset}
        self._session.headers.update({"x-api-key": api_key})

        if raise_on_error:
            self._session.hooks = {
                "response": lambda r, *args, **kwargs: r.raise_for_status()
            }

    def wait_for_rate_limit(self, url: str) -> None:
        """
        Wait the appropriate amount of time to respect rate limits

        Args:
            url: The URL being requested (used to track per-domain limits)
        """
        current_time = time.time()

        # Global rate limiting
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.request_interval:
            sleep_time = self.request_interval - time_since_last_request
            # Add a small random delay to prevent exact patterns
            sleep_time += random.uniform(0.1, 0.5)
            time.sleep(sleep_time)

        # Per-domain rate limiting
        # domain = urlparse(url).netloc
        # if domain in self.domain_last_request:
        #     domain_time_since_last = current_time - self.domain_last_request[domain]
        #     if domain_time_since_last < .5:  # At least .5 seconds between requests to same domain
        #         time.sleep(.5 - domain_time_since_last + random.uniform(0.1, 0.2))

        # Update timing trackers
        self.last_request_time = time.time()
        # self.domain_last_request[domain] = time.time()

        # Track domain request count
        # if domain not in self.domain_requests:
        #     self.domain_requests[domain] = 0
        # self.domain_requests[domain] += 1

    def __getattr__(self, method_name):
        """Find the session method dynamically and cache for later."""
        method = _MethodWrapper(self, method_name)
        self.__dict__[method_name] = method
        return method

# %%

# BILL_HR = "hr"
# BILL_NUM = 21
BILL_PATH = "bill"
CONGRESS = 118
# parse_xml = lambda data: ET.fromstring(data)  # from bytes, more accurately

# bill_links = []
# pagination_links = []

offset = 0

# %%
bill_info = []

# %%
essa = {}

# %%
# trimmed_bill_info = bill_info[:10]

# %%
# text_links = []

# %%
# cosponsors_list = []

# %%
"""
    CDG Examples

    Below are some examples of using the Bill endpoint with XML parsing.

    @copyright: 2022, Library of Congress
    @license: CC0 1.0
"""
import xml.etree.ElementTree as ET
import json
import sys

# from lxml import etree as ET  # lxml is faster, but an extra download.

# from cdg_client import CDGClient


def print_items(items):
    """Print the items found."""
    for i, item in enumerate(items):

        print(f"{i + 1:2}. {item.tag}:")
        for field in item:
            if field.text:
                print(f"   - {field.tag + ':':20} {field.text.strip()!r}")

    # print(data.xpath("count(.//bills/bill)"), 'bills') # lxml implements count()


# def get_bill(client):
#     """
#     'https://api.congress.gov/v3/bill'
#     this API returns, list of latest bills
#     """
#     data, status_code = client.get(BILL_PATH)
#     print("response data:", data[:70] + b"...", "status:", status_code)


def get_bill_congress(client):
    """
    'https://api.congress.gov/v3/bill/117'
    this API returns, list of Congress bill that's picked

    Bill list by Congress
    """

    try:
      # client.wait_for_rate_limit(data_URL)
      endpoint = f"{BILL_PATH}/{CONGRESS}"
      data, _ = client.get(endpoint)
      data = data

      for bill in data["bills"]:
          congress = bill["congress"]
          chamber_code = bill["type"].lower()
          bill_number = bill["number"]
          title = bill["title"]
          url = bill["url"]

          #true/false if this bill became law
          law_flag = False

          if "Public Law" in bill["latestAction"]["text"]: #or could look at laws -> type. If it says Public law then True
              law_flag = True
          else :
              law_flag = False


          bill_info.append({"congress": congress, 
                           "chamber_code":chamber_code,
                           "bill_number": bill_number,
                           "title": title,
                           "law_flag": law_flag,
                           "url": url})



    #   if "next" in root["pagination"]:
    #       # pagination_links.append(root["pagination"]["next"])

    #       #recursively call get_bill_congress until you get to the end of the bills for this congress

    #       global offset

    #       offset += 250
    #       offset_str = str(offset)
    #       client_mod = CDGClient(api_key, response_format="json", offset= offset_str)
    #       get_bill_congress(client_mod)

    #   else :
    #       print("all done!")

    except OSError as err:
        print('Error:', err)



def get_single_bill(client, bill, congress, chamber, number):
    #do a thing

    try:

        endpoint = f"{BILL_PATH}/{congress}/{chamber}/{number}"
        data, _= client.get(endpoint)
        
        if data["bill"].get("actions"):
            bill["actions"] = data["bill"].get("actions")
        if data["bill"].get("amendments"):
            bill["amendments"] = data["bill"]["amendments"]
        if data["bill"].get("cboCostEstimates"):
            bill["cbo_estimates"] = [estimate for estimate in data["bill"]["cboCostEstimates"]]  
        if data["bill"].get("policyArea"):
            bill["policy_area"] = data["bill"]["policyArea"]["name"]

    except OSError as err:
        print('Error:', err) 


def get_bill_detail(client, bills):
    """
    'https://api.congress.gov/v3/bill/117/hr/21'
    This API returns list of all Bill details
    Bill Details
    """

    try:
        number_processed = 0

        for bill in bills:

            endpoint = f"{BILL_PATH}/{CONGRESS}/{bill["chamber_code"]}/{bill["bill_number"]}"
            data, _ = client.get(endpoint)
            root = data
            # print(root)
            if root["bill"].get("actions"):
                bill["actions"] = root["bill"]["actions"]
            if root["bill"].get("amendments"):
                bill["amendments"] = root["bill"]["amendments"]
            if root["bill"].get("cboCostEstimates"):
                bill["cbo_estimates"] = [estimate for estimate in root["bill"]["cboCostEstimates"]]  
            if root["bill"].get("policyArea"):
                bill["policy_area"] = root["bill"]["policyArea"]["name"]

            number_processed +=1

        print(f"got details for {number_processed} bills")

    except OSError as err:
        print('Error:', err)  



def get_bill_cosponsors(client, bills):
    """
    'https://api.congress.gov/v3/bill/117/hr/21/cosponsors'
    This API returns, cosponsors of the specified Bill
    Bill Cosponsors
    """
    # endpoint = f"{BILL_PATH}/{CONGRESS}/{BILL_HR}/{BILL_NUM}/cosponsors"
    # client.get(endpoint)
    try:
      number_processed = 0
  

      for bill in bills:
          client.wait_for_rate_limit(ROOT_URL)
          endpoint = f"{BILL_PATH}/{CONGRESS}/{bill['chamber_code']}/{bill['bill_number']}/cosponsors"
          data, _ = client.get(endpoint)
        #   print('cosponor data', data)

          bill["cosponsors"] = [item for item in data['cosponsors']]
        #   cosponsors_list.append(cosponors)

        #   print('cosponsor result', cosponors)
          number_processed+=1
        
      print(f"Cosponsors collected for {number_processed} bills")

        
          
    except OSError as err:
        print('Error:', err)



def get_bill_text(client, bills):
    """
    'https://api.congress.gov/v3/bill/117/hr/21/text'
    This API returns, text of the specified Bill
    Bill subjects
    """

    try:
      number_processed = 0

      for bill in bills:
          client.wait_for_rate_limit(ROOT_URL)
          endpoint = f"{BILL_PATH}/{CONGRESS}/{bill['chamber_code']}/{bill['bill_number']}/text"
          data, _ = client.get(endpoint)

          formats = data["textVersions"][0]["formats"]

          xml_formatted = [item["url"] for item in formats if item["type"]== "Formatted XML"]
        #   text_links.append(*xml_formatted)
          bill["text_link"] = xml_formatted
                  
          number_processed +=1

      print(f"Retrieved text links for {number_processed} bills")
          
    except OSError as err:
        print('Error:', err)



def get_text(client, bill, congress, chamber, number):
    client.wait_for_rate_limit(ROOT_URL)
    endpoint = f"{BILL_PATH}/{congress}/{chamber}/{number}/text"
    data, _ = client.get(endpoint)

    formats = data["textVersions"][0]["formats"]

    xml_formatted = [item["url"] for item in formats if item["type"]== "Formatted XML"]

    bill["text_link"] = xml_formatted

# if __name__ == "__main__":
#     """
#     to run the file command :
#         python bill.py <optional api version v3/v4>
#         Example - python bill.py v3 or python bill.py
#     """
#     # This section demonstrates how to store your key in a config file that should be
#     # out of the source code repo and in a secure location only readable by the user
#     # of your application:
#     from configparser import ConfigParser

#     config = ConfigParser()
#     config.read("../secrets.ini")
#     api_key = os.environ.get("CONGRESS_API_KEY")

#     # if you want to view data in json format, you can change the output type here. You can also change the number of replies you want which is set to 250, the max:
#     client = CDGClient(api_key, response_format="json", offset = 0)

#     print(f"Contacting Congress.gov, at {client.base_url} ...")
#     pause = lambda: input('\nPress Enter to continue…')

#     try:

#         # get_bill(client)
#         # pause()
#         # get_bill_congress(client)
#         # print(f"collected {len(bill_info)} bills")
#         # pause()
#         # # get_bill_list_type(client)
#         # # pause()
#         # get_bill_detail(client, bill_info)
#         # print(f"collected detail about bills")
#         # pause()
#         # # get_bill_action(client)
#         # # pause()
#         # # get_bill_amendments(client)
#         # # pause()
#         # # get_bill_committee(client)
#         # # pause()
#         # get_bill_cosponsors(client, bill_info)
#         # print("collected cosponsors")
#         # pause()
#         # # get_bill_relatedbills(client)
#         # # pause()
#         # # get_bill_subjects(client)
#         # # pause()
#         # # get_bill_summaries(client)
#         # # pause()
#         # get_bill_text(client, bill_info)
#         # print("collected text links and all done")
#         # # print(f"collected {len(text_lins)} text links")
#         # # pause()
#         # # get_bill_titles(client)

#     except OSError as err:
#         print('Error:', err)

# %%
from config import settings
api_key = settings.CONGRESS_API_KEY
client = CDGClient(api_key, response_format="json", offset = 0)

get_single_bill(client, essa, '114', 's', 1177)
get_text(client, essa, '114', 's', 1177)