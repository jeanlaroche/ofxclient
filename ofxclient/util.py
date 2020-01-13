from __future__ import absolute_import
from __future__ import unicode_literals
try:
    # python 3
    from io import StringIO
except ImportError:
    # python 2
    from StringIO import StringIO

from ofxclient.client import Client
from multiprocessing import Pool, Array
import time

# This is used to synchronize the threads during parallel download
done = Array('h',100)
def do_download(a):
    ofx = a.download(days=a.days).read()
    # if len(ofx):
    #     f=StringIO(ofx)
    #     from ofxclient.ofx2qif import printOfx
    #     printOfx(f)
    print('->>{} DONE'.format(a.description.strip()))
    done[a.ii]=1
    return ofx


def combined_download(accounts, days=60, do_parallel=1):
    """Download OFX files and combine them into one

    It expects an 'accounts' list of ofxclient.Account objects
    as well as an optional 'days' specifier which defaults to 60
    set do_parallel to 0 to no download all accounts simultaneously.
    """
    client = Client(institution=None)
    out_file = StringIO()
    out_file.write(client.header())
    out_file.write('<OFX>')

    print("Starting at {}".format(time.asctime()))
    t_start = time.time()

    if not do_parallel:
        print("Downloading")
        for a in accounts:
            print('    {}'.format(a.description))
            ofx = a.download(days=days).read()
            stripped = ofx.partition('<OFX>')[2].partition('</OFX>')[0]
            out_file.write(stripped)
    else:
        pool = Pool(12)
        print("Downloading in parallel")
        for ii,a in enumerate(accounts):
            print('    {}'.format(a.description))
            a.days = days
            a.ii = ii
        res = pool.map_async(do_download,accounts)
        ii=0
        while not res.ready():
            res.wait(1)
            if ii%10==0: print("Waiting for:" + ', '.join([a.description for a in accounts if done[a.ii] == 0]))
            else: print('.',end='')
            ii+=1
        out_list = res.get()
        from ofxclient.ofx2qif import printOfx
        stripped = []
        for ii,ofx in enumerate(out_list):
            if not len(ofx): continue
            f = StringIO(ofx)
            print("Account {}".format(accounts[ii].description))
            printOfx(f)
            stripped.append(ofx.partition('<OFX>')[2].partition('</OFX>')[0])
        stripped = '\n'.join(stripped)
        out_file.write(stripped)
    t_end = time.time()
    print('Done. {:.0f} seconds elapsed...'.format(t_end-t_start))

    out_file.write("</OFX>")
    out_file.seek(0)

    return out_file
