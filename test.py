import logging
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logging.basicConfig(level=logging.DEBUG)

#http://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request

s = requests.Session()
retries = Retry(total=5,
                backoff_factor=0.5,
                method_whitelist=["GET", "POST"],
                status_forcelist=[ 404, 500, 502, 503, 504 ])
s.mount('http://', HTTPAdapter(max_retries=retries))
data = "{}"
try:
    r = s.post('http://httpstat.us/500', data)
    print r
except requests.exceptions.RetryError as e:
    print e
