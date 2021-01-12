import re

from bs4 import BeautifulSoup
import requests

from errors import *

ERROR_KW = ['your computer or network may be sending automated queries']
ROBOT_KW = ['unusual traffic from your computer network', 'not a robot', '로봇']
EMPTY_KW = ["정보가 없습니다", "no information is available"]

def get_element(driver, xpath, attempts=5, _count=0):
    '''Safe get_element method with multiple attempts'''
    try:
        element = driver.find_element_by_xpath(xpath)
        return element
    except Exception as e:
        if _count<attempts:
            sleep(1)
            get_element(driver, xpath, attempts=attempts, _count=_count+1)
        else:
            print("Element not found")

def get_gscholar_contents(driver):
    '''Inspect Google Scholar search results with exception handling.'''
    el = get_element(driver, "/html/body")

    if any(kw in el.text for kw in ROBOT_KW):
        # Solve Captcha
        raise RobotError()
    
    elif any(kw in el.text for kw in ERROR_KW):
        # Replace the Google Scholar base URL
        raise AQError()

    c = el.get_attribute('innerHTML').encode('utf-8')
    soup = BeautifulSoup(c, 'html.parser')
    div = soup.findAll("div", { "class" : "gs_r" })[0] # The first contents row.

    if any(kw in div.text for kw in EMPTY_KW):
        # Empty Search Results
        raise SearchError()

    return div

def get_citations(s):
    '''Parse the citations count in a Google Scholar search result.'''
    out = 0

    pattern_kor = ">(.*?)회 인용"
    pattern_eng = "Cited by (.*?)<"

    res = re.search(pattern_kor, s)
    if res is not None:
        out = int(res.group(1))
    
    res = re.search(pattern_eng, s)
    if res is not None:
        out = int(res.group(1))

    return out

def removeDigits(s):
    '''Remove any digits in a given string.'''
    result = ''.join(i for i in s if not i.isdigit())

    return result

def get_papers_list(conference, year):
    '''Helper function to link papers parser for each conference defined.'''
    conference_dict = {'CVPR': get_cvpr,
                       'ICCV': get_iccv,
                       'ICLR': get_iclr,
                       'ICML': get_icml,
                       'ECCV': get_eccv,
                       'NeurIPS': get_nips}
    
    return conference_dict[conference](year)

def get_cvpr(year):
    '''
    CVPR papers parser.
    This gathers a list of titles, authors, links for CVPR papers at the CVF foundation site.
    '''

    if year < 2013 or year > 2020:
        # There are CVPR events happened prior to 2013. However, the CVF site only supports those since 2013.
        # TODO: Support CVPR < 2013.
        raise ValueError("Year must be in [2013, ..., 2020] for CVPR.")
    
    session = requests.Session()
    page = session.get("https://openaccess.thecvf.com/CVPR{}.py".format(year))
    soup = BeautifulSoup(page.content, 'html.parser')

    link_psoup = soup.select("dt.ptitle") # Soup containing titles and links
    cit_psoup = soup.select("div.bibref") # Soup containing authors
    if len(link_psoup) == 0:
        # Some CVPR proceedings are organized by its poster date.
        # The following loop iterates thorough each day.
        for date_soup in soup.select("dd"):
            href = date_soup.select_one("a").get("href")
            page = session.get("https://openaccess.thecvf.com/{}".format(href))
            soup = BeautifulSoup(page.content, 'html.parser')

            link_psoup += soup.select("dt.ptitle")
            cit_psoup += soup.select("div.bibref")

    pattern = "author = {(.*?)},\ntitle"
    authors = [re.search(pattern, paper_.text).group(1) for paper_ in cit_psoup]
    titles = [paper_.select_one("a").text for paper_ in link_psoup]
    links = ["https://openaccess.thecvf.com/{}".format(paper_.select_one("a").get("href")) for paper_ in link_psoup]

    return authors, titles, links

def get_iccv(year):
    '''
    ICCV papers parser.
    This gathers a list of titles, authors, links for ICCV papers at the CVF foundation site.
    '''
    if year not in [2013, 2015, 2017, 2019]:
        # There are ICCV events happened prior to 2013. However, the CVF site only supports those since 2013.
        # TODO: Support ICCV < 2013.
        raise ValueError("Year must be in [2013, 2015, 2017, 2019] for ICCV.")
    
    session = requests.Session()
    page = session.get("https://openaccess.thecvf.com/ICCV{}.py".format(year))
    soup = BeautifulSoup(page.content, 'html.parser')

    link_psoup = soup.select("dt.ptitle") # Soup containing titles and links
    cit_psoup = soup.select("div.bibref") # Soup containing authors
    if len(link_psoup) == 0:
        # Some ICCV proceedings are organized by its poster date.
        # The following loop iterates thorough each day.
        for date_soup in soup.select("dd"):
            href = date_soup.select_one("a").get("href")
            page = session.get("https://openaccess.thecvf.com/{}".format(href))
            soup = BeautifulSoup(page.content, 'html.parser')

            link_psoup += soup.select("dt.ptitle")
            cit_psoup += soup.select("div.bibref")

    pattern = "author = {(.*?)},\ntitle"
    authors = [re.search(pattern, paper_.text).group(1) for paper_ in cit_psoup]
    titles = [paper_.select_one("a").text for paper_ in link_psoup]
    links = ["https://openaccess.thecvf.com/{}".format(paper_.select_one("a").get("href")) for paper_ in link_psoup]

    return authors, titles, links

