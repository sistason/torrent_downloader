#!/usr/bin/env python3
import os
import bs4
import time
import logging
import asyncio
import requests

from premiumize_me_dl.premiumize_me_api import PremiumizeMeAPI


class TorrentDownloader:
    def __init__(self, download_directory, auth, event_loop=None):
        self.download_directory = download_directory

        self.grabber = PirateBayTorrentGrabber()
        self.premiumize_me_api = PremiumizeMeAPI(auth, event_loop=event_loop)

    async def download(self, search):
        if search.startswith('http') or search.startswith('magnet:?'):
            torrent = PirateBayResult(None)
            torrent.magnet = search
        else:
            torrent = self.grabber.get_torrent(search)
        if not torrent:
            return

        logging.info('Uploading torrent {}...'.format(torrent.title))
        transfer = await self.premiumize_me_api.upload(torrent)
        if not transfer:
            return

        logging.info('Downloading {}...'.format(transfer.name))
        success = await self.premiumize_me_api.download_transfer(transfer, self.download_directory)
        if success:
            logging.info('Success! Deleting torrent...')
            await self.premiumize_me_api.delete(transfer, deep=True)
            return success
        logging.error('Error! Could not download torrent, was {}'.format(success))


class PirateBayResult:
    def __init__(self, beautiful_soup_tag):
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

    def __bool__(self):
        return bool(self.title or self.magnet)


class PirateBayTorrentGrabber:
    url = 'https://thepiratebay.org'

    def get_torrent(self, search):
        results = self._get_search_results(search)
        logging.info('Fount {} torrents, selecting...'.format(len(results)))
        return self._select_search_result(results)

    def _get_search_results(self, search):
        logging.info('Searching piratebay for "{}"'.format(search))
        response = self._make_request(self.url + '/search/{}/0/99/0'.format(search))
        if response:
            bs4_response = bs4.BeautifulSoup(response, "lxml")
            main_table = bs4_response.find('table', attrs={'id': 'searchResult'})
            if main_table:
                return [PirateBayResult(tag) for tag in main_table.find_all('tr')[1:]]
        return []

    @staticmethod
    def _make_request(url):
        for retry in range(3):
            try:
                ret = requests.post(url, timeout=5)
                if ret.status_code == 200:
                    return ret.text
                else:
                    logging.warning('Piratebay returned status "{}", site problems?'.format(ret.status_code))
            except (requests.Timeout, requests.ConnectionError):
                time.sleep(1)
            except Exception as e:
                logging.error(
                    'Caught Exception "{}" while making a get-request to "{}"'.format(e.__class__, url))
                return
        logging.warning('Connection to Piratebay failed. Site down?')

    @staticmethod
    def _select_search_result(results):
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
                logging.info('{:2}:  {}'.format(i, result_formatted))
            index = input('Select Torrent to download: ')
            if not index.isdigit() or int(index) < 0 or int(index) >= len(results):
                logging.warning('Selected nothing, exiting...')
                return
            return sorted_results[int(index)]


if __name__ == '__main__':
    import argparse

    def argcheck_dir(string):
        if os.path.exists(string):
            if os.path.isdir(string) and os.access(string, os.W_OK) and os.access(string, os.R_OK):
                return os.path.abspath(string)
        else:
            base_dir = os.path.dirname(string)
            if os.access(base_dir, os.W_OK) and os.access(base_dir, os.R_OK):
                os.makedirs(string, exist_ok=True)
                return os.path.abspath(string)

        raise argparse.ArgumentTypeError('{} is no directory or isn\'t writeable'.format(string))

    argparser = argparse.ArgumentParser(description="Search and download from piratebay via premiumize.me")
    argparser.add_argument('search', type=str, help='Search string')
    argparser.add_argument('download_directory', type=argcheck_dir, default='.', nargs='?',
                           help='Set the directory to download the file into.')
    argparser.add_argument('-a', '--auth', type=str,
                           help="Either 'user:password' or a path to a pw-file with that format (for premiumize.me)")
    argparser.add_argument('-q', '--quiet', action='store_true')

    args = argparser.parse_args()

    logging.basicConfig(format='%(message)s',
                        level=logging.WARN if args.quiet else logging.INFO)

    event_loop_ = asyncio.get_event_loop()
    td = TorrentDownloader(args.download_directory, args.auth, event_loop_)
    try:
        event_loop_.run_until_complete(td.download(args.search))
    except KeyboardInterrupt:
        pass
    finally:
        event_loop_.run_until_complete(td.premiumize_me_api.close())
