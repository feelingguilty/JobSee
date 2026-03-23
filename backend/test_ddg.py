from ddgs import DDGS
query = 'site:naukri.com/job-listings ai developer delhi python'
with DDGS() as ddgs:
    results = list(ddgs.text(query, max_results=10, timelimit='w'))
    print(f"Total results: {len(results)}")
    for r in results:
        print(r['href'])
