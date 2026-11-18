"""Checks the generated INFORM job with an offline arithmetic/control-flow model.
No DX200 kinematics, motion planner, PLC or hardware is simulated.
"""
from pathlib import Path
from fractions import Fraction
import ast,random,re,json,math
ROOT=Path(__file__).resolve().parent
PATH=ROOT/'OBLICZ_SZLIF_TROJNIKA.JBI'

def number(s,values):
 def run(n):
  if isinstance(n,ast.Expression):return run(n.body)
  if isinstance(n,ast.Constant):return Fraction(str(n.value))
  if isinstance(n,ast.Name):return Fraction(values.get(n.id,0))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -run(n.operand)
  if isinstance(n,ast.BinOp):
   a,b=run(n.left),run(n.right)
   if isinstance(n.op,ast.Add):return a+b
   if isinstance(n.op,ast.Sub):return a-b
   if isinstance(n.op,ast.Mult):return a*b
   if isinstance(n.op,ast.Div):return a/b
  raise ValueError(ast.dump(n))
 return run(ast.parse(s.removeprefix('EXPRESS').strip(),mode='eval'))

def execute(initial,rounding='truncate'):
 s=PATH.read_bytes().decode('cp1250').split('//INST',1)[1]
 lines=[l.strip() for l in s.splitlines() if l.strip() and not l.strip().startswith(('///',"'"))]
 values=dict(initial);points={};writes=[];outputs=[]
 quantize=int if rounding=='truncate' else round
 def val(s):return number(s,values)
 def cond(s):
  m=re.fullmatch(r'(\w+)(<=|>=|=|<|>)(-?\d+)',s);assert m,s
  a,b=values.get(m[1],0),int(m[3]);return {'=':a==b,'<':a<b,'>':a>b,'<=':a<=b,'>=':a>=b}[m[2]]
 def block(lo,hi):
  i=lo
  while i<hi:
   l=lines[i];op=l.split()[0]
   if op=='IFTHENEXP':
    j=i+1;depth=1
    while depth:
     if lines[j].startswith('IFTHENEXP '):depth+=1
     if lines[j]=='ENDIF':depth-=1
     j+=1
    if cond(l.split(' ',1)[1]):block(i+1,j-1)
    i=j;continue
   if op=='FOR':
    m=re.fullmatch(r'FOR (I\d{3}) START=\s*(\d+) TO (\d+) STEP=\s*(\d+)',l);assert m,l
    j=i+1
    while not lines[j].startswith('NEXT '):j+=1
    for k in range(int(m[2]),int(m[3])+1,int(m[4])):values[m[1]]=k;block(i+1,j)
    values[m[1]]=int(m[3])+int(m[4]);i=j+1;continue
   if op=='SWITCH':
    variable=l.split()[1];j=i+1
    while lines[j]!='ENDSWITCH':
     assert lines[j].startswith('CASE ');case=int(lines[j].split()[1]);k=j+1
     while lines[k]!='ENDSWITCH' and not lines[k].startswith('CASE '):k+=1
     if values.get(variable,0)==case:block(j+1,k)
     j=k
    i=j+1;continue
   if op=='SET':
    _,v,expr=l.split(maxsplit=2);values[v]=quantize(val(expr));writes.append(v)
   elif op in ['MUL','DIV','SUB','ADD']:
    _,v,operand=l.split(maxsplit=2);a,b=values[v],val(operand)
    result={'MUL':lambda:a*b,'DIV':lambda:a/b,'SUB':lambda:a-b,'ADD':lambda:a+b}[op]()
    values[v]=quantize(result);writes.append(v)
   elif op=='SETE':
    m=re.fullmatch(r'SETE (P\d{3}|P\[I\d{3}\]) (?:TL#\((\d+)\)|\((\d+)\) (D\d{3}))',l);assert m,l
    name=m[1]
    if '[' in name:name='P'+str(values[name[2:-1]]).zfill(3)
    points.setdefault(name,{})['tool' if m[2] else int(m[3])]=int(m[2]) if m[2] else values[m[4]]
   elif op=='DOUT':outputs.append(l)
   elif op=='PAUSE':raise ValueError('Program paused for invalid pass number or geometry')
   elif op=='JUMP':raise AssertionError('JUMP should only follow a pause in this job')
   elif op in ['RET','END']:return
   elif op=='NOP' or l.startswith('*'):pass
   else:raise ValueError(l)
   i+=1
 block(0,len(lines));return values,points,writes,outputs

