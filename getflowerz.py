#!/usr/bin/env python3

import argparse, cgi, getpass, os, re, sys
import requests # pip3 install requests

DOMAIN = 'https://app.bloomz.net/'
LOGIN_URI = DOMAIN + 'api/user/login?authType=bloomz'
DOWNLOAD_URI = DOMAIN + 'download/'

def parse_response(request):
    request.raise_for_status()
    j = request.json()
    if j['status'] != 'success':
        raise RuntimeError('API call failed: ' + j['status'])
    return j['data']

def dologin(session, username, password):
    r = session.get(DOMAIN)
    r.raise_for_status()
    session.headers['X-Xsrftoken'] = r.cookies['_xsrf']

    j = {'username': username, 'password': password}
    r = session.post(LOGIN_URI, json=j)
    return parse_response(r)

def dorequest(session, url, params=None):
    lastid = None
    r = session.get(url, params=params)
    return parse_response(r)

def itercollection(session, url):
    lastid = None
    while True:
        j = dorequest(session, url, params={'id': lastid})
        l = j['collection']
        if l == []:
            return
        yield from l
        lastid = l[-1]['id']

def lsalbums(session, myid):
    res = dorequest(session, DOMAIN + 'api/' + myid + '/albums')
    fmt = '%-36s %-15s %s'
    print(fmt % ('Album ID', 'Group', 'Description'))
    print(fmt % ('-'*36, '-'*15, '-'*15))

    for a in res['collection']:
        try:
            extrainfo = ' (%d pictures)' % a['numPictures']
        except KeyError:
            extrainfo = ''
        print(fmt % (a['id'], a['albumGroupCategory'], a['title'] + extrainfo))

def dlphoto(session, guid, dirname=None):
    r = session.get(DOWNLOAD_URI + guid)
    r.raise_for_status()
    _, params = cgi.parse_header(r.headers['Content-Disposition'])
    filename = params['filename']

    if dirname:
        filename = os.path.join(dirname, filename)

    if os.path.exists(filename):
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

    with open(filename, 'wb') as fh:
        fh.write(r.content)

def dlalbum(session, albumid, dirname=None):
    for p in itercollection(session, DOMAIN + 'api/v2/'+albumid+'/photos'):
        dlphoto(session, p['id'], dirname)

def parseargs():
    p = argparse.ArgumentParser(description='Download tool for photo albums on Bloomz')
    p.add_argument('-u', '--username', metavar='USER', dest='username',
                   required=True, help='Username')
    p.add_argument('-p', '--password', metavar='PASS', dest='password',
                   help='Password (default: prompt)')
    p.add_argument('-o', '--outdir', metavar='DIR', dest='outdir',
                   help='Directory to write images (default: CWD)')
    p.add_argument('albumid', metavar='ID', nargs='*',
                   help='album(s) to download; if none, a listing is printed')
    return p.parse_args()

def main():
    args = parseargs()
    if not args.password:
        args.password = getpass.getpass()

    with requests.Session() as sess:
        loginres = dologin(sess, args.username, args.password)
        if args.albumid:
            for a in args.albumid:
                dlalbum(sess, a, args.outdir)
        else:
            myid = loginres['profile']['id']
            lsalbums(sess, myid)

if __name__ == '__main__':
    main()
