#!/usr/bin/env python3
"""Simple HTTP server for the Deutsch Lernen web app."""

import http.server
import os
import webbrowser
import threading

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def main():
    os.chdir(DIRECTORY)
    with http.server.HTTPServer(('', PORT), Handler) as httpd:
        url = f'http://localhost:{PORT}/web/'
        print(f'Serving Deutsch Lernen at {url}')
        print('Press Ctrl+C to stop.')
        threading.Timer(1, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')


if __name__ == '__main__':
    main()
