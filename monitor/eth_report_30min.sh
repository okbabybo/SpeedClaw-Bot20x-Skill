#!/bin/bash
STATE_FILE="/root/.openclaw/workspace/monitor/last_30min_report.json"

if [ -f "$STATE_FILE" ]; then
    LAST=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('last_epoch',0))" 2>/dev/null)
    [ $(( $(date +%s) - LAST )) -lt 1700 ] && exit 0
fi

E=$(curl -s "https://www.okx.com/api/v5/market/ticker?instId=ETH-USDT-SWAP" 2>/dev/null)
B=$(curl -s "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP" 2>/dev/null)
[ -z "$E" ] || [ -z "$B" ] && exit 1

python3 -c "
import json, datetime, requests

eth = json.loads('$E')['data'][0]
btc = json.loads('$B')['data'][0]

el = float(eth['last']); eh = float(eth['high24h']); elw = float(eth['low24h']); eo = float(eth['open24h'])
bl = float(btc['last']); bh = float(btc['high24h']); blw = float(btc['low24h']); bo = float(btc['open24h'])
ec = f'{(el-eo)/eo*100:+.2f}'; bc = f'{(bl-bo)/bo*100:+.2f}'
now = datetime.datetime.now().strftime('%H:%M')

card = {
    'config': {'wide_screen_mode': True},
    'elements': [
        {'tag': 'div', 'text': f'🦞 ETH实时行情 | {now} GMT+8'},
        {'tag': 'table', 'columns': [{'title':'项目'},{'title':'ETH-USDT'},{'title':'BTC-USDT'}],
         'elements': [
             {'tag':'tr','cells':[{'tag':'td','text':'当前价格'},{'tag':'td','text':f'\${el:.2f}'},{'tag':'td','text':f'\${bl:.2f}'}]},
             {'tag':'tr','cells':[{'tag':'td','text':'24h涨跌'},{'tag':'td','text':f'{ec}%'},{'tag':'td','text':f'{bc}%'}]},
             {'tag':'tr','cells':[{'tag':'td','text':'24h高'},{'tag':'td','text':f'\${eh:.2f}'},{'tag':'td','text':f'\${bh:.2f}'}]},
             {'tag':'tr','cells':[{'tag':'td','text':'24h低'},{'tag':'td','text':f'\${elw:.2f}'},{'tag':'td','text':f'\${blw:.2f}'}]}
         ]},
        {'tag': 'hr'},
        {'tag': 'div', 'text': '📊 关键价位'},
        {'tag': 'table', 'columns': [{'title':'类型'},{'title':'价格'},{'title':'意义'}],
         'elements': [
             {'tag':'tr','cells':[{'tag':'td','text':'压力'},{'tag':'td','text':f'\$2005 / \${eh:.0f}'},{'tag':'td','text':'突破才能转多'}]},
             {'tag':'tr','cells':[{'tag':'td','text':'当前位置'},{'tag':'td','text':f'\${el:.0f}'},{'tag':'td','text':'空头主导'}]},
             {'tag':'tr','cells':[{'tag':'td','text':'支撑'},{'tag':'td','text':f'\${elw:.0f} / \$1930'},{'tag':'td','text':'强撑/中期支撑'}]}
         ]},
        {'tag': 'hr'},
        {'tag': 'div', 'text': '📐 多空方向 + 建仓价位'},
        {'tag': 'table', 'columns': [{'title':'方向'},{'title':'入场'},{'title':'止损'},{'title':'目标'},{'title':'时效'}],
         'elements': [
             {'tag':'tr','cells':[{'tag':'td','text':'👎 SHORT'},{'tag':'td','text':'\$1998-2000'},{'tag':'td','text':'\$2005'},{'tag':'td','text':'\$1980→\$1962'},{'tag':'td','text':'今晚4h'}]},
             {'tag':'tr','cells':[{'tag':'td','text':'🟢 LONG'},{'tag':'td','text':'\$2005站稳'},{'tag':'td','text':'\$1995'},{'tag':'td','text':f'\$2020→\${eh:.0f}'},{'tag':'td','text':'明日'}]}
         ]}
    ]
}

resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id':'cli_a937a37e16b85cc7','app_secret':'82d0j94AKv3QpHISQXT79gAGnJVfYOfX'})
token = resp.json().get('tenant_access_token','')

if token:
    r = requests.post('https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id',
        headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},
        json={'receive_id':'ou_ce5a94cfca07b266414b003138b8f1f8','msg_type':'interactive','content':json.dumps(card)})
    if r.json().get('code') == 0:
        print(f'OK {now}')

json.dump({'last_epoch':int(datetime.datetime.now().timestamp()),'eth':str(el),'btc':str(bl)},
    open('/root/.openclaw/workspace/monitor/last_30min_report.json','w'))
"
