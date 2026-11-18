"""Offline model of the generated INFORM jobs, not a DX200 or PLC simulator."""
from pathlib import Path
from fractions import Fraction
import ast,copy,json,math,random,re
ROOT=Path(__file__).resolve().parent
JOBS=['OBLICZ_SZLIF_TROJNIKA','SZLIF_SPAWU_TROJNIKA']
class Paused(Exception):pass

def expression(source,values):
 def calc(n):
  if isinstance(n,ast.Expression):return calc(n.body)
  if isinstance(n,ast.Constant):return Fraction(str(n.value))
  if isinstance(n,ast.Name):return Fraction(values.get(n.id,0))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -calc(n.operand)
  if isinstance(n,ast.BinOp):
   a,b=calc(n.left),calc(n.right)
   if isinstance(n.op,ast.Add):return a+b
   if isinstance(n.op,ast.Sub):return a-b
   if isinstance(n.op,ast.Mult):return a*b
   if isinstance(n.op,ast.Div):return a/b
  raise ValueError(ast.dump(n))
 return calc(ast.parse(source.removeprefix('EXPRESS').strip(),mode='eval'))

def compile_job(name):
 raw=(ROOT/(name+'.JBI')).read_bytes()
 assert raw.count(b'\n')==raw.count(b'\r\n'),name
 source=raw.decode('cp1250').split('//INST',1)[1]
 lines=[l.strip() for l in source.splitlines() if l.strip() and not l.strip().startswith(('///',"'"))]
 mapping={};stack=[];labels={};switches={}
 for i,l in enumerate(lines):
  op=l.split()[0]
  if l.startswith('*'):labels[l]=i
  if op in ['IFTHENEXP','FOR','SWITCH']:stack.append([op,i,[]])
  elif op in ['ELSE','CASE']:stack[-1][2].append(i)
  elif op in ['ENDIF','NEXT','ENDSWITCH']:
   typ,start,branches=stack.pop()
   assert (typ,op) in [('IFTHENEXP','ENDIF'),('FOR','NEXT'),('SWITCH','ENDSWITCH')]
   mapping[start]=(i,branches)
   if typ=='IFTHENEXP':
    for b in branches:mapping[b]=(i,[])
   elif typ=='FOR':mapping[i]=(start,[])
   else:
    switches[start]=[(int(lines[b].split()[1]),b) for b in branches]
    for b in branches:mapping[b]=(i,[])
 assert not stack
 return lines,mapping,labels,switches

