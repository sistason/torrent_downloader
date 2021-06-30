import logging
import click
import asyncio
import os

from torrent_downloader.download import TorrentDownloader


def argcheck_dir(ctx, params, string):
    if os.path.exists(string):
        if os.path.isdir(string) and os.access(string, os.W_OK) and os.access(string, os.R_OK):
            return os.path.abspath(string)
    else:
        base_dir = os.path.dirname(string)
        if os.access(base_dir, os.W_OK) and os.access(base_dir, os.R_OK):
            os.makedirs(string, exist_ok=True)
            return os.path.abspath(string)

    raise click.BadParameter('{} is no directory or isn\'t writeable'.format(string))


@click.command()
@click.argument("search_string", nargs=-1)
@click.option("-v", "--verbose", is_flag=True)
@click.option("-q", "--quiet", is_flag=True)
@click.option("-d", "--download_directory", default=".", callback=argcheck_dir,
              help="Where to download? Default: Current folder")
@click.option("-a", "--auth", help="Either 'user:password' or a path to a pw-file with that format (for premiumize.me)")
@click.option("-t", "--type", default=None,
              type=click.Choice(["video", "show", "movie", "porn", "audio", "game"], case_sensitive=False))
def cli(search_string, download_directory, verbose, quiet, auth, type):
    """Search and download from piratebay via premiumize.me"""
    logging.basicConfig(format='%(message)s',
                        level=logging.WARN if quiet else logging.DEBUG if verbose else logging.INFO)

    search_string = ' '.join(search_string)
    event_loop_ = asyncio.get_event_loop()
    td = TorrentDownloader(download_directory, auth, event_loop_)
    try:
        event_loop_.run_until_complete(td.download(search_string, type_=type))
    except KeyboardInterrupt:
        pass
    finally:
        event_loop_.run_until_complete(td.premiumize_me_api.close())


if __name__ == '__main__':
    cli()