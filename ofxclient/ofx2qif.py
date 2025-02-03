from ofxparse import OfxParser
from collections import OrderedDict
from pprint import pprint
import datetime
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
)

# See this: https://en.wikipedia.org/wiki/Quicken_Interchange_Format
def ofxToQif(ofxFile,accountName="",accountType=""):
    with open(ofxFile) as f:
        ofx = OfxParser.parse(f)
    if accountName:
        outStr=['''!Account\nN{}\nT{}\n^\n!Type:{}'''.format(accountName,accountType,accountType)]
    else:
        outStr=['!Type:Bank']
    transDict = OrderedDict([('date','D'),('tradeDate','D'),('amount','T'),('total','T'),('checknum','N'),('memo','M'),('payee','P'),
                             ('type','N'),('unit_price','I'),('units','Q')])
    n = 0
    logging.info('Found %d accounts',len(ofx.accounts))
    if hasattr(ofx, 'security_list'): logging.info("Securities %s", ofx.security_list[0].name)
    for account in ofx.accounts:
        if hasattr(account,'brokerid'): logging.info("Broker ID %s",account.brokerid)
        for tr in account.statement.transactions:
            print('    '+tr.type)
            if hasattr(tr,'income_type'): print('    '+tr.income_type)
            for key,val in transDict.items():
                if not key in vars(tr): continue
                value = vars(tr)[key]
                if isinstance(value,datetime.datetime): value=value.strftime("%m/%d/%Y")
                if val=='N':
                    if tr.type=='reinvest' and tr.income_type == 'DIV': value = 'ReinvDiv'
                    if tr.type=='reinvest' and tr.income_type == 'CGSHORT': value = 'ReinvSh'
                    if tr.type=='reinvest' and tr.income_type == 'CGLONG': value = 'ReinvLg'
                    if tr.type=='reinvest' and tr.income_type == 'CGMID': value = 'ReinvMd'
                    if tr.type=='buymf': value = 'BuyX'
                    if tr.type=='sellmf': value = 'SellX'
                outStr.append('{}{}'.format(val,value))
            n+=1
            outStr.append('^')
    outFile = ofxFile.replace('.ofx','.qif')
    #print('\n'.join(outStr))
    with open(outFile,'w') as f:
        f.write('\n'.join(outStr))
    logging.info("%d transactions written",n)


def printOfx(filename,onlyPositions=0):
    from pprint import pprint
    if isinstance(filename,str):
        with open(filename) as f:
            ofx = OfxParser.parse(f)
    else:
        ofx = OfxParser.parse(filename)
    acctId2name = {"58086120":"Audience rollover","41479581":"Creative rollover","25738055":"Roth IRA","72781273":"Trust"}
    secId2name = {
        "921908877": "VGSLX",
        "921946786": "VHYAX",
        "922906300": "VMFXX",
        "922021407": "VCAIX",
        "921909305": "VSCGX",
        "921909818": "VTIAX",
        "921943304": "VTMFX",
        "921913208": "VGIAX",
        "92202E888": "VTHRX",
        "92202E805": "VTWNX",
        "92202E508": "VTTHX",
    }
    # print(vars(ofx.account))
    for account in ofx.accounts:
        inst = getattr(account,'brokerd',getattr(account.institution,'organization',"No name"))
        name = acctId2name.get(account.account_id,account.account_id)
        if "28740911" == account.account_id and onlyPositions: continue
        print("Account: {} {} {}".format(name,account.account_type,inst))
        if account.type == 1 and not onlyPositions:
            for tr in account.statement.transactions:
                print("       * {} {} {} {}".format(tr.date,tr.amount,tr.memo,tr.id))
        if account.type == 3:
            for tr in account.statement.transactions:
                if onlyPositions: continue
                try:
                    print("       * {} {} {} {} @ ${}".format(tr.settleDate if tr.settleDate else tr.tradeDate,tr.total,tr.type,tr.units,tr.unit_price))
                except:
                    print("       * {} {} {}".format(tr.date, tr.amount, tr.memo))
            print("    Positions:")
            tot = 0
            for pos in account.statement.positions:
                name = secId2name.get(pos.security, pos.security)
                print("       * {} {} ${} {} @ ${}".format(pos.date,name,pos.market_value,pos.units,pos.unit_price))
                tot += pos.market_value
            print("       * TOTAL: ${}".format(tot))

        if not onlyPositions: print('    {} transactions'.format(len(account.statement.transactions)))
        try:
            if not hasattr(account.statement,'end_date'): account.statement.end_date = 'No Date'
            print("    Cash {} as of {}".format(account.statement.available_cash,str(account.statement.end_date)))
        except:
            pass
        try:
            if not onlyPositions:
                print("    Market Value {} as of {}".format(account.statement.positions[-1].market_value,str(account.statement.positions[-1].date)))
        except:
            pass
        try:
            print("    Balance {} as of {}".format(account.statement.balance,str(account.statement.balance_date)))
        except:
            pass

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser('ofx2qif', description='Convert ofx file to qif for Quicken.',
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inputFile', help='Input OFX file')
    args = parser.parse_args()
    printOfx(args.inputFile)
    #ofxToQif(args.inputFile, accountName="", accountType="")

