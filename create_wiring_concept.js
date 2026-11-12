await eda.dmt_EditorControl.openDocument('bc806f309d128c37');
const blocks=[];
const wires=[];
async function text(s,x,y,size=10){return await eda.sch_PrimitiveText.create(x,y,s,0,'#172A3A','Arial',size,false,false,false,5);}
async function block(name,x,y,w,h,description){const o=await eda.sch_PrimitiveRectangle.create(x,y,w,h,0,0,'#365D7C',null,1);if(!o)throw Error('Block failed');await text(name,x+w/2,y-h/2+8,12);await text(description,x+w/2,y-h/2-12,8);blocks.push({name,x,y,w,h,description});}
async function wire(net,points){const o=await eda.sch_PrimitiveWire.create(points,net,'#246B58',1);if(!o)throw Error('Wire failed');wires.push({net,points});}
await text('SWITCH ROBOT / WIFI BRIDGE V0.1',490,90,18);
await text('WIRING CONCEPT ONLY - NO ELECTRICAL ERC OR PCB LINK',490,62,10);
await block('EXTERNAL ESP32',80,0,190,100,'Model / GPIO pins not confirmed');
await block('5V SUPPLY',80,-190,190,80,'J1 -> F1 -> +5V; C1/C2 to GND');
await block('SERVO',430,-190,190,80,'J3: GND / +5V / SIGNAL');
await block('U1 PhotoMOS',430,0,190,80,'KEY1 -> R1 470R -> LED1');
await block('U2 PhotoMOS',430,-95,190,80,'KEY2 -> R2 470R -> LED2');
await block('REMOTE KEY 1',770,0,190,80,'J4 across button contacts');
await block('REMOTE KEY 2',770,-95,190,80,'J5 across button contacts');
await wire('KEY1',[270,-25,430,-25]);
await wire('KEY2',[270,-70,350,-70,350,-120,430,-120]);
await wire('PWM',[270,-90,320,-90,320,-220,430,-220]);
await wire('+5V',[270,-245,430,-245]);
await wire('BTN1_A',[620,-25,770,-25]);
await wire('BTN1_B',[620,-50,770,-50]);
await wire('BTN2_A',[620,-120,770,-120]);
await wire('BTN2_B',[620,-145,770,-145]);
await text('R3 / R4: 100k GPIO pulldowns; R5: 220R PWM series; R6: 100k PWM pulldown',490,-305,10);
await text('MCU and servo supply share GND. PhotoMOS outputs remain isolated from GND.',490,-333,10);
await text('Use existing remote battery. Verify voltage, button topology and relay pinout before soldering.',490,-361,10);
await text('PCB: 60 x 40 mm; four M3 holes at (4,4), (56,4), (56,36), (4,36).',490,-389,10);
await eda.sch_Document.save();
await eda.dmt_EditorControl.zoomToAllPrimitives();
return {blocks,wires,source:await eda.sys_FileManager.getDocumentSource()};