class Model:
 def __init__(self,values,rounding='truncate',hook=None):
  self.values=copy.deepcopy(values);self.points={};self.trace=[];self.writes=[];self.hook=hook
  self.rounding=rounding;self.steps=0;self.jobs={n:compile_job(n) for n in JOBS}
 def get(self,k):return self.values.get(k,0)
 def store(self,k,value):
  value=int(value) if self.rounding=='truncate' else round(value)
  if k.startswith('I'):value=(value+32768)%65536-32768
  if k.startswith('B'):value%=256
  if k.startswith('D'):value=(value+2147483648)%4294967296-2147483648
  self.values[k]=value;self.writes.append(k)
 def value(self,s):return expression(s,self.values)
 def condition(self,s):
  m=re.fullmatch(r'(\w+)(<=|>=|=|<|>)(\w+|-?\d+)',s);assert m,s
  a,b=self.value(m[1]),self.value(m[3]);return {'=':a==b,'<':a<b,'>':a>b,'<=':a<=b,'>=':a>=b}[m[2]]
 def run(self,name):
  lines,mapping,labels,switches=self.jobs[name];pc=0
  if self.hook:self.hook(self,name,'enter')
  while pc<len(lines):
   self.steps+=1
   if self.steps>2000000:raise AssertionError('Model instruction limit: possible nonterminating loop')
   s=lines[pc];op=s.split()[0]
   if op=='IFTHENEXP':
    end,branches=mapping[pc]
    if self.condition(s.split(' ',1)[1]):pc+=1
    else:pc=branches[0]+1 if branches else end+1
    continue
   if op=='ELSE':pc=mapping[pc][0]+1;continue
   if op=='FOR':
    m=re.fullmatch(r'FOR (I\d{3}) START=\s*(-?\d+) TO (-?\d+) STEP=\s*(-?\d+)',s);assert m,s
    self.store(m[1],int(m[2]));pc+=1;continue
   if op=='NEXT':
    start=mapping[pc][0];m=re.fullmatch(r'FOR (I\d{3}) START=\s*(-?\d+) TO (-?\d+) STEP=\s*(-?\d+)',lines[start])
    self.store(m[1],self.get(m[1])+int(m[4]));pc=start+1 if self.get(m[1])<=int(m[3]) else pc+1;continue
   if op=='SWITCH':
    selected=next((b for v,b in switches[pc] if v==self.get(s.split()[1])),None)
    pc=selected+1 if selected is not None else mapping[pc][0]+1;continue
   if op=='CASE':pc=mapping[pc][0]+1;continue
   if op=='SET':
    _,v,expr=s.split(maxsplit=2);self.store(v,self.value(expr))
   elif op in ['MUL','DIV','SUB','ADD']:
    _,v,operand=s.split(maxsplit=2);a,b=self.get(v),self.value(operand)
    value={'MUL':lambda:a*b,'DIV':lambda:a/b,'SUB':lambda:a-b,'ADD':lambda:a+b}[op]()
    self.store(v,value)
   elif op=='SETE':
    m=re.fullmatch(r'SETE (P\d{3}|P\[I\d{3}\]) (?:TL#\((\d+)\)|\((\d+)\) (D\d{3}))',s);assert m,s
    key=m[1]
    if '[' in key:key='P'+str(self.get(key[2:-1])).zfill(3)
    self.points.setdefault(key,{})['tool' if m[2] else int(m[3])]=int(m[2]) if m[2] else self.get(m[4])
   elif op=='CALL':self.run(s.split('JOB:',1)[1])
   elif op=='JUMP':pc=labels[s.split()[1]];continue
   elif op=='PAUSE':raise Paused((name,self.get('I120')))
   elif op=='DOUT':self.trace.append({'kind':'DOUT','instruction':s})
   elif op in ['MOVL','MOVC']:
    m=re.fullmatch(r'(MOVL|MOVC) (P\d{3}) V=(I\d{3}) PL=(\d+)',s);assert m,s
    event={'kind':'MOVE','motion':op,'point':m[2],'position':copy.deepcopy(self.points[m[2]]),'speed':self.get(m[3]),'pl':int(m[4]),'pass':self.get('I120'),'radius':self.get('D074'),'limit':self.get('D120'),'radial_step':self.get('D121')}
    self.trace.append(event)
    if self.hook:self.hook(self,name,'move')
   elif op in ['RET','END']:
    if self.hook:self.hook(self,name,'leave')
    return
   elif op in ['NOP','ENDIF','ENDSWITCH'] or s.startswith('*'):pass
   else:raise ValueError((name,s))
   pc+=1
  if self.hook:self.hook(self,name,'leave')

def initial(step=100,outer=269,wall=16,cutter=120):
 return {'I035':30,'I070':cutter,'I071':outer,'I072':1,'I073':step,'I074':wall,'I075':177,'I089':550,'I120':16,'B030':1,'D074':999999,'D120':-1,'D121':-500,'D103':-1000,'D104':1300,'D105':5000}

def check_cycle(model,outer,wall,cutter,step):
 limit=(outer-2*wall-cutter)*50
 assert limit>=3000
 radial=step//2;count=math.ceil((limit-3000)/radial)+1
 model.run('SZLIF_SPAWU_TROJNIKA')
 moves=[e for e in model.trace if e['kind']=='MOVE']
 assert len(moves)==count*6,(len(moves),count)
 for index in range(count):
  radius=min(3000+index*radial,limit);events=moves[index*6:(index+1)*6]
  assert [e['motion'] for e in events]==['MOVL']+['MOVC']*5
  assert [e['point'] for e in events]==['P010','P010','P013','P012','P011','P010']
  for e in events:
   assert e['radius']==radius and e['limit']==limit and e['radial_step']==radial
   assert e['pass']==index+1 and e['speed']==200
   p=e['position'];x,y,z=model.get('D103'),model.get('D104'),19000+model.get('D105')
   assert p['tool']==17 and [p[k] for k in [4,5,6]]==[-1800000,0,900000]
   assert p[3]==z and math.hypot(p[1]-x,p[2]-y)==radius
  assert events[0]['pl']==events[-1]['pl']==0
 assert moves[-1]['radius']==limit
 assert sum(1 for e in moves if e['motion']=='MOVC' and e['point']=='P010' and e['pl']==0 and e['radius']==limit)==1
 assert model.get('D074')==model.get('D120')==limit and model.get('I120')==count
 assert not any(v in model.writes for v in ['I070','I071','I072','I073','I074','I075'])
 return count,moves

