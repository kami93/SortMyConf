import sys, os, datetime, argparse
import pickle as pkl
from time import sleep

import pandas as pd
from tqdm import tqdm

from errors import *
from contents import get_gscholar_contents, get_citations, get_papers_list

# Solve conflict between raw_input and input on Python 2 and Python 3
if sys.version[0]=="3": raw_input=input

# Default Parameters
CSVPATH = '.' # Current folder

def get_command_line_args():
    now = datetime.datetime.now()

    # Command line arguments
    parser = argparse.ArgumentParser(description='Arguments')
    parser.add_argument('--conference', type=str, required=True, help='Conference name to sort papers.')
    parser.add_argument('--year', type=int, required=True, help='Conference year to sort papers.')
    parser.add_argument('--month', type=int, help='Conference month. (Optinal)')
    parser.add_argument('--csvpath', type=str, help='Path to save the exported csv file. By default it is the current folder')

    # Parse and read arguments and assign them to variables if exists
    args, _ = parser.parse_known_args()

    conference_dict = {'cvpr': 'CVPR',
                       'iccv': 'ICCV',
                       'iclr': 'ICLR',
                       'icml': 'ICML',
                       'eccv': 'ECCV',
                       'nips': 'NeurIPS',
                       'neurips': 'NeurIPS'}
    if args.conference.lower() not in conference_dict.keys():
        raise ValueError("Conference must be one of {}".format(list(conference_dict.keys())))
    conference = conference_dict[args.conference.lower()]

    year = args.year
    month = None
    if args.month:
        if args.month < 1 or args.month > 12:
            raise ValueError("Month must be in range [1, ..., 12].")
            
        if year == now.year and args.month > now.month:
            raise ValueError("Month must be <= {}.".format(now.month))

        month = args.month

    csvpath = CSVPATH
    if args.csvpath:
        csvpath = args.csvpath

    return conference, year, month, csvpath

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

