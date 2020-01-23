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
import time
import datetime
import io
import os
import glob
import re
from threading import Thread

def do_download(a,all_results):
    ofx = a.download(days=a.days).read()
    print('->>{} DONE'.format(a.description.strip()))
    all_results[a.ii] = ofx


def combined_download(accounts, days=60, do_parallel=1):
    """Download OFX files and combine them into one

    It expects an 'accounts' list of ofxclient.Account objects
    as well as an optional 'days' specifier which defaults to 60
    set do_parallel to 0 to no download all accounts simultaneously.
    """
    client = Client(institution=None)

    print("Starting at {}".format(time.asctime()))
    t_start = time.time()

    def prune_transactions(ofx_str):
        if not len(ofx_str): return None,ofx_str,0
        f = StringIO(ofx_str)
        ofx = OfxParser.parse(f)
        a = ofx.account
        if a.type == 3:
            return ofx, ofx_str, len(a.statement.transactions)
        days_ago = datetime.datetime.now() - datetime.timedelta(days=days)
        new_transactions = []
        # Some banks (citibank for example) simply ignore the STDATE value and return everything.
        for trans in a.statement.transactions:
            if getattr(trans,'date',datetime.datetime(1900,1,1)) >= days_ago:
                new_transactions.append(trans)
                continue
            if getattr(trans, 'settleDate', datetime.datetime(1900,1,1)) >= days_ago:
                new_transactions.append(trans)
                continue

        a.statement.transactions = new_transactions
        return ofx,None,len(a.statement.transactions)

    def output_account(account,ofx,ofx_str,idx):
        a=ofx.account
        inst = account.description
        p = OfxPrinter(ofx,None)
        balance = 0
        bal_date = ''
        try:
            if not hasattr(a.statement, 'end_date'): a.statement.end_date = 'No Date'
            balance,bal_date = a.statement.available_cash,a.statement.end_date
        except:
            pass
        try:
            balance,bal_date = a.statement.positions[-1].market_value,a.statement.positions[-1].date
        except:
            pass
        try:
            balance, bal_date = a.statement.balance, a.statement.balance_date
        except:
            pass

        outDir = os.getenv('OFX_OUTDIR',os.getenv('HOME','.'))
        if not os.path.exists(outDir): os.mkdir(outDir)
        if idx is None:
            all_files_written = glob.glob(os.path.join(outDir,'*.ofx'))
            all_indices = [re.findall('(\d+)_',os.path.basename(file)) for file in all_files_written]
            all_indices = [int(item[0]) for item in all_indices if len(item)]+[0]
            idx = (max(all_indices)+1)%100
        name = os.path.join(outDir,'{:02d}_'.format(idx)+account.description.replace(' ', '_') + '.ofx')
        for ii in range(1,100):
            prev_idx = (idx-ii+100)%100
            prev_name = os.path.join(outDir,'{:02d}_'.format(prev_idx)+account.description.replace(' ', '_') + '.ofx')
            if os.path.exists(prev_name): break
        else:
            prev_name = ''

        num_new_trans = len(a.statement.transactions)
        if prev_name:
            with open(prev_name) as f:
                prev_ofx = OfxParser.parse(f)
                prev_a = prev_ofx.account
                try:
                    if 0:
                        # This counts new transactions by date.
                        prev_max_date = max([t.date for t in prev_a.statement.transactions])
                        num_new_trans = len([t for t in a.statement.transactions if t.date > prev_max_date])
                    else:
                        # This counts transactions that are in the new one, but not in the previous one.
                        all_new_ids = [t.id for t in a.statement.transactions]
                        all_prev_ids = [t.id for t in prev_a.statement.transactions]
                        num_new_trans = len(set(all_new_ids)-set(all_prev_ids))
                except:
                    num_new_trans = -1
        if num_new_trans == 0:
            return idx

        if ofx_str is None:
            outfile = io.open(name, 'w')
            p.writeToFile(outfile)
            outfile.close()
        else:
            with open(name,'w') as f:
                f.write(ofx_str)

        if hasattr(bal_date,'strftime'): bal_date = bal_date.strftime('%Y-%b-%d')
        print('    {:<25} {:>2}/{}  trans. Bal. {:>10} as of {} -> {}'.format(inst, len(a.statement.transactions), num_new_trans,
                                                                        balance, bal_date, name))
        return idx

    if not do_parallel:
        print("Downloading")
        idx = None
        for a in accounts:
            print('    {}'.format(a.description))
            ofx = a.download(days=days).read()
            ofx,ofx_str,n = prune_transactions(ofx)
            idx=output_account(a,ofx,ofx_str,idx)
    else:
        print("Downloading in parallel")
        out_list = [[]]*len(accounts)
        for ii,a in enumerate(accounts):
            a.days = days
            a.ii = ii
            a.thread = Thread(target=do_download,args=(a,out_list))
            a.thread.start()

        # It would be cleaner to use semaphores here, but this works OK.
        ii=0
        while any([a.thread.is_alive() for a in accounts]):
            time.sleep(1)
            if ii%10==0: print("Waiting for:" + ', '.join([a.description for a in accounts if a.thread.isAlive()]))
            else: print('.',end='')
            ii+=1
        print('\nDone downloading')
        idx = None
        for ii,ofx in enumerate(out_list):
            ofx,ofx_str,n = prune_transactions(ofx,)
            if n != 0:
                idx = output_account(accounts[ii],ofx,ofx_str,idx)
    t_end = time.time()
    print('Done. {:.0f} seconds elapsed...'.format(t_end-t_start))