def main():
 randomizer=random.Random(20261118);cases=0;nominal=[]
 geometries=[(269,16,120),(220,20,120),(269,20,120),(300,10,120)]
 for rounding in ['truncate','nearest']:
  for outer,wall,cutter in geometries:
   for step in [2,10,50,100,200,400,1000,2000,5700,6000,32766]:
    m=Model(initial(step,outer,wall,cutter),rounding);count,moves=check_cycle(m,outer,wall,cutter,step);cases+=1
    if rounding=='truncate' and (outer,wall,cutter)==(269,16,120):nominal.append({'I073':step,'diameter_step_mm':step/1000,'passes':count,'first_axis_radius_mm':moves[0]['radius']/1000,'last_axis_radius_mm':moves[-1]['radius']/1000})
  for _ in range(20):
   outer=randomizer.randint(250,450);wall=randomizer.randint(10,30);step=2*randomizer.randint(1,1000)
   m=Model(initial(step,outer,wall),rounding);check_cycle(m,outer,wall,120,step);cases+=1
 # Inputs are latched on first pass; later operator edits apply to the next piece.
 changed=False
 def hook(m,name,stage):
  nonlocal changed
  if stage=='move' and not changed:
   changed=True;m.values['I073']=400;m.values['I071']=300;m.values['I074']=20
 m=Model(initial(100),hook=hook);check_cycle(m,269,16,120,100)
 m.hook=None;m.trace=[];count,_=check_cycle(m,300,20,120,400);cases+=2
 # Repeating the calculation at the same pass does not advance the cutter again.
 for lap in [2,10,20]:
  m=Model(initial(100));m.values['I120']=1;m.run('OBLICZ_SZLIF_TROJNIKA')
  m.values['I120']=lap;m.run('OBLICZ_SZLIF_TROJNIKA');first=(m.get('D074'),copy.deepcopy(m.points))
  m.run('OBLICZ_SZLIF_TROJNIKA');assert first==(m.get('D074'),m.points);cases+=1
 bad=[]
 for step in [0,-100,1,3,99,32767]:
  v=initial(step);bad.append(v)
 for change in [{'I071':219,'I074':20},{'I070':0},{'I074':-1},{'I035':20}]:
  v=initial();v.update(change);bad.append(v)
 for v in bad:
  m=Model(v)
  try:m.run('SZLIF_SPAWU_TROJNIKA')
  except Paused:assert not any(e['kind']=='MOVE' for e in m.trace)
  else:raise AssertionError(('Invalid input accepted',v))
 source=(ROOT/'OBLICZ_SZLIF_TROJNIKA.JBI').read_bytes().decode('cp1250')
 assert 'SET I073' not in source and 'I072' not in source and 'I075' not in source
 result={'model':'Arithmetic/control flow only; no DX200, PLC, motion interpolation or collision simulation','passing_cycle_and_replay_cases':cases,'rejected_parameter_cases':len(bad),'one_full_final_circle_verified':True,'first_move_to_axis_radius_3mm_verified':True,'diameter_increment_is_I073_and_radius_increment_half_verified':True,'step_and_dimensions_latched_for_next_piece_verified':True,'nominal_geometry':{'outer_mm':26.9,'wall_mm':1.6,'cutter_mm':12,'D120_axis_radius_mm':5.85},'nominal_examples':nominal}
 (ROOT/'wyniki_sprawdzenia.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
