from __future__ import absolute_import
from __future__ import unicode_literals
try:
    # python 3
    from io import StringIO
except ImportError:
    # python 2
    from StringIO import StringIO

from ofxclient.client import Client
from multiprocessing import Pool
import time


def do_download(a_days):
    a,days = a_days
    ofx = a.download(days=days).read()
    stripped = ofx.partition('<OFX>')[2].partition('</OFX>')[0]
    return stripped


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

    pool = Pool(12)
    print("Starting at {}".format(time.asctime()))
    t_start = time.time()

    if not do_parallel:
        print("Downloading")
        for a in accounts:
            print('    {} from {} {}'.format(a.description, a.institution.org,
                                             a.broker_id if hasattr(a, 'broker_id') else ''))
            ofx = a.download(days=days).read()
            stripped = ofx.partition('<OFX>')[2].partition('</OFX>')[0]
            out_file.write(stripped)
    else:
        print("Downloading in parallel")
        for a in accounts:
            print('    {} from {} {}'.format(a.description,a.institution.org,a.broker_id if hasattr(a,'broker_id') else ''))
        res = pool.map_async(do_download,zip(accounts,[days]*len(accounts)))
        while not res.ready():
            res.wait(1)
        out_list = res.get()
        stripped = '\n'.join(out_list)
        out_file.write(stripped)
    t_end = time.time()
    print('Done. {:.0f} seconds elapsed...'.format(t_end-t_start))

    out_file.write("</OFX>")
    out_file.seek(0)

    return out_file