def get_iclr(year):
    '''
    ICLR papers parser.
    This gathers a list of titles, authors, links for ICLR papers at the DBLP library.
    '''
    if year < 2013 or year > 2020:
        raise ValueError("Year must be in [2013, ..., 2020] for ICLR.")
    
    authors = []
    titles = []
    links = []

    
    first = 0
    total = 1
    while first < total: # DBLP returns 1,000 papers at a query. Repeat queries until every papers are collected.
        results =  request.get("https://dblp.org/search/publ/api?q=toc%3Adb/conf/iclr/iclr{}.bht%3A&f={}&h=1000&format=json".format(year, first)).json()
        
        papers = results['result']['hits']['hit']
        for paper in papers:
            if 'authors' not in paper['info'].keys():
                # No author: This object describes the ICLR conference itself.
                continue

            if type(paper['info']['authors']['author']) == dict:
                # A single author case.
                authors.append(removeDigits(paper['info']['authors']['author']['text']).strip())
            
            else:
                # Multiple authors case.
                authors.append(', '.join(removeDigits(i['text']).strip() for i in paper['info']['authors']['author']))

            titles.append(paper['info']['title'])
            links.append(paper['info']['ee'])
        
        first += 1000
        total = int(results['result']['hits']['@total'])
    
    return authors, titles, links

def get_eccv(year):
    '''
    ECCV papers parser.
    
    This gathers a list of titles, authors, links for ECCV papers using the combination
    of the DBLP library and Springer proceedings page.

    This first gathers the list of links to Springer proceedings pages for ECCV proceedings.
    (Note that ECCV proceedings consists of multiple partitions with 30~40 papers in each.)

    Threading module then simultaneously gather authors, titles, links to the papers from every Springer proceedings pages.
    '''
    from threading import Thread

    if year not in [int(1990 + 2*x) for x in range(16)]:
            raise ValueError("Year must be in [1990, 1992, 1994, ..., 2020] for ECCV.")
    
    session = requests.Session()
    page = session.get("https://dblp.org/db/conf/eccv/index.html") # DBLP page for ECCV proceedings.
    soup = BeautifulSoup(page.content, 'html.parser')
    year_soup = soup.select("li[id^='conf/eccv/{}']".format(year)) # Gather ECCV proceedings at year.

    def get_proc(proc_link, results):
        session_ = requests.Session()
        with session_.get(proc_link) as page:
            proc_soup = BeautifulSoup(page.content, 'html.parser')
            paper_soup = proc_soup.select("li.chapter-item.content-type-list__item") # Rows of papers

            authors = [i.select_one("div.content-type-list__text[data-test='author-text']").text for i in paper_soup]
            titles = [i.select_one("a.content-type-list__link.u-interface-link").text for i in paper_soup]
            links = ["https://link.springer.com{}".format(i.select_one("a.content-type-list__link.u-interface-link").get("href")) for i in paper_soup]

            results.append([authors, titles, links])

    results = []
    ths = []
    for soup_ in year_soup:
        if 'Workshop' not in soup_.select_one("span.title").text: # Exclude workshop papers.
            proc_link = soup_.select_one("li.ee").select_one("a").get("href") # A link to the Springer proceedings.
            th = Thread(target=get_proc, args=(proc_link, results)) # Multithreading to speed-up the process.
            th.start()
            ths.append(th)
    
    for th in ths:
        th.join()

    authors = [j for i in results for j in i[0]]
    titles = [j for i in results for j in i[1]]
    links = [j for i in results for j in i[2]]

    return authors, titles, links

def get_icml(year):
    '''
    ICML papers parser.
    This gathers a list of titles, authors, links for ICML papers at the PMLR site.
    '''
    if year < 2013 or year > 2020:
        # There are ICML events happened prior to 2013. However, the PMLR site only supports those since 2013.
        # TODO: Support ICML < 2013.
        raise ValueError("Year must be in [2013, ..., 2020] for ICML.")

    pmlr_dict = {2020: 'v119', # PMLR code for each year.
                 2019: 'v97',
                 2018: 'v80',
                 2017: 'v70',
                 2016: 'v48',
                 2015: 'v37',
                 2014: 'v32',
                 2013: 'v28'}

    page = session.get('http://proceedings.mlr.press/{}'.format(pmlr_dict[year]))
    soup = BeautifulSoup(page.content, 'html.parser')

    authors = [i.select('span.authors')[0].text.replace(u'\xa0', u' ') for i in soup.select('p.details')]
    titles = [i.text for i in soup.select('p.title')]
    links = [i.select_one("a[href*='html']").get('href') for i in soup.select('p.links')]

    return authors, titles, links

def get_nips(year):
    '''
    NeurIPS papers parser.
    This gathers a list of titles, authors, links for NeurIPS papers at the official NeurIPS site.
    '''
    if year < 1987 or year > 2020:
        raise ValueError("Year must be in [1987, ..., 2020] for NeurIPS.")

    page = session.get('https://papers.nips.cc/paper/{}'.format(year))
    soup = BeautifulSoup(page.content, 'html.parser')

    list_papers_soup = soup.select("ul")[1].select("li") # Rows containing each paper.
    
    authors = [paper_.select_one("i").text for paper_ in list_papers_soup]
    titles = [paper_.select_one("a").text for paper_ in list_papers_soup]
    links = ["https://papers.nips.cc{}".format(paper_.select_one("a").get("href")) for paper_ in list_papers_soup]

    return authors, titles, links