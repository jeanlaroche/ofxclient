from __future__ import absolute_import
from __future__ import unicode_literals
try:
    # python 3
    from io import StringIO
except ImportError:
    # python 2
    from StringIO import StringIO

from ofxclient.client import Client
from ofxparse import OfxParser, OfxPrinter
from multiprocessing import Pool, Array
import time
import datetime
import io
import os

# This is used to synchronize the threads during parallel download
done = Array('h',100)
def do_download(a):
    ofx = a.download(days=a.days).read()
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

    print("Starting at {}".format(time.asctime()))
    t_start = time.time()

    def output_account(account,ofx_str):
        if not len(ofx_str): return
        f = StringIO(ofx_str)
        ofx = OfxParser.parse(f)
        a=ofx.account
        inst = account.description
        days_ago = datetime.datetime.now() - datetime.timedelta(days=days)
        new_transactions = []
        # Some banks (citibank for example) simply ignore the STDATE value and return everything.
        for trans in a.statement.transactions:
            if trans.date >= days_ago:
                new_transactions.append(trans)
        a.statement.transactions = new_transactions
        p = OfxPrinter(ofx,None)
        num_trans = len(a.statement.transactions)
        if num_trans:
            bal = 0
            bal_date = ''
            try:
                if not hasattr(a.statement, 'end_date'): a.statement.end_date = 'No Date'
                bal,bal_date = a.statement.available_cash,str(a.statement.end_date)
            except:
                pass
            try:
                bal,bal_date = a.statement.positions[-1].market_value,str(a.statement.positions[-1].date)
            except:
                pass
            try:
                bal, bal_date = a.statement.balance, str(a.statement.balance_date)
            except:
                pass
            name = account.description.replace(' ', '_') + '.ofx'
            outfile = io.open(name, 'w')
            p.writeToFile(outfile)
            # outfile.write(ofx_str)
            outfile.close()
            print(' {} {} trans. Balance {} as of {} -> {}'.format(inst,num_trans,bal,bal_date,name))
        else:
            print(' {} {} transactions'.format(inst,num_trans))

    if not do_parallel:
        print("Downloading")
        for a in accounts:
            print('    {}'.format(a.description))
            ofx = a.download(days=days).read()
            output_account(a,ofx)
    else:
        pool = Pool(12)
        print("Downloading in parallel")
        for ii,a in enumerate(accounts):
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
        for ii,ofx in enumerate(out_list):
            output_account(accounts[ii],ofx)
    t_end = time.time()
    print('Done. {:.0f} seconds elapsed...'.format(t_end-t_start))
