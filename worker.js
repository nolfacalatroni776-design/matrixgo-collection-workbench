importScripts('runtime/pyodide.js');
const ready=(async()=>{const root=new URL('.',self.location.href), py=await loadPyodide({indexURL:new URL('runtime/',root).href});for(const f of ['model.py','attributes.json']){const r=await fetch(new URL(f,root));if(!r.ok)throw Error('无法加载配置规则');py.FS.writeFile('/home/pyodide/'+f,await r.text())}py.runPython(`from model import question_csv, prepare
import json
def handle(path, payload):
 d=json.loads(payload)
 if path=='/question-csv': return json.dumps(question_csv(d))
 c=d['config'];c['action']='generate' if path=='/theme-plan' else 'import'
 csv,w=prepare(c,data_only=True);b=c['batch']
 if path=='/theme-plan':return json.dumps(dict(totalQuantity=b['copies'],skipQuantity=b['skip'],rules=b['rules']))
 return json.dumps(dict(csv=csv,warnings=w,steps=['下载 CSV 或将草稿交给本机配置台','用本人账号核对所选环境的目标并确认导入']))`);return py.globals.get('handle')})();
onmessage=async({data:{id,path,body}})=>{try{const handle=await ready;postMessage({id,value:JSON.parse(handle(path,JSON.stringify(body)))})}catch(e){postMessage({id,error:(String(e).trim().split('\n').at(-1)||'校验失败').replace(/^ValueError: /,'')})}};
