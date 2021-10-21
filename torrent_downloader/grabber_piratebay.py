import re
import bs4
import time
import logging
import requests
from simplejson.errors import JSONDecodeError


class PirateBayResult:
    def __init__(self, beautiful_soup_tag=None, json_entry=None):
        self.title = self.magnet = self.size = ''
        self.seeders = self.leechers = 0
        if beautiful_soup_tag is not None:
            try:
                tds = beautiful_soup_tag.find_all('td')
                self.title = tds[1].a.text
                self.magnet = tds[1].find_all('a')[1].attrs.get('href')
                self.seeders = int(tds[-2].text)
                self.leechers = int(tds[-1].text)
                description = tds[1].find_all('font', attrs={'class': "detDesc"})[0].text
                self.size = description.split(',')[1][6:]
            except (IndexError, ValueError, AttributeError):
                return

        if json_entry is not None:
            self.title = json_entry.get("name")
            self.magnet = 'magnet:?xt=urn:btih:{}'.format(json_entry.get("info_hash"))
            self.seeders = json_entry.get("seeders")
            self.leechers = json_entry.get("leechers")
            self.size = self.humanize(int(json_entry.get("size")))

    @staticmethod
    def humanize(num):
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s" % (num, unit)
            num /= 1024.0
        return "%.1f%sB" % (num, 'Yi')

    def __bool__(self):
        return bool(self.title or self.magnet)


class PirateBayTorrentGrabber:
    TYPE_URL = {'movie': '207', 'show': '208', 'video': '200', 'audio': '100', 'porn': '500', 'game': '400'}

    def __init__(self):
        self.proxies = self.setup_proxies()

    @staticmethod
    def setup_proxies():
        ret = requests.get("https://piratebayproxy.info/")
        if ret.ok:
            try:            
                bs4_response = bs4.BeautifulSoup(ret.text, "lxml")
                proxylist = bs4_response.find('table', attrs={'id': 'searchResult'})
                return [p.td.a.attrs.get('href') for p in proxylist.find_all('tr') if p.td]
            except:
                pass
        logging.warning("PirateBay Proxy down again. Please inform your Serverbetreiber :)")


    def get_torrents(self, search, type_=None):
        results = self._get_search_results(search, type_=type_)
        logging.info('Found {} torrents, selecting...'.format(len(results)))
        return self._select_search_results(results)

    def _parse_api(self, response):
        try:
            results_json = response.json()[:30] if response else None
            if not results_json or len(results_json) == 1 and results_json[0].get("id") == "0":
                return None
            return [PirateBayResult(json_entry=entry) for entry in results_json]
        except (JSONDecodeError, AttributeError):
            return None

    def _parse_site(self, response):
        try:
            bs4_response = bs4.BeautifulSoup(response.text, "lxml")
            main_table = bs4_response.find('table', attrs={'id': 'searchResult'})
            if main_table:
                return [PirateBayResult(beautiful_soup_tag=tag) for tag in main_table.find_all('tr')[1:]]
        except:
            return None

    def _get_search_results(self, search, type_=None):
        type_ = self.TYPE_URL.get(type_) if type_ else '0'
        self.proxies = []
        for proxy_url in self.proxies:
            logging.info('Searching {} for "{}"'.format(proxy_url, search))
            response = self._make_request('{}/newapi/q.php?q={}&cat={}'.format(proxy_url, search, type_),
                                          timeout=2, retries=2)
            if response:
                results = self._parse_api(response)
                if results:
                    return results
            else:
                response = self._make_request('{}/s/?q={}&cat={}'.format(proxy_url, search, type_),
                                              timeout=2, retries=2)
                if response:
                    results = self._parse_site(response)
                    if results:
                        return results
        else:
            logging.info('Searching the original pirate bay for "{}"'.format(search))
            response = self._make_request('https://apibay.org/q.php?q={}&cat={}'.format(search, type_),
                                          timeout=2, retries=2)
            results = self._parse_api(response)
            if results:
                return results
            
        logging.warning("No site returned results, either nothing found or all sites down... :(")
        return []

    @staticmethod
    def _make_request(url, retries=3, timeout=5):
        for retry in range(retries):
            try:
                ret = requests.post(url, timeout=timeout)
                if ret.status_code == 200:
                    return ret
                else:
                    logging.debug('{} returned status "{}", site problems?'.format(url, ret.status_code))
            except (requests.Timeout, requests.ConnectionError):
                time.sleep(1)
            except Exception as e:
                logging.error(
                    'Caught Exception "{}" while making a get-request to "{}"'.format(e.__class__, url))
                return
        logging.info('Connection to "{}" failed. Site probably down'.format(url))

    @staticmethod
    def _select_search_results(results):
        sorted_results = sorted(results, key=lambda f: f.leechers, reverse=True)
        if not sorted_results:
            return
        if logging.getLogger().level > logging.INFO:
            # quiet mote, select torrent with most leechers (popularity)
            return sorted_results[0]
        else:
            logging.info('ID:    S  |    Size    |     Title')
            for i, result in enumerate(sorted_results):
                result_formatted = '{r.seeders:4} | {r.size:>10} | {r.title}'.format(r=result)
                logging.info('{:2}:  {}'.format(i, result_formatted.replace(u'\xa0', u' ')))    #Replace &nbsp;
            indices = re.split(r'\D', input('Select Torrent to download: '))
            selected_results = []
            for index in indices:
                if not index.isdigit() or int(index) < 0 or int(index) >= len(results):
                    logging.warning('Selected nothing, exiting...')
                    continue
                selected_results.append(sorted_results[int(index)])
            return selected_results
