#!/usr/bin/env python3

import argparse, cgi, enum, getpass, os
import requests # pip install requests

DOMAIN = 'https://app.bloomz.net/'
LOGIN_URI = DOMAIN + 'api/user/login?authType=bloomz'
DOWNLOAD_URI = DOMAIN + 'download/'

class DuplicateAction(enum.Enum):
    OVERWRITE = 'overwrite'
    RENAME = 'rename'
    SKIP = 'skip'

    def __str__(self):
        return self.value

class Client:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def parse_response(request):
        request.raise_for_status()
        j = request.json()
        if j['status'] != 'success':
            raise RuntimeError('API call failed: ' + j['status'])
        return j['data']

    def dologin(self, username, password):
        r = self.session.get(DOMAIN)
        r.raise_for_status()
        self.session.headers['X-Xsrftoken'] = r.cookies['_xsrf']

        j = {'username': username, 'password': password}
        r = self.session.post(LOGIN_URI, json=j)
        return self.parse_response(r)

    def dorequest(self, url, params=None):
        r = self.session.get(url, params=params)
        return self.parse_response(r)

    def itercollection(self, url):
        lastid = None
        while True:
            j = self.dorequest(url, params={'id': lastid})
            l = j['collection']
            if l == []:
                return
            yield from l
            lastid = l[-1]['id']

    def lsalbums(self, myid):
        res = self.dorequest(DOMAIN + 'api/' + myid + '/albums')
        fmt = '%-36s %-15s %s'
        print(fmt % ('Album ID', 'Group', 'Description'))
        print(fmt % ('-'*36, '-'*15, '-'*15))

        for a in res['collection']:
            try:
                extrainfo = ' (%d pictures)' % a['numPictures']
            except KeyError:
                extrainfo = ''
            print(fmt % (a['id'], a['albumGroupCategory'], a['title'] + extrainfo))

    def getdetails(self, guid):
        r = self.session.get(DOMAIN + 'api/v3/media/' + guid + '/details')
        r.raise_for_status()
        return r.json()

    @staticmethod
    def mkfilename(args, filename):
        if args.outdir:
            filename = os.path.join(args.outdir, filename)

        if os.path.exists(filename) and args.dups != DuplicateAction.OVERWRITE:
            if args.dups == DuplicateAction.SKIP:
                print(filename, 'exists; skipped')
                return None
            elif args.dups == DuplicateAction.RENAME:
                origname = filename
                root, ext = os.path.splitext(filename)
                def mkname(n):
                    return root + "_" + str(n) + ext
                n = 1
                while os.path.exists(mkname(n)):
                    n += 1
                filename = mkname(n)
                print(origname, 'exists; saving as', filename)
        else:
            print('Saving', filename)

        return filename

    def dlphoto(self, args, guid):
        with self.session.get(DOWNLOAD_URI + guid, stream=True) as r:
            r.raise_for_status()
            _, params = cgi.parse_header(r.headers['Content-Disposition'])
            filename = self.mkfilename(args, params['filename'])
            if filename:
                with open(filename, 'wb') as fh:
                    fh.write(r.content)

    def dlalbum(self, args, albumid):
        for p in self.itercollection(DOMAIN + 'api/v2/'+albumid+'/photos'):
            guid = p['id']
            self.dlphoto(args, guid)

def parseargs():
    p = argparse.ArgumentParser(description='Download tool for photo albums on Bloomz')
    p.add_argument('-u', '--username', metavar='USER', dest='username',
                   required=True, help='Username')
    p.add_argument('-p', '--password', metavar='PASS', dest='password',
                   help='Password (default: prompt)')
    p.add_argument('-o', '--outdir', metavar='DIR', dest='outdir',
                   help='Directory to write images (default: CWD)')
    p.add_argument('--dups', type=DuplicateAction, choices=DuplicateAction,
                   help='What to do with duplicate filenames (default: rename)',
                   default=DuplicateAction.RENAME)
    p.add_argument('albumid', metavar='ID', nargs='*',
                   help='album(s) to download; if none, a listing is printed')
    return p.parse_args()

def main():
    args = parseargs()
    if args.password is None:
        args.password = getpass.getpass()

    with requests.Session() as sess:
        client = Client(sess)
        loginres = client.dologin(args.username, args.password)
        if args.albumid:
            for a in args.albumid:
                client.dlalbum(args, a)
        else:
            myid = loginres['profile']['id']
            client.lsalbums(myid)

if __name__ == '__main__':
    main()
