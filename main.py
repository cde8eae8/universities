from selenium import webdriver
import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import collections
import difflib
import tqdm
import time
import json
import enum
import re
import pandas as pd
import argparse
import requests
from lxml import etree
from urllib.parse import urlparse

import resources

country_code_to_country_unirank = {
    "al": "Albania",
    "ad": "Andorra",
    "at": "Austria",
    "by": "Belarus",
    "be": "Belgium",
    "ba": "Bosnia and Herzegovina",
    "bg": "Bulgaria",
    "hr": "Croatia",
    "cz": "the Czech Republic",
    "dk": "Denmark",
    "ee": "Estonia",
    "fi": "Finland",
    "fr": "France",
    "de": "Germany",
    "gr": "Greece",
    "hu": "Hungary",
    "is": "Iceland",
    "ie": "Ireland",
    "it": "Italy",
    "lv": "Latvia",
    "li": "Liechtenstein",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "mt": "Malta",
    "md": "Moldova",
    "mc": "Monaco",
    "me": "Montenegro",
    "nl": "the Netherlands",
    "mk": "North Macedonia",
    "no": "Norway",
    "pl": "Poland",
    "pt": "Portugal",
    "ro": "Romania",
    "ru": "Russia",
    "sm": "San Marino",
    "rs": "Serbia",
    "sk": "Slovakia",
    "si": "Slovenia",
    "es": "Spain",
    "se": "Sweden",
    "ch": "Switzerland",
    "ua": "Ukraine",
    "gb": "the United Kingdom",
    "va": "the Vatican City State",
}

country_code_to_country_qs = {
    # "al": "Albania",
    # "ad": "Andorra",
    "at": "Austria",
    "by": "Belarus",
    "be": "Belgium",
    "ba": "Bosnia & Herzegovina",
    "bg": "Bulgaria",
    "hr": "Croatia",
    "cz": "Czechia",
    "dk": "Denmark",
    "ee": "Estonia",
    "fi": "Finland",
    "fr": "France",
    "de": "Germany",
    "gr": "Greece",
    "hu": "Hungary",
    "is": "Iceland",
    "ie": "Ireland",
    "it": "Italy",
    "lv": "Latvia",
    # "li": "Liechtenstein",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "mt": "Malta",
    # "md": "Moldova",
    # "mc": "Monaco",
    # "me": "Montenegro",
    "nl": "Netherlands",
    # "mk": "North Macedonia",
    "no": "Norway",
    "pl": "Poland",
    "pt": "Portugal",
    "ro": "Romania",
    "ru": "Russia",
    # "sm": "San Marino",
    "rs": "Serbia",
    "sk": "Slovakia",
    "si": "Slovenia",
    "es": "Spain",
    "se": "Sweden",
    "ch": "Switzerland",
    "ua": "Ukraine",
    "gb": "United Kingdom",
    # "va": "Vatican City State",
}

country_to_country_code_qs = {
    v: k for k, v in country_code_to_country_qs.items()
}

class PartType(enum.StrEnum):
    UNIVERSITY = 'UNIVERSITY'
    PROGRAM = 'PROGRAM'
    OTHER = 'OTHER'

def get_title_from_links(link):
    r = requests.get(link)
    if r.status_code != 200:
        raise RuntimeError(f"request to {link} failed with code {r.status_code}")
    htmlparser = etree.HTMLParser()
    page = etree.fromstring(r.content, htmlparser)
    title_node = page.xpath('.//head/title')[0]
    title = html.unescape(''.join(title_node.itertext()))
    return title

def get_titles_from_links(links):
    driver = webdriver.Chrome()
    titles = {}
    for link in links:
        driver.get(link)
        titles[link] = driver.title
    return titles

def analyze_part(part):
    UNIVERSITY_WORDS = [
        'university',
        'universität',
        'università',
    ]
    PROGRAM_MASTER = [
        r'm\.a',
        r'ma',
        r'master',
        r'msc',
        r'm\.s',
        r'msc\.',
        r'm\.sc',
        r'mres',
        r'll\.m',
    ]
    PROGRAM_BACHELOR = [
        r'bachelor',
        r'b\.sc',
    ]
    for university in UNIVERSITY_WORDS:
        if university in part:
            return PartType.UNIVERSITY
    for bachelor in PROGRAM_MASTER:
        if re.match(r'.*\b' + bachelor + r'\b.*', part):
            return PartType.PROGRAM
    for bachelor in PROGRAM_BACHELOR:
        if re.match(r'.*\b' + bachelor + r'\b.*', part):
            return PartType.PROGRAM
    return PartType.OTHER

