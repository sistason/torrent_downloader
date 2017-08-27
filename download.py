import os
import bs4
import time
import logging
import asyncio
import requests

from premiumize_me_dl.premiumize_me_api import PremiumizeMeAPI


class TorrentDownloader:
    def __init__(self, download_directory, auth):
        self.download_directory = download_directory
        self.event_loop = asyncio.get_event_loop()

        self.grabber = PirateBayTorrentGrabber()
        self.premiumize_me_api = PremiumizeMeAPI(auth, event_loop=self.event_loop)

    async def download(self, search):
        torrent = self.grabber.get_torrent(search)
        if not torrent:
            return

        logging.info('Uploading torrent {}...'.format(torrent.title))
        upload_ = await self.premiumize_me_api.upload(torrent)
        if not upload_:
            return

        transfer = await self._wait_for_torrent(upload_)
        if not transfer:
            return

        await self._download_torrent(transfer)

    async def _wait_for_torrent(self, upload_):
        logging.info('Waiting for premiumize.me to finish downloading the torrent...')
        transfer = None
        while transfer is None or transfer.is_running() and transfer.status != 'error':
            time.sleep(2)
            transfer = await self._get_transfer_status(upload_)
            logging.info('  Status: {}'.format(transfer.status_msg()))
        return transfer

    async def _get_transfer_status(self, upload_):
        transfers = await self.premiumize_me_api.get_transfers()

        for transfer in transfers:
            if transfer.id == upload_.id:
                return transfer

    async def _download_torrent(self, transfer):
        logging.info('Downloading {}...'.format(transfer.name))
        file_ = await self.premiumize_me_api.get_file_from_transfer(transfer)
        if file_:
            success = await self.premiumize_me_api.download_file(file_, self.download_directory)
            if success:
                logging.info('Success! Deleting torrent...')
                await self.premiumize_me_api.delete(file_)
                return success
            logging.error('Error! Could not download torrent, was {}'.format(success))


class PirateBayResult:
    def __init__(self, beautiful_soup_tag):
        self.title = self.magnet = ''
        self.seeders = self.leechers = 0
        try:
            tds = beautiful_soup_tag.find_all('td')
            self.title = tds[1].a.text
            self.magnet = tds[1].find_all('a')[1].attrs.get('href')
            self.seeders = int(tds[-2].text)
            self.leechers = int(tds[-1].text)
        except (IndexError, ValueError, AttributeError):
            return

    def __bool__(self):
        return bool(self.title)


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
                    logging.warning('Piratebay returned status "{}", parser corrupt?'.format(ret.status_code))
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
            logging.info('ID: L  |  S  -     Title')
            for i, result in enumerate(sorted_results):
                result_formatted = 'L{r.leechers:4}|S{r.seeders:4} - {r.title}'.format(r=result)
                logging.info('{:2}: {}'.format(i, result_formatted))
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
    argparser.add_argument('download_directory', type=argcheck_dir, default='.',
                           help='Set the directory to download the file into.')
    argparser.add_argument('-a', '--auth', type=str,
                           help="Either 'user:password' or a path to a pw-file with that format (for premiumize.me)")
    argparser.add_argument('-q', '--quiet', action='store_true')

    args = argparser.parse_args()

    logging.basicConfig(format='%(message)s',
                        level=logging.WARN if args.quiet else logging.INFO)

    td = TorrentDownloader(args.download_directory, args.auth)
    event_loop = asyncio.get_event_loop()
    try:
        td.event_loop.run_until_complete(td.download(args.search))
    except KeyboardInterrupt:
        pass
    finally:
        td.premiumize_me_api.close()
        td.event_loop.close()
