#!/usr/bin/env python3
import os
import logging
import asyncio

from premiumizeme.api import PremiumizeMeAPI
from torrent_downloader.grabber_piratebay import PirateBayResult, PirateBayTorrentGrabber


class TorrentDownloader:
    def __init__(self, download_directory, auth, event_loop=None):
        self.download_directory = download_directory

        self.grabber = PirateBayTorrentGrabber()
        self.premiumize_me_api = PremiumizeMeAPI(auth, event_loop=event_loop)

    async def download(self, search, type_=None):
        if search.startswith('http') or search.startswith('magnet:?'):
            torrents = [PirateBayResult(None)]
            torrents[0].magnet = search
        else:
            torrents = self.grabber.get_torrents(search, type_=type_)
        if not torrents:
            return

        tasks = asyncio.gather(*[self._download_torrent(torrent) for torrent in torrents])
        await tasks

    async def _download_torrent(self, torrent):
        logging.info('Uploading torrent {}...'.format(torrent.title))
        transfer = await self.premiumize_me_api.upload(torrent)
        if not transfer:
            return

        logging.info('Downloading {}...'.format(transfer.name))
        success = await self.premiumize_me_api.download_transfer(transfer, self.download_directory)
        if success:
            logging.info('Success! Deleting torrent...')
            await self.premiumize_me_api.delete(transfer)
            return success
        logging.error('Error! Could not download torrent, was {}'.format(success))


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
    argparser.add_argument('-t', '--type', type=str,
                           help="Either video, show, movie, porn, audio, game")
    argparser.add_argument('-q', '--quiet', action='store_true')
    argparser.add_argument('-v', '--verbose', action='store_true')

    args = argparser.parse_args()

    logging.basicConfig(format='%(message)s',
                        level=logging.WARN if args.quiet else logging.DEBUG if args.verbose else logging.INFO)

    event_loop_ = asyncio.get_event_loop()
    td = TorrentDownloader(args.download_directory, args.auth, event_loop_)
    try:
        event_loop_.run_until_complete(td.download(args.search, type_=args.type))
    except KeyboardInterrupt:
        pass
    finally:
        event_loop_.run_until_complete(td.premiumize_me_api.close())
