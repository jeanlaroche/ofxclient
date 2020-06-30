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
    #print('->>{} DONE'.format(a.description.strip()))
    all_results[a.ii] = ofx

def getTransDate(t):
    return getattr(t,'date',getattr(t,'settleDate',datetime.datetime(1900,1,1)))

def output_account2(account,ofx,ofx_str,idx):
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

    out_dir = os.getenv('OFX_OUTDIR',os.getenv('HOME','.'))
    if not os.path.exists(out_dir): os.mkdir(out_dir)
    if idx is None:
        all_files_written = glob.glob(os.path.join(out_dir,'*.ofx'))
        all_indices = [re.findall('^(\d+)_',os.path.basename(file)) for file in all_files_written]
        all_indices = [int(item[0]) for item in all_indices if len(item)]+[0]
        idx = (max(all_indices)+1)%100
    name = os.path.join(out_dir,'{:02d}_'.format(idx)+account.description.replace(' ', '_') + '.ofx')
    for ii in range(1,100):
        prev_idx = (idx-ii+100)%100
        prev_name = os.path.join(out_dir,'{:02d}_'.format(prev_idx)+account.description.replace(' ', '_') + '.ofx')
        if os.path.exists(prev_name): break
    else:
        prev_name = ''

    num_new_trans = len(a.statement.transactions)
    if prev_name:
        with open(prev_name) as f:
            prev_ofx = OfxParser.parse(f)
            prev_a = prev_ofx.account
            try:
                prev_max_date = max([getTransDate(t) for t in prev_a.statement.transactions])
                # This counts transactions that are in the new one, but not in the previous one and whose date
                # is later than the previous latest date.
                # all_new_ids = [t.id for t in a.statement.transactions if getTransDate(t) > prev_max_date]
                all_new_ids = [t.id for t in a.statement.transactions]
                all_prev_ids = [t.id for t in prev_a.statement.transactions]
                num_new_trans = len(set(all_new_ids)-set(all_prev_ids))
            except:
                num_new_trans = -1
    if num_new_trans <= 0:
        print('    {:<25} No new transactions Bal. {:>10} as of {}'.format(inst,balance, bal_date))
        return idx,0

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
    return idx,num_new_trans