def main():
 rng=random.Random(20261118);cases=0;table=[]
 for rounding in ['truncate','nearest']:
  for geometry in [(269,16)]+[(rng.randint(260,500),rng.randint(10,35)) for _ in range(20)]:
   outer,wall=geometry
   for reset in [0,1]:
    previous=-math.inf
    for lap in range(1,16):
     init={'I035':30,'I071':outer,'I074':wall,'I070':210,'I120':lap,'I072':rng.randint(-300,300),'I073':87,'I075':177,'D079':21000,'B030':reset,'I089':550,'D103':rng.randint(-5000,5000),'D104':rng.randint(-5000,5000),'D105':rng.randint(-5000,5000)}
     v,p,writes,outputs=execute(init,rounding)
     # Independent geometric expectation in millimetres: bore radius minus cutter radius,
     # with the remaining 3 mm clearance linearly decreasing over 14 intervals.
     expected=(outer/10-2*wall/10)/2-6-3*(15-lap)/14
     assert abs(v['D074']/1000-expected)<=0.00100001,(geometry,lap,v['D074'],expected)
     assert v['D074']>previous;previous=v['D074']
     assert 'I072' not in writes and 'I073' not in writes and 'I075' not in writes and 'D079' not in writes
     assert v['I072']==init['I072'] and v['I075']==177 and v['I073']==87
     for name in ['P010','P011','P012','P013']:
      q=p[name]
      assert q['tool']==17 and [q[e] for e in [4,5,6]]==[-1800000,0,900000]
      assert q[3]==19000+init['D105']
      radius=math.hypot(q[1]-init['D103'],q[2]-init['D104'])
      assert radius==v['D074']
     r=v['D074'];x,y=init['D103'],init['D104']
     assert (p['P010'][1],p['P010'][2])==(x+r,y)
     assert (p['P011'][1],p['P011'][2])==(x,y-r)
     assert (p['P012'][1],p['P012'][2])==(x-r,y)
     assert (p['P013'][1],p['P013'][2])==(x,y+r)
     assert v['B030']==0 and outputs==['DOUT OT#(6) OFF']
     if geometry==(269,16) and rounding=='truncate' and reset==0:
      table.append({'obieg':lap,'promien_osi_mm':v['D074']/1000,'odstep_krawedzi_od_scianki_mm':round(11.85-6-v['D074']/1000,3)})
     cases+=1
 rejected=0
 for lap,outer,wall in [(0,269,16),(16,269,16),(-1,269,16),(1,180,0),(1,200,15)]:
  try:execute({'I035':30,'I120':lap,'I071':outer,'I074':wall,'I089':550})
  except ValueError as e:
   assert 'paused' in str(e);rejected+=1
  else:raise AssertionError('Invalid parameters accepted')
 raw=PATH.read_bytes();assert raw.count(b'\n')==raw.count(b'\r\n')
 report={'model':'Arithmetic and control-flow subset; not DX200/PLC/kinematics validation','passing_geometry_cases':cases,'rejected_invalid_parameter_cases':rejected,'nominal_outer_diameter_mm':26.9,'nominal_wall_mm':1.6,'cutter_diameter_mm':12,'tool':17,'passes':15,'nominal_passes_truncation_model':table}
 (ROOT/'wyniki_sprawdzenia.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
