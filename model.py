import csv,io,json,re,math
from pathlib import Path
from collections import Counter
CAT=json.loads(Path(__file__).with_name('attributes.json').read_text())
TYPES=['INSTRUCTION','INPUT','RECORDING','IMAGE','IMAGES','VIDEO','HANDWRITING','VOIP','GUI','EMBODIED_VIDEO']
def dictionary(t):
 g=CAT['groups'];return {**{k:g['COMMON'][k] for k in CAT['commonByType'][t]},**g.get(CAT['inherits'].get(t),{}),**g.get(t,{})}
def must(ok,msg):
 if not ok:raise ValueError(msg)
def text(x):return isinstance(x,str) and bool(x.strip())
def integer(x,a,b):return type(x)==int and a<=x<=b
def validforms(items):
 must(isinstance(items,list),'表单必须是数组');ds=set();ns=set()
 for x in items:
  must(isinstance(x,dict) and text(x.get('desc')) and x['desc'] not in ds and text(x.get('name')) and x['name'] not in ns,'表单 name、desc 必填且各自唯一');ds.add(x['desc']);ns.add(x['name']);t=x.get('type');must(t in ['string','str','int','integer','float','bool','boolean','radio','checkbox','list','dropdown','radio_cascader','checkbox_cascader'],'无效的表单控件');must(type(x.get('required',True))==bool,'必填开关必须为布尔值');
  if t in ('radio','checkbox','list','dropdown'):must(isinstance(x.get('values'),list) and len(x['values']) and all(map(text,x['values'])),'选择控件至少需要一个非空选项')
  if str(t).endswith('cascader'):must(isinstance(x.get('cascader'),list) and len(x['cascader']),'级联选项不能为空')
def csv_columns(static, questions):
 if not static:return ['Name','Prompt Type','Theme Name','Priority','Total Quantity','LimitQuantity','Content','Attributes','Inputs']
 columns=['Script Name','Prompt Type','Name','Content','Attributes','Inputs']
 for key,column in [('pin','Pin'),('check','Data Check Flag')]:
  if any(r.get(key) for r in questions):columns.append(column)
 return columns

def compact_json(value):
 return json.dumps(value,ensure_ascii=False,separators=(',',':'))

def question_row(r,static,first):
 row={'Name':r['name'],'Prompt Type':r['type'],'Content':r['content'],'Attributes':compact_json(r['attrs']),
      'Inputs':compact_json(r['inputs']) if r['type']=='INPUT' else ''}
 if static:
  row.update({'Script Name':r['group'],'Pin':r.get('pin','').strip() if first else '','Data Check Flag':r.get('check','')})
 else:
  row.update({'Theme Name':r['group'],'Priority':r['priority'],'Total Quantity':r['total'],'LimitQuantity':r['limit']})
 return row

def csv_record(values):
 out=io.StringIO(newline='');csv.writer(out).writerow(values);return out.getvalue()

def question_csv(d):
 questions=d['questions'];i=d['index'];mode=d['mode']
 must(mode in ['STATIC','DYNAMIC'] and isinstance(questions,list) and integer(i,0,len(questions)-1),'无效的题目位置或模式')
 r=questions[i];static=mode=='STATIC';first=not any(x['group']==r['group'] for x in questions[:i])
 headers=csv_columns(static,questions);row=question_row(r,static,first)
 # A second dummy cell makes even a single empty cell follow multi-column CSV quoting.
 cells={k:{'text':'' if row[k] is None else str(row[k]),'raw':csv_record([row[k],'x'])[:-4]} for k in headers}
 parts={}
 def member(path,key,val):
  parts[path+'.'+key]=compact_json(key)+':'+compact_json(val)
 def form_fields(path,items):
  if isinstance(items,list):
   for n,item in enumerate(items):
    if isinstance(item,dict):
     for k,v in item.items():member(path+'.'+str(n),k,v)
 for k,v in r['attrs'].items():member('attrs',k,v)
 form_fields('attrs.forms',r['attrs'].get('forms'))
 if r['type']=='INPUT':form_fields('inputs',r['inputs'])
 return {'headers':headers,'cells':cells,'parts':parts,'first':first,
         'header':csv_record(headers)[:-2],'row':csv_record(row[k] for k in headers)[:-2]}

def prepare(c,*,data_only=False):
 must(isinstance(c,dict),'配置格式错误');p=c['project'];m=c['mode'];new=not data_only and c['target']=='new';must(c['target'] in ['new','existing'] and m in ['STATIC','DYNAMIC'],'请选择目标与数据类型');must(data_only or re.fullmatch(r'A\d+',p),'项目编号格式为 A 加数字');must(c.get('action') in ['import','generate','publish'],'执行范围无效');gen=m=='DYNAMIC' and c['action']!='import';s=m=='STATIC';must(not(s and c['action']=='generate'),'静态流程不需要抽题生成');j=c['job'];b=c['batch'];q=c['questions'];must(0<len(q)<=2000,'题目数应为 1–2000');must(data_only or new or re.fullmatch(re.escape(p)+r'-W\d+',c['flow']), '已有流程号须属于所填项目，例如 A7868-W7776');
 if new:
  must(text(c['name']) and len(c['name'])<=50 and text(j['name']) and len(j['name'])<=50 and text(j['desc']),'新流程名称、节点名称和介绍必填，名称最多50字');must(c['category'] in ['VOICE_RECORDING','TTS_EVALUATION','IMAGE_COLLECTION','VIDEO_COLLECTION','EMBODIED_AI_COLLECTION'],'业务分类错误');must(j['team'] in ['PRIVATE','PUBLIC','BPO_COMPANY','SELF_CROWD'],'作业团队错误');must(not(j['team']=='SELF_CROWD' and c['action']=='publish'),'自营团队的发布由接单团队处理');
  if j['team']=='SELF_CROWD':must(re.fullmatch(r'[0-9A-Za-z-]+',j['demand']),'须填已接受的自营需求单 ID')
  else:
   must(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',j['email']) and len(j['email'])<=36,'须填有效的租户 PM 联系邮箱');must(j['payment'] in ['BY_COUNT','BY_TIME','BY_QUESTION','BY_QUESTION_TYPE'],'计费方式无效');
   if j['payment']=='BY_QUESTION_TYPE':
    rates=j['rates'];must(isinstance(rates,list) and rates and all(type(x.get('rate')) in (float,int) and 0<=x['rate']<=5000 for x in rates) and Counter(t for x in rates for t in x['promptTypes'])==Counter(TYPES),'分档计价须覆盖所有10种题型各一次，单价为0–5000')
   else:must(j['rate'] is not None and type(j['rate']) in (float,int) and 0<=j['rate']<=5000 and round(j['rate'],3)==j['rate'],'须明确单价，0–5000，最多三位小数')
   if j['team']=='BPO_COMPANY':must(text(j.get('bpo')),'须填供应商 ID')
  must(j['acquire'] in ['RANDOM','BY_PIN'] and (j['acquire']!='BY_PIN' or s and j['team']!='SELF_CROWD'),'PIN 只适用于非自营静态流程');
 if s:must(integer(b['total'],1,5000) and (b['limit']==-1 or integer(b['limit'],1,5000)) and integer(b['skip'],0,5000),'静态总量或领取/跳过上限超出范围')
 headers=csv_columns(s,q)
 buf=io.StringIO(newline='');buf.write(csv_record(headers));seen=set();pins={};themes={};warn=[]
 for i,r in enumerate(q,1):
  pref=f'第 {i} 题：';t=r['type'];g=r['group'];n=r['name'];a=r['attrs'];must(t in TYPES and text(g) and text(n) and text(r['content']),pref+'分组、题名、题面与题型必填');must(not s or len(g)<=36,pref+'脚本名最多36字');key=(g,n) if s else n;must(key not in seen,pref+'题名重复');seen.add(key);must(isinstance(a,dict),pref+'Attributes 须为对象');defs=dictionary(t)
  for k,v in a.items():
   must(k in defs,pref+'未收录或不适用的属性 '+k);f=defs[k];tt=f['kind'];must({'bool':type(v)==bool,'number':type(v) in (int,float) and math.isfinite(v),'string':isinstance(v,str),'array':isinstance(v,list),'object':isinstance(v,dict)}[tt],pref+k+' 类型不正确');must(not f['choices'] or str(v) in f['choices'],pref+k+' 超出允许选项');
  if t in ['GUI','EMBODIED_VIDEO']:must(text(a.get('query')),pref+'专用采集端需要任务指令 query')
  if t=='EMBODIED_VIDEO':
   steps=a.get('steps');must(isinstance(steps,list) and len(steps)>0,pref+'具身视频至少需要一个执行步骤（Attributes.steps）')
   for step_no,step in enumerate(steps,1):
    k=pref+f'执行步骤 {step_no}：';must(isinstance(step,dict) and text(step.get('name')),k+'请填写步骤名称 name');d=step.get('durationSec');must(type(d) in (float,int) and math.isfinite(d) and d>0,k+'录制时长 durationSec 必须大于 0 秒');must(text(step.get('voicePrompt')),k+'请填写语音提示 voicePrompt')
  if t=='INPUT':must(r['inputs'],pref+'至少增加一个表单项');validforms(r['inputs'])
  else:must(not r['inputs'],pref+'仅 INPUT 使用 Inputs')
  if 'forms' in a:must(t not in ['INPUT','INSTRUCTION'],pref+'该题型不支持附加表单');validforms(a['forms'])
  if t in ['INPUT','INSTRUCTION']:must(not a.get('withTranscription'),pref+'该题型没有转写入口')
  if 'defaultTranscription' in a:must(t=='RECORDING' and a.get('withTranscription') and a.get('txType','text')=='text',pref+'预填转写只适用于已启用文本转写的录音题')
  if a.get('txType') in ['radio','dropdown','checkbox']:must(a.get('withTranscription') and a.get('txValues') and all(map(text,a['txValues'])),pref+'选择式转写必须启用转写并填写选项')
  for lo,hi in [('audioMinDuration','audioMaxDuration'),('videoMinDuration','videoMaxDuration'),('fileMinSize','fileMaxSize'),('minPeakLimit','maxPeakLimit')]:
   if lo in a and hi in a:must(a[lo]<=a[hi],pref+lo+' 不能大于 '+hi)
  if t=='VOIP':
   if 'connectLimit' in a:must(integer(a['connectLimit'],2,10),pref+'声网房间人数为2–10的整数');
   if a.get('voipChannel','agora')=='agora':must(a.get('cloudRecording',True) or a.get('individualRecording',False),pref+'声网混音与分轨不能同时关闭')
   if any(k in a for k in ['aecEnable','ansEnable','agcEnable','audioScenario','channelProfile','speakerphoneEnable','forcePhoneMic']):must(a.get('connectLimit',2)==2 and a.get('voipChannel','agora')=='agora',pref+'此音频配置仅适用于声网双人通话')
  if a.get('enableAIGenerate'):warn.append(pref+'GUI 智能生成可能产生额外费用。')
  if t in ['GUI','EMBODIED_VIDEO']:warn.append(pref+'需在对应专用采集端验证。')
  if a.get('defaultTranscription') is not None and a.get('transcriptionResult'):warn.append(pref+'预填文本与朗读比对并用时不能核验实际发音。')
  first=g not in pins
  if s:
   pin=r.get('pin','').strip();must(not pin or len(pin)==6,pref+'PIN 必须正好6字符');must(not(pin and g in pins and pins[g]!=pin),pref+'PIN 只在脚本首行填写');pins.setdefault(g,pin);must(r.get('check','') in ('','true','false'),pref+'图片检查标记错误')
  else:
   must(integer(r['priority'],0,2147483647) and integer(r['total'],1,9999) and (r['limit'] is None or integer(r['limit'],1,9999)),pref+'优先级、总次数或单份上限错误');themes.setdefault(g,[]).append(r)
  data=question_row(r,s,first);buf.write(csv_record(data[k] for k in headers))
 if new and j.get('nodeLimit') == -1:raise ValueError('创建节点时个人领取上限请留空（不限）或填写正整数')
 if s:
  vals=[v for v in pins.values() if v];must(len(vals)==len(set(vals)),'不同脚本的 PIN 不能重复');
  if new and j['acquire']=='BY_PIN':must(all(pins.values()),'按 PIN 领取时，每个脚本首行都需要 PIN')
 if new and j.get('gui'):must(all(r['type']=='GUI' for r in q),'GUI 业务标签只能上传 GUI 题目')
 if gen:
  rules=b['rules'];must(integer(b['copies'],1,2000) and integer(b['skip'],0,999999) and isinstance(rules,list) and rules,'生成需要份数、跳过数及主题规则');must(len(set(v['theme'] for v in rules))==len(rules),'抽题主题不能重复');
  for v in rules:
   g=v['theme'];k=v['quantity'];must(g in themes and integer(k,1,1000),'抽题主题须来自本次 CSV，数量 1–1000');must(sum(min(r['total'],b['copies']*(r['limit'] or k)) for r in themes[g])>=k*b['copies'],'本次导入的主题可抽余量不足：'+g)
  must(sum(v['quantity'] for v in rules)<=1000,'单份不能超过1000题')
 return buf.getvalue(),warn