def collect_rankings():
    elements_per_page = 1000
    n_pages = 2
    driver = webdriver.Chrome()
    rankings = []
    for page in range(1, n_pages + 1):
        link = f'https://www.topuniversities.com/world-university-rankings?page={page}&items_per_page={elements_per_page}&sort_by=rank&order_by=asc'
        driver.get(link)
        wait = WebDriverWait(driver, timeout=120)
        wait.until(lambda d: driver.find_elements(By.XPATH, ".//div[contains(@class, 'new-ranking-cards')]"))
        elements = driver.find_elements(By.XPATH, ".//div[contains(@class, 'new-ranking-cards')]")
        for element in elements:
            link = element.find_element(By.XPATH, ".//a[contains(@class, 'uni-link')]").text.strip()
            location = element.find_element(By.XPATH, ".//div[contains(@class, 'location')]")
            rank = element.find_element(By.XPATH, ".//div[contains(@class, 'rank-square')]").text
            print(rank)
            assert rank.startswith('Rank ')
            rank = rank[4:]
            location_text = location.text.replace(',,', ',')
            if 'Russia' in location_text or 'United States' in location_text:
                continue
            if 'California State University - Long Beach' in link:
                continue

            city, country = [p.strip() for p in location_text.split(',', 1)]
            country_code = country_to_country_code_qs.get(country)
            ranking = {
                'university': link,
                'city': city,
                'country': country,
                'country_code': country_code,
                'rank': rank,
            }
            rankings.append(ranking)
    unknown_countries = set()
    for ranking in rankings:
        if ranking['country_code'] == None:
            unknown_countries.add(ranking['country'])
    print('unknown countries:')
    print(sorted(unknown_countries))
    return rankings
    

def collect_universities_in_country(country_code):
    base = 'https://www.4icu.org'
    link = f'{base}/{country_code}/a-z'
    r = requests.get(link)
    if r.status_code != 200:
        raise RuntimeError(f"request to {link} failed with code {r.status_code}")
    htmlparser = etree.HTMLParser()
    page = etree.fromstring(r.content, htmlparser)
    table = page.xpath('.//table')[0]
    links = table.xpath('.//tbody/tr/td/a')
    data = {}
    for link in links:
        university = ''.join(link.itertext())
        link_path = link.get('href')
        assert link_path.startswith('/reviews') or link_path.startswith('/about')
        if link_path.startswith('/about'):
            continue
        link = base + link_path
        data[university] = link
    universities = []
    for i, (university, link) in tqdm.tqdm(enumerate(data.items()), total=len(data), desc=f'collecting {country_code}'):
        data = collect_university_info(link)
        data['country'] = country_code
        universities.append(data)
        if (i + 1) % 10 == 0:
            time.sleep(5)
    return universities

def collect_university_info(review_link):
    r = requests.get(review_link)
    if r.status_code != 200:
        raise RuntimeError(f"request to {review_link} failed with code {r.status_code}")
    htmlparser = etree.HTMLParser()
    page = etree.fromstring(r.content, htmlparser)
    heading = page.xpath(".//div/h2[contains(text(), 'University Identity')]")[0]
    div = heading.getparent().getparent()
    rows = div.xpath(".//table//tr")
    data = {
        'local_names': []
    }
    university_names = {}
    for row in rows:
        value_node = row.xpath('./td')[0]
        field_name = ''.join(row.xpath('./th')[0].itertext()).strip()
        field_value = ''.join(value_node.itertext()).strip()
        if field_name == 'Name':
            university_names[(0, 'basic')] = field_value
            data['link'] = value_node.xpath('.//a')[0].get('href')
        elif field_name.startswith('Name (English)'):
            university_names[(1, 'english')] = field_value
        if field_name.startswith('Name'):
            data['local_names'].append(field_value)
    data['name'] = max(university_names.items(), key=lambda v:v[0])[1]
    if 'name' not in data or 'link' not in data:
        raise RuntimeError(f"Can not extract link or name from {review_link}")
    
    heading = page.xpath(".//div/h2[contains(text(), 'University Location')]")[0]
    div = heading.getparent().getparent()
    rows = div.xpath(".//table//tr")
    for row in rows:
        value_node = row.xpath('./td')[0]
        field_name = ''.join(row.xpath('./th')[0].itertext()).strip()
        field_value = ''.join(value_node.itertext()).strip()
        if field_name == 'Address':
            address = field_value.replace('\r\n', '\n')
            data['address'] = address
            address = [line.strip() for line in address.split('\n')]
            city = address[1]
            data['city'] = city
    return data