def multi_download(accounts, days=60, do_parallel=1):
    """Download OFX files

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
        try:
            a = ofx.account
        except Exception as e:
            print(e)
            import pdb
            pdb.set_trace()
        if a.type == 3:
            return ofx, ofx_str, len(a.statement.transactions)
        days_ago = datetime.datetime.now() - datetime.timedelta(days=days)
        new_transactions = []
        # Some banks (citibank for example) simply ignore the STDATE value and return everything.
        for trans in a.statement.transactions:
            if getTransDate(trans) >= days_ago:
                new_transactions.append(trans)

        a.statement.transactions = new_transactions
        return ofx,ofx_str,len(a.statement.transactions)

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

        out_dir = os.getenv('OFX_OUTDIR',os.getenv('HOME','.'))
        if not os.path.exists(out_dir): os.mkdir(out_dir)
        if idx is None:
            all_files_written = glob.glob(os.path.join(out_dir,'*.ofx'))
            all_indices = [re.findall('^(\d+)_',os.path.basename(file)) for file in all_files_written]
            all_indices = [int(item[0]) for item in all_indices if len(item)]+[0]
            idx = (max(all_indices)+1)%100
        name = os.path.join(out_dir,'{:02d}_'.format(idx)+account.description.replace(' ', '_') + '.ofx')
        for ii in range(1,100):
            prev_idx = (idx-ii+100)%100
            prev_name = os.path.join(out_dir,'{:02d}_'.format(prev_idx)+account.description.replace(' ', '_') + '.ofx')
            if os.path.exists(prev_name): break
        else:
            prev_name = ''

        num_new_trans = len(a.statement.transactions)
        if prev_name:
            with open(prev_name) as f:
                prev_ofx = OfxParser.parse(f)
                prev_a = prev_ofx.account
                try:
                    prev_max_date = max([getTransDate(t) for t in prev_a.statement.transactions])
                    # This counts transactions that are in the new one, but not in the previous one and whose date
                    # is later than the previous latest date.
                    # all_new_ids = [t.id for t in a.statement.transactions if getTransDate(t) > prev_max_date]
                    all_new_ids = [t.id for t in a.statement.transactions]
                    all_prev_ids = [t.id for t in prev_a.statement.transactions]
                    num_new_trans = len(set(all_new_ids)-set(all_prev_ids))
                except:
                    num_new_trans = -1
        if num_new_trans <= 0:
            print('    {:<25} No new transactions Bal. {:>10} as of {}'.format(inst,balance, bal_date))
            return idx,0

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
        return idx,num_new_trans

    if not do_parallel:
        print("Downloading")
        idx = None
        for a in accounts:
            print('    {}'.format(a.description))
            ofx = a.download(days=days).read()
            ofx,ofx_str,n = prune_transactions(ofx)
            idx,_=output_account(a,ofx,ofx_str,idx)
    else:
        print("Downloading in parallel")
        out_list = [[]]*len(accounts)
        for ii,a in enumerate(accounts):
            a.days = days
            a.ii = ii
            a.thread = Thread(target=do_download,args=(a,out_list),daemon=True)
            a.thread.start()

        # It would be cleaner to use semaphores here, but this works OK.
        ii=0
        idx = None
        all_ofx = []
        while 1:
            for ii,a in enumerate(accounts):
                ofx = out_list[ii]
                if not len(ofx): continue
                ofx,ofx_str,n = prune_transactions(ofx)
                if n != 0:
                    idx,m = output_account(accounts[ii],ofx,ofx_str,idx)
                    if m: all_ofx.append(ofx_str)
                else:
                    print('    {:<25} No new transactions'.format(a.description))
                out_list[ii] = ''
            if all([not a.thread.is_alive() for a in accounts]): break
            time.sleep(1)
    t_end = time.time()
    #combine_ofx(all_ofx,idx)
    print('Done. {:.0f} seconds elapsed...'.format(t_end-t_start))

def combine_ofx(ofx_list,idx):
    if len(ofx_list) < 2: return
    def findOFXTab(ofx_str):
        ofxIdx = []
        sofxIdx = []
        all_lines = ofx_str.split('<')
        out_lines = []
        for ii,line in enumerate(all_lines):
            line='<'+line
            if '<OFX>' in line: ofxIdx.append(ii)
            if '</OFX>' in line: sofxIdx.append(ii)
            out_lines.append(line)
        return ofxIdx,sofxIdx,out_lines
    # Output the first one to the last </OFX> then the next one from <OFX> -> </OFX>
    o,s,lines = findOFXTab(ofx_list[0])
    A = ''.join(lines[0:s[-1]])
    for ofx in ofx_list[1:]:
        o, s, lines = findOFXTab(ofx)
        A += ''.join(lines[o[0]+1:s[-1]])
    A += '</OFX>\n'

    out_dir = os.getenv('OFX_OUTDIR', os.getenv('HOME', '.'))
    name = os.path.join(out_dir, '{:02d}_Combined.ofx'.format(idx))
    with open(name,'w') as f:
        f.write(A)
    print('Wrote {}'.format(name))

def grab_from_tmp(days):
    src_dir = 'E:\\temp'
    if not os.path.exists(src_dir):
        src_dir = os.path.join(os.getenv('HOME',''),'Downloads')
    # Look for "ExportedTransactions"
    print("Grabbing OFX files from temp")
    all_temp_files = glob.glob(os.path.join(src_dir, '*.ofx_done'))
    for file in all_temp_files:
        os.remove(file)
    all_temp_files = glob.glob(os.path.join(src_dir, '*.ofx'))
    all_temp_files += glob.glob(os.path.join(src_dir, '*.qfx'))
    print("Found %d files"%len(all_temp_files))
    out_dir = os.getenv('OFX_OUTDIR', os.getenv('HOME', '.'))
    idx = find_max_idx(out_dir)+1
    # Rename the files according to their account.
    for file in all_temp_files:
        with open(file) as f:
            ofx = OfxParser.parse(f,fail_fast=0)
        if ofx.account.account_id == '*****578679-75': out_name = 'Patelco_Visa'
        elif ofx.account.account_id == '*****578679-10': out_name = 'Patelco_Checking'
        elif ofx.account.account_id == '*****578679-15': out_name = 'Patelco_Money_Market'
        elif ofx.account.account_id == '840210': out_name = 'MassMutual'
        elif ofx.account.account_id == '0234067981': out_name = 'SunTrust'
        elif ofx.account.account_id == '********3009': out_name = 'Barclays'
        elif ofx.account.account_id == '21199293923': out_name = 'Indivision'
        else:
            print("Can't figure out name for file %s"%file)
            exit(0)
        days_ago = datetime.datetime.now() - datetime.timedelta(days=days)
        new_transactions = []
        a = ofx.account
        # Some banks (citibank for example) simply ignore the STDATE value and return everything.
        for trans in a.statement.transactions:
            if getTransDate(trans) >= days_ago:
                new_transactions.append(trans)

        a.statement.transactions = new_transactions
        ofx.description = out_name
        fix_ofx(ofx)
        output_account2(ofx,ofx,None,idx)
        os.rename(file,file+"_done")

    # Move files from src_dir to out_dir
    # os.rename()

def fix_ofx(ofx):
    if not hasattr(ofx,'trnuid'): ofx.trnuid = 0
    if not hasattr(ofx,'status'): ofx.status = ""

def find_max_idx(out_dir):
    # Find max index of all ofx files
    all_files_written = glob.glob(os.path.join(out_dir, '*.ofx'))
    all_indices = [re.findall('^(\d+)_', os.path.basename(file)) for file in all_files_written]
    all_indices = [int(item[0]) for item in all_indices if len(item)] + [0]
    idx = max(all_indices)
    return idx

def renumber_files(files,old,new):
    # Renumber files in files from old->new (e.g. 55_this.ofx -> 25_this.ofx)
    if old == new: return
    for file in files:
        new_file = file.replace('{:02d}'.format(old), '{:02d}'.format(new))
        print("Renaming {} -> {}".format(os.path.basename(file), os.path.basename(new_file)))
        os.rename(file,new_file)

def purge_files():
    # Removes the oldest ofx files to make room for new ones.
    out_dir = os.getenv('OFX_OUTDIR', os.getenv('HOME', '.'))
    if not os.path.exists(out_dir): return
    idx = find_max_idx(out_dir)
    if idx < 90: return
    # Before purging, rename files to remove any gaps in the numbering.
    jj = 0
    for ii in range(idx+1):
        to_rename = glob.glob(os.path.join(out_dir, '{:02d}_*.ofx'.format(ii)))
        if not len(to_rename):
            continue # ii increments but not jj
        if ii==jj:
            jj += 1
            continue
        renumber_files(to_rename,ii,jj)
        jj += 1
    # Did we make enough room to not have to purge?
    idx = find_max_idx(out_dir)
    if idx <= 90: return

    purge = 20
    answer = input('Nearing max number of files, purge the earliest {}? ->[yes/n]'.format(purge))
    if not answer == 'yes': return
    for ii in range(purge):
        to_purge = glob.glob(os.path.join(out_dir, '{:02d}_*.ofx'.format(ii)))
        for file in to_purge:
            print("Removing {}".format(os.path.basename(file)))
            os.remove(file)
    for ii in range(purge,100):
        to_rename = glob.glob(os.path.join(out_dir, '{:02d}_*.ofx'.format(ii)))
        renumber_files(to_rename,ii,ii-purge)