def setup_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.common.exceptions import StaleElementReferenceException
    except Exception as e:
        print(e)
        print("Please install Selenium and chrome webdriver for manual checking of captchas")

    print('Loading...')
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("window-size=1280,800")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36")

    driver = webdriver.Chrome(chrome_options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def save_checkpoint(conference, year, authors, titles, links, idx, citations, etc):
    if idx != 0:
        with open('./temp/backup.pkl', 'wb') as f:
            pkl.dump({'conference': conference,
                      'year': year,
                      'authors': authors,
                      'titles': titles,
                      'links': links,
                      'idx': idx,
                      'citations': citations,
                      'etc': etc}, f)

def restore_checkpoint():
    with open('./temp/backup.pkl', 'rb') as f:
        data = pkl.load(f)
    
    return data['conference'], data['year'], data['authors'], data['titles'], data['links'], data['idx'], data['citations'], data['etc']

def main():
    GSCHOLAR_URL = "https://scholar.google.com/scholar?hl=en&as_sdt=0%2C5&q={}&num=1"
    
    # Variables
    conference, year, month, csvpath = get_command_line_args()

    if month is None:
        print("Please provide month for \"cit/month\" information.")

    # Accumul.
    start_idx = 0
    citations = []
    etc = []

    restored = False
    if os.path.isfile('./temp/backup.pkl'):
        conf_, year_, authors, titles, links, start_idx_, citations, etc = restore_checkpoint()

        if conference == conf_ and year == year_:
            restored = query_yes_no("Restore from backup? {} {} {}/{} papers done.".format(conf_, year_, start_idx_, len(authors)))

    if restored:
        start_idx = start_idx_

    else:
        print("Loading {} {} results".format(conference, year))
        authors, titles, links = get_papers_list(conference, year)
        print("Found {:d} papers.".format(len(authors)))
    
    driver = setup_driver() # Load chrome driver
    for idx in tqdm(range(start_idx, len(authors)), total=len(authors), initial=start_idx):
        title = titles[idx]
        link = links[idx]

        url = GSCHOLAR_URL.format(link.replace(':', '%3A').replace('/', '%2F'))
        driver.get(url)

        while(len(citations) != idx+1):
            """
            While Loop 작동 매커니즘

            구글 스콜라 검색 결과를 읽어와서 다음 예외 상황에 대처
      
            Case (1) 캡차 풀기 요구 받은 경우
            유저가 직접 캡차를 풀고, 터미널에 엔터를 입력해주면 계속 진행.

            Case (2) Auto Query 감지에 걸린 경우
            이 경우는 구글 국가를 변경하는 방법 외에는 Bypass 불가능.
            .com -> .co.kr -> .co.uk -> .ca 순으로 변경.
            .ca 까지 모두 소진한 경우 프로그램 종료 (프로그램 다시 시작하면 됨).

            Case (3) 검색 결과가 없음
            논문 Repo 링크 대신 논문 제목으로 재검색.
            재검색에도 결과 없으면 Citation 0개로 처리 및 "etc" 열에 에러 로그 추가.

            Case (4) 알 수 없는 에러
            Python debugger 실행.
            """

            try:
                # Try getting gscholar search results.
                gs_content = get_gscholar_contents(driver)
                citations.append(get_citations(str(gs_content.format_string)))
                etc.append("")

            except RobotError:
                # You must solve captcha. Case (1).
                save_checkpoint(conference, year, authors, titles, links, idx, citations, etc)
                raw_input("Solve captcha manually and press enter here to continue...")

            except AQError:
                # Replace the google url with one for other counturies. Case (2).
                save_checkpoint(conference, year, authors, titles, links, idx, citations, etc)
                if '.com' in GSCHOLAR_URL:
                    GSCHOLAR_URL = GSCHOLAR_URL.replace('.com', '.co.kr')

                elif '.co.kr' in GSCHOLAR_URL:
                    GSCHOLAR_URL = GSCHOLAR_URL.replace('.co.kr', '.co.uk')

                elif '.co.uk' in GSCHOLAR_URL:
                    GSCHOLAR_URL = GSCHOLAR_URL.replace('.co.kr', '.ca')
                
                else:
                    raise GScholarError()
                
                url = GSCHOLAR_URL.format(link.replace(':', '%3A').replace('/', '%2F'))
                driver.get(url)
                
            except SearchError:
                # No Search Results. Case (3).
                new_url = GSCHOLAR_URL.format("\""+title.replace(' ', '+')+"\"")
                if url != new_url:
                    print("Warning: No search result with link for \"{}\"".format(title))
                    print("Retrying Search with the title...")
                    url = new_url
                    driver.get(url)

                else:
                    print("Error: No search result for \"{}\"".format(title))
                    citations.append(0)
                    etc.append("No Search Results")
            
            except Exception as e:
                # Unknown Error. Case (4).
                print("Error: No success.")
                print(e)
                import pdb; pdb.set_trace()
                a=1
    
        if idx+1 == len(titles):
            save_checkpoint(conference, year, authors, titles, links, idx+1, citations, etc)

        # Delay
        sleep(0.5)

    # Create a dataset and sort by the number of citations
    data = pd.DataFrame(list(zip(authors, titles, citations, links, etc)), index = [i+1 for i in range(len(authors))],
                        columns=['Author', 'Title', 'Citations', 'Source', 'Etc'])
    data.index.name = 'ID'

    # Sort by Citations
    data_ranked = data.sort_values(by='Citations', ascending=False)

    # Add columns with number of citations per year
    now = datetime.datetime.now()
    year_diff = now.year - year
    data_ranked.insert(4, 'cit/year', data_ranked['Citations'] / (year_diff + 1))
    data_ranked['cit/year'] = data_ranked['cit/year'].round(0).astype(int)

    # Add columns with number of citations per month 
    if month is not None:
        month_diff = now.month - month + 12 * year_diff
        data_ranked.insert(5, 'cit/month', data_ranked['Citations'] / (month_diff + 1))
        data_ranked['cit/month'] = data_ranked['cit/month'].round(0).astype(int)

    print(data_ranked)

    # Save results
    data_ranked.to_csv(os.path.join(csvpath, '{}{}'.format(conference, year)+'.csv'), encoding='utf-8') # Change the path

if __name__ == '__main__':
        main()