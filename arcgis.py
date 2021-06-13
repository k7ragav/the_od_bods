from urllib import request, parse
from datetime import datetime
import json
import csv

def get_json(url):
    req = request.Request(url)
    return json.loads(request.urlopen(req).read().decode())

#start_url = 'https://opendata.arcgis.com/api/v3/search?filter[tags]=any(renfrewshire)&filter[openData]=true'
start_url = 'https://opendata.arcgis.com/api/v3/search?catalog[groupIds]=any(79dc9ae7552e4782bf66dadbdf049a0d,bcaad01ef27a4457b9c9406818eaca5d)'
url = start_url

datasets = []

while True:
    d = get_json(url)
    datasets += d['data']
    if 'next' in d['meta']  and d['meta']['next']:
        url = d['meta']['next']
        print(f"Next {url}")
    else:
        break

print(f"Found {len(datasets)} datasets")

prepped = []
for e in datasets:
    prepped.append([e['attributes'].get('name', ""),
                    e['attributes'].get('source', ""),
                    e.get('links', {}).get('itemPage', ""),
                    "", #Link to data
                    datetime.utcfromtimestamp(
                        e['attributes'].get('created', 0)/1000).strftime(
                            '%Y-%m-%d'),
                    datetime.utcfromtimestamp(
                        e['attributes'].get('modified', 0)/1000).strftime(
                            '%Y-%m-%d'),
                    # ^^ Should really do something better than defaulting to start of epoch
                    e['attributes'].get('size', ""),
                    e['attributes'].get('type', ""),
                    e['attributes'].get('recordCount', ""),
                    ";".join(e['attributes'].get('tags', [])),
                    "", #Manual tags
                    "", #license
                    e['attributes'].get('searchDescription', "")
                    ])

    
                    
with open('renfrew.csv', 'w') as csvf:
    w = csv.writer(csvf, quoting=csv.QUOTE_MINIMAL)
    for r in prepped:
        if r[-1]:
            r[-1] = r[-1].replace('\n', ' ')
        w.writerow(r)
                                                                       
                                                                       