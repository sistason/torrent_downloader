# torrent_downloader
Search and download from piratebay via premiumize.me

## Requirements
- python3
- aiohttp
- aiofiles
- bs4
- requests
- lxml
- http://www.github.com/sistason/premiumize.me.dl

## Usage
`python3 download.py "$search string" /your/download/path [-a auth.txt] [-q]`
- -a auth: See the [premiumize.me.dl-documentation](http://www.github.com/sistason/premiumize.me.dl#usage)
- -q: quiet mode, just download the torrent-result with most leechers