def extract_study(title):
    NON_SEPARATORS = set(('(', ')', ' ', '.', '"', '\'', ':', ','))
    words = title.split(' ')
    separators = []
    for word in words:
        word = word.strip()
        if not word: continue
        if len(word) <= 1 and not all(c.isalpha() for c in word):
            separators.append(word)
    separators = set(separators)
    if len(separators) > 1:
        raise RuntimeError(f'Multiple separators found in title {title}: {separators}')
    if len(separators) == 0:
        return {PartType.PROGRAM: title}
    parts = [part.strip() for part in title.split(next(iter(separators)))]
    result = {PartType.OTHER: []}
    for part in parts:
        unified_part = part.lower()
        part_type = analyze_part(unified_part)
        if part_type == PartType.OTHER:
            result[part_type].append(part)
            continue
        if part_type in result:
            raise RuntimeError(f'Multiple parts for part type {part_type}: {result[part_type]}, {part}')
        result[part_type] = part
    # if no program was found & only one part of the title is not designated
    if len(result[PartType.OTHER]) == 1:
        if PartType.PROGRAM not in result:
            result[PartType.PROGRAM] = result[PartType.OTHER][0]
            del result[PartType.OTHER]
    if PartType.PROGRAM not in result:
        result[PartType.PROGRAM] = max(result[PartType.OTHER], key=len, default=None)
    return result

def find_university_entry(universities, link):
    link = link.strip()
    if not link:
        return None
    def unify_link(link):
        if link.startswith('www.'):
            return link[3:]
        return link
    domain = unify_link(urlparse(link).netloc)
    for university in universities:
        if not university['link'].strip():
            continue
        university_domain = unify_link(urlparse(university['link']).netloc)
        if domain.endswith(university_domain):
            return university
    return None

def find_ranking_entry(rankings: pd.DataFrame, university):
    # TODO: compare country codes in universities & rankings
    rankings = [ranking for ranking in rankings if ranking['country_code'] == university['country']]
    if not rankings:
        return None
    university_names = [university['name']] + university.get('local_names', [])
    best_match = None
    best_similarity = 0.0
    for university_name in university_names:
        ranking_name = difflib.get_close_matches(university_name, [ranking['university'] for ranking in rankings], n=1, cutoff=0.9)
        if len(ranking_name) == 0:
            continue
        ranking_name = ranking_name[0]
        similarity = difflib.SequenceMatcher(None, ranking_name, university_name).ratio()
        if similarity >= best_similarity:
            best_similarity = similarity
            best_match = ranking_name
    if best_match is None:
        return best_match
    return [ranking for ranking in rankings if ranking['university'] == best_match][0]

def extract_info_from_link(link):
    universities = resources.load_universities()
    rankings = resources.load_rankings()
    title = get_title_from_links(link)
    entry = extract_study(title)
    entry['link'] = link
    entry['title'] = title
    target_university = find_university_entry(universities, link)
    if target_university is not None:
        entry['university'] = target_university
        ranking = find_ranking_entry(rankings, target_university)
        if ranking is not None:
            entry['ranking'] = ranking
    return entry

def main():
    titles = [
        'https://www.uni-due.de/in-east/study_programs/ma_meas/',
        'https://www.geschkult.fu-berlin.de/en/e/ma-global-east-asia/our-program/index.html',
        'https://www.uni-frankfurt.de/35792022',
        'https://www.arts.ac.uk/subjects/fine-art/postgraduate/mres-art-exhibition-studies-csm',
        'https://www.uva.nl/en/programmes/masters/comparative-cultural-analysis-arts-and-culture/comparative-cultural-analysis.html?origin=5BOaRAofTjCccATraJp2XA',
        'https://www.gla.ac.uk/postgraduate/erasmusmundus/magma/',
        'https://www.unive.it/web/en/6434/home',
        'https://www.unibocconi.it/en/programs/master-science/economics-and-management-arts-culture-media-and-entertainment',
        'https://curriculum.maastrichtuniversity.nl/education/master/media-studies-digital-cultures',
        'https://www.su.se/english/search-courses-and-programmes/hicao-1.517236?open-collapse-boxes=programme-contact,programme-application',
        'https://globalstudies-masters.eu/',
        'https://www.mundusmapp.org/',
        'https://courses.ceu.edu/programs/ma/master-arts-international-public-affairs',
        'https://www.uva.nl/shared-content/programmas/en/masters/international-development-studies/international-development-studies.html?origin=znSrDUT%2BQ5uz6dso72fBmw',
        'https://www.ru.nl/en/education/masters/international-relations',
        'https://www.uni-bremen.de/mair',
        'https://www.uni-leipzig.de/en/studying/prospective-students/courses-of-study/degree-programme/course/show/global-studies-ma',
        'https://www.goethe-university-frankfurt.de/120919453/Application_M_A__ISPC',
        'https://www.fau.eu/studiengang/standards-of-decision-making-across-cultures-ma/',
        'https://www.wu.ac.at/en/programs/masters-programs/socio-ecological-economics-and-policy/overview/',
        'https://corsi.unibo.it/2cycle/gioca/index.html',
        'https://www.unive.it/web/en/6434/home',
        'https://www.iulm.it/en/offerta-formativa/corsi-di-lauree-magistrali/arte-valorizzazione-mercato/arte-valorizzazione-mercato',
        'https://www.unibocconi.it/en/programs/master-science/economics-and-management-arts-culture-media-and-entertainment',
        'https://www.eact-unito.info/cultura-e-territorio',
        'https://emle.org/programme-structure-2/',
        'https://www.jura.fu-berlin.de/en/studium/masterstudiengaenge/mbl-fu/program/index.html',
        'https://www.rewi.hu-berlin.de/en/sp/angebote/master/idr',
        'https://emildai.eu/',
        'https://vu.nl/en/education/master/law-and-politics-of-international-security',
        'https://gchumanrights.org/education/regional-programmes/ema/about.html',
        'https://studies.ku.dk/masters/cognition-and-communication/',
        'https://www.uu.se/en/study/programme/masters-programme-human-computer-interaction',
        'https://studieren.univie.ac.at/en/degree-programmes/master-programmes/communication-science-master/',
        'https://international.unitn.it/mhci/admission-requirements',
        'https://www.uni-saarland.de/en/study/programmes/bachelor/computer-science.html',
        'https://www.uni.lu/fstm-en/study-programs/bachelor-in-computer-science/admissions/',
        'https://www.unipd.it/en/educational-offer/first-cycle-degree/engineering?tipo=L&scuola=IN&ordinamento=2024&key=IN2801&cg=engineering',
        'https://international.unitn.it/ict/',
        'https://acsai.di.uniroma1.it/#programme'
    ]
    parser = argparse.ArgumentParser()
    parser.add_argument('--load', action='store_true')
    parser.add_argument('--collect-universities', action='store_true')
    parser.add_argument('--collect-rankings', action='store_true')
    args = parser.parse_args()
    if args.load:
        titles = get_titles_from_links(titles)
        entries = []
        for link, title in titles.items():
            data = {}
            data['link'] = link
            data['title'] = title
            entries.append(data)
        with open('info.json', 'w') as f:
            json.dump(entries, f, indent=2)
        return
    if args.collect_universities:
        countries = list(country_code_to_country_unirank.keys())
        for country_code in countries:
            known_universities = resources.load_universities()
            other_universities = [u for u in known_universities if u['country'] != country_code]
            country_universities = collect_universities_in_country(country_code)
            known_universities = other_universities
            known_universities += country_universities
            with open('universities.json', 'w') as f:
                json.dump(known_universities, f, indent=2)
        return
    if args.collect_rankings:
        rankings = collect_rankings()
        with open('rankings.json', 'w') as f:
            json.dump(rankings, f, indent=2)
        return
    data = []
    universities = resources.load_universities()
    rankings = resources.load_rankings()
    with open('info.json') as f:
        titles = json.load(f)
    for title in titles:
        entry = extract_study(title['title'])
        entry['title'] = title['title']
        entry['link'] = title['link']
        target_university = find_university_entry(universities, title['link'])
        if target_university:
            entry['university_site'] = target_university['link']
            entry['university_address'] = target_university['city'] + ', ' + target_university['country']
            entry['university_name'] = target_university['name']
            ranking = None
            # TODO: match by local & en name
            # TODO: match by country
            ranking = find_ranking_entry(rankings, target_university)
            if ranking is not None:
                entry['ranking_university'] = ranking['university']
                #entry['ranking_world'] = ranking['ranking']
        data.append(entry)
    df = pd.DataFrame.from_dict(data = data)
    df.to_html('out.html')

if __name__ == "__main__":
    main()