"""Development API. Deploy behind HTTPS; no banking provider credentials required."""
import os, json, sqlite3, secrets, hashlib, hmac, time, re, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
DB=os.environ.get('AURORA_DB',str(Path(__file__).with_name('aurora.sqlite3')))
ORIGINS=set(os.environ.get('AURORA_ORIGINS','http://localhost:8081,http://localhost:8080').split(','))
LIMIT=2_000_000
# Shared client forms can retain unused fields, such as target='' on a
# transaction or limit='' on a purchase. Validate money for this record type.
MONEY_FIELDS={
 'accounts':('opening',),
 'transactions':('amount',),
 'goals':('target',),
 'cards':('limit',),
 'purchases':('amount',),
}
lock=threading.Lock(); attempts={}
def connect():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;return c
def initialize():
 with connect() as c:
  c.executescript('CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,salt BLOB NOT NULL,password BLOB NOT NULL); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS states(user_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL);')
def digest(token):return hashlib.sha256(token.encode()).hexdigest()
def password_hash(password,salt):return hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1)
def validate_state(s):
 if not isinstance(s,dict) or s.get('version')!=1:raise ValueError('Versão de dados inválida.')
 for k in ['accounts','transactions','goals','cards','purchases']:
  if not isinstance(s.get(k,[] if k in ('cards','purchases') else None),list) or len(s.get(k,[]))>20000:raise ValueError('Coleção inválida.')
  ids=set()
  for item in s.get(k,[]):
   if not isinstance(item,dict) or not isinstance(item.get('id'),str) or item['id'] in ids:raise ValueError('Identificador inválido/duplicado.')
   ids.add(item['id'])
   for field in MONEY_FIELDS[k]:
    if field in item and (type(item[field]) is not int or abs(item[field])>10**12):raise ValueError('Valor monetário inválido.')
 if not s.get('accounts'):raise ValueError('É necessária pelo menos uma conta.')
 accounts={x['id'] for x in s['accounts']};cards={x['id'] for x in s.get('cards',[])}
 for a in s['accounts']:
  if not isinstance(a.get('name'),str) or type(a.get('opening')) is not int:raise ValueError('Conta inválida.')
 for t in s['transactions']:
  if t.get('type') not in ('income','expense','transfer','card_payment') or t.get('accountId') not in accounts or type(t.get('amount')) is not int or t['amount']<=0 or not isinstance(t.get('description'),str) or not isinstance(t.get('category'),str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(t.get('date',''))):raise ValueError('Transação inválida.')
  if t['type']=='transfer' and (t.get('toAccountId') not in accounts or t['toAccountId']==t['accountId']):raise ValueError('Transferência inválida.')
  if t['type']=='card_payment' and (t.get('cardId') not in cards or not re.fullmatch(r'\d{4}-\d{2}',str(t.get('invoiceMonth','')))):raise ValueError('Fatura inválida.')
 for g in s['goals']:
  if g.get('accountId') not in accounts or not isinstance(g.get('name'),str) or type(g.get('target')) is not int or g['target']<=0:raise ValueError('Meta inválida.')
 for c in s.get('cards',[]):
  if not isinstance(c.get('name'),str) or type(c.get('limit')) is not int or c['limit']<=0 or any(type(c.get(k)) is not int or not 1<=c[k]<=28 for k in ('closing','due')):raise ValueError('Cartão inválido.')
 for p in s.get('purchases',[]):
  if p.get('cardId') not in cards or type(p.get('amount')) is not int or p['amount']<=0 or type(p.get('parts')) is not int or not 1<=p['parts']<=48 or not isinstance(p.get('description'),str) or not isinstance(p.get('category'),str) or not re.fullmatch(r'\d{4}-\d{2}',str(p.get('firstMonth',''))) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(p.get('date',''))):raise ValueError('Compra inválida.')
 # Snapshot storage: business calculations remain in the client; never execute client data.
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,data):
  body=json.dumps(data).encode();self.send_response(status)
  origin=self.headers.get('Origin')
  if origin in ORIGINS:self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
  self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_OPTIONS(self):
  if self.headers.get('Origin') not in ORIGINS:return self.reply(403,{'error':'Origem não autorizada.'})
  self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods','GET, POST, PUT, OPTIONS');self.end_headers()
 def do_GET(self):self.dispatch()
 def do_POST(self):self.dispatch()
 def do_PUT(self):self.dispatch()
 def dispatch(self):
  try:
   if self.headers.get('Origin') and self.headers['Origin'] not in ORIGINS:return self.reply(403,{'error':'Origem não autorizada.'})
   data={}
   if self.command in ('POST','PUT'):
    size=int(self.headers.get('Content-Length','0'))
    if size<0 or size>LIMIT:return self.reply(413,{'error':'Arquivo maior que 2 MB.'})
    data=json.loads(self.rfile.read(size) or b'{}')
    if not isinstance(data,dict):raise ValueError('Objeto JSON esperado.')
   if self.path=='/health':return self.reply(200,{'status':'ok'})
   if self.path in ['/auth/register','/auth/login'] and self.command=='POST':
    with lock:
     ip=self.client_address[0];now=time.time();recent=[t for t in attempts.get(ip,[]) if now-t<60];attempts[ip]=recent
     if len(recent)>=10:return self.reply(429,{'error':'Muitas tentativas. Aguarde um minuto.'})
     recent.append(now)
    email=data.get('email','').strip().lower();password=data.get('password','')
    if not isinstance(password,str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 12<=len(password)<=128:raise ValueError('Informe email e senha de 12 a 128 caracteres.')
    with connect() as c:
     if self.path.endswith('register'):
      salt=secrets.token_bytes(16);user=secrets.token_hex(16)
      try:c.execute('INSERT INTO users VALUES(?,?,?,?)',(user,email,salt,password_hash(password,salt)))
      except sqlite3.IntegrityError:return self.reply(409,{'error':'Não foi possível cadastrar este email.'})
     else:
      row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
      hashed=password_hash(password,row['salt'] if row else b'0'*16)
      if not row or not hmac.compare_digest(hashed,row['password']):return self.reply(401,{'error':'Email ou senha inválidos.'})
      user=row['id']
     token=secrets.token_urlsafe(32);c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),));c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),user,int(time.time())+86400))
    return self.reply(200,{'token':token,'email':email})
   token=self.headers.get('Authorization','').removeprefix('Bearer ')
   with connect() as c:
    session=c.execute('SELECT * FROM sessions WHERE token=? AND expires>?',(digest(token),int(time.time()))).fetchone()
    if not session:return self.reply(401,{'error':'Entre novamente para continuar.'})
    user=session['user_id']
    if self.path=='/auth/logout' and self.command=='POST':c.execute('DELETE FROM sessions WHERE token=?',(digest(token),));return self.reply(200,{'ok':True})
    if self.path=='/state' and self.command=='GET':
     row=c.execute('SELECT * FROM states WHERE user_id=?',(user,)).fetchone();return self.reply(200,{'revision':row['revision'] if row else 0,'state':json.loads(row['payload']) if row else None})
    if self.path=='/state' and self.command=='PUT':
     state=data.get('state');validate_state(state);expected=data.get('revision')
     if type(expected) is not int or expected<0:raise ValueError('Revisão inválida.')
     c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT revision FROM states WHERE user_id=?',(user,)).fetchone();actual=row['revision'] if row else 0
     if expected!=actual:return self.reply(409,{'error':'Outro dispositivo alterou os dados. Baixe a versão do servidor antes de enviar.','revision':actual})
     c.execute('INSERT INTO states VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(user,actual+1,json.dumps(state)));c.commit();return self.reply(200,{'revision':actual+1})
   self.reply(404,{'error':'Rota não encontrada.'})
  except (ValueError,TypeError,AttributeError):self.reply(400,{'error':'Confira os campos e o formato dos dados.'})
  except Exception:self.reply(500,{'error':'Falha interna. Tente novamente.'})
if __name__=='__main__':
 initialize();address=os.environ.get('AURORA_HOST','127.0.0.1');port=int(os.environ.get('AURORA_PORT','8787'));print(f'Aurora API: {address}:{port}',flush=True);ThreadingHTTPServer((address,port),Handler).serve_forever()
