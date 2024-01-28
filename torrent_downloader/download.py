#!/usr/bin/env python3
import logging
import asyncio
from pathlib import Path

from premiumizeme.api import PremiumizeMeAPI
from torrent_downloader.grabber_piratebay import PirateBayResult, PirateBayTorrentGrabber


class TorrentDownloader:
    def __init__(self, download_directory, auth, event_loop=None):
        self.download_directory = Path(download_directory)

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
