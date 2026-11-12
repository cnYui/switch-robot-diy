const EPCB_LayerId={TOP:1,BOTTOM:2,TOP_SILKSCREEN:3,BOARD_OUTLINE:11,MULTI:12};
const EPCB_PrimitivePadShapeType={ELLIPSE:'ELLIPSE',RECTANGLE:'RECT'};
const EPCB_PrimitivePadHoleType={ROUND:'ROUND'};
const EPCB_PrimitiveStringAlignMode={CENTER:5};
const mm=x=>x/0.0254;
const pads=[];
const lines=[];
const texts=[];
async function text(s,x,y,size=1.1){const o=await eda.pcb_PrimitiveString.create(EPCB_LayerId.TOP_SILKSCREEN,mm(x),mm(y),s,'Arial',mm(size),mm(.15),EPCB_PrimitiveStringAlignMode.CENTER,0,false,0,false,false);if(!o)throw Error('Text failed '+s);texts.push(s);}
async function line(net,layer,x1,y1,x2,y2,w=.25){const o=await eda.pcb_PrimitivePolyline.create(net,layer,eda.pcb_MathPolygon.createPolygon([mm(x1),mm(y1),'L',mm(x2),mm(y2)]),mm(w),false);if(!o)throw Error('Line failed');lines.push({net,layer,x1,y1,x2,y2,w});}
async function pad(ref,n,x,y,net,hole=.9,diam=1.8){const o=await eda.pcb_PrimitivePad.create(EPCB_LayerId.MULTI,String(n),mm(x),mm(y),0,[EPCB_PrimitivePadShapeType.ELLIPSE,mm(diam),mm(diam)],net,[EPCB_PrimitivePadHoleType.ROUND,mm(hole)],0,0,0,true);if(!o)throw Error('Pad failed '+ref);pads.push({ref,pin:n,x,y,net,hole,diam});}
async function resistor(ref,x,y,net1,net2,value,vertical=false){await pad(ref,1,x,y,net1,.8,1.7);await pad(ref,2,x+(vertical?0:7.62),y+(vertical?-7.62:0),net2,.8,1.7);await text(ref+' '+value,x+(vertical?2.6:3.81),y+(vertical?-3.8:1.8),.95);}
async function header(ref,x,y,nets,horizontal=false){for(let i=0;i<nets.length;i++)await pad(ref,i+1,x+(horizontal?2.54*i:0),y+(horizontal?0:2.54*i),nets[i],1,1.9);}
async function ssr(ref,x,y,netA,netB,led){await pad(ref,1,x,y,led);await pad(ref,2,x,y+2.54,'GND');await pad(ref,3,x+7.62,y+2.54,netB);await pad(ref,4,x+7.62,y,netA);for(const [a,b,c,d] of [[x+1,y-1,x+6.62,y-1],[x+6.62,y-1,x+6.62,y+3.54],[x+6.62,y+3.54,x+1,y+3.54],[x+1,y+3.54,x+1,y-1]])await line('',EPCB_LayerId.TOP_SILKSCREEN,a,b,c,d,.15);await text(ref+' AQY212EH',x+3.81,y+5.2,.85);await text('1',x-1.5,y,.85);}

for(const [x,y]of [[4,4],[56,4],[56,36],[4,36]]){const o=await eda.pcb_PrimitivePad.create(EPCB_LayerId.MULTI,'',mm(x),mm(y),0,[EPCB_PrimitivePadShapeType.ELLIPSE,mm(3.2),mm(3.2)],'',[EPCB_PrimitivePadHoleType.ROUND,mm(3.2)],0,0,0,false);if(!o)throw Error('Mount hole failed');}
await header('J1',8,8,['VIN5','GND']);await text('J1 5V / GND',9,5.7,.9);
await pad('F1',1,15,8,'VIN5');await pad('F1',2,20.08,8,'+5V');await text('F1 PPTC TBD',17.5,5.6,.85);
await pad('C1',1,27,8,'+5V');await pad('C1',2,32,8,'GND');await text('C1 470uF + -',29.5,5.6,.85);
await pad('C2',1,27,12.5,'+5V');await pad('C2',2,29.54,12.5,'GND');await text('C2 100n',28,10.7,.8);
await header('J3',8,22,['GND','+5V','SERVO']);await text('J3 SERVO',8,19.3,.9);await text('G / 5V / S',8,29.5,.85);
await header('J2',10,34,['GND','PWM','KEY1','KEY2','AUX'],true);await text('J2 MCU: G P K1 K2 AUX',15,37,.9);
await resistor('R1',28,23.8,'KEY1','LED1','470',true);
await resistor('R2',28,34,'KEY2','LED2','470',true);
await resistor('R3',15,17,'KEY1','GND','100k');
await resistor('R4',15,20.5,'KEY2','GND','100k');
await resistor('R5',15,25,'SERVO','PWM','220');
await resistor('R6',15,29,'PWM','GND','100k');
await ssr('U1',35,16,'BTN1_A','BTN1_B','LED1');
await ssr('U2',35,27,'BTN2_A','BTN2_B','LED2');
await header('J4',52,16,['BTN1_A','BTN1_B']);await text('J4 KEY1',52,13.3,.9);
await header('J5',52,27,['BTN2_A','BTN2_B']);await text('J5 KEY2',52,24.3,.9);
await line('VIN5',EPCB_LayerId.TOP,8,8,15,8,1);
await line('+5V',EPCB_LayerId.TOP,20.08,8,27,8,1);
await line('+5V',EPCB_LayerId.TOP,27,8,27,12.5,.8);
await line('+5V',EPCB_LayerId.TOP,20.08,8,20.08,10.5,1);
await line('+5V',EPCB_LayerId.TOP,20.08,10.5,11,10.5,1);
await line('+5V',EPCB_LayerId.TOP,11,10.5,11,19.58,1);
await line('+5V',EPCB_LayerId.TOP,11,19.58,11,24.54,1);
await line('+5V',EPCB_LayerId.TOP,11,24.54,8,24.54,1);
await line('SERVO',EPCB_LayerId.TOP,8,27.08,12.92,27.08,.3);
await line('SERVO',EPCB_LayerId.TOP,12.92,27.08,15,25,.3);
await line('LED1',EPCB_LayerId.TOP,28,16.18,35,16,.3);
await line('LED2',EPCB_LayerId.TOP,28,26.38,35,27,.3);
for(const [y,s]of [[16,'1'],[27,'2']]){await line('BTN'+s+'_A',EPCB_LayerId.TOP,42.62,y,52,y,.3);await line('BTN'+s+'_B',EPCB_LayerId.TOP,42.62,y+2.54,52,y+2.54,.3);}
await text('SWITCH BRIDGE V0.1',42,7,1);
await text('LAYOUT DRAFT - NOT FOR FAB',40,38,.85);
await eda.pcb_Document.save();
await eda.dmt_EditorControl.zoomToAllPrimitives();
return {pads,lines,texts,source:await eda.sys_FileManager.getDocumentSource(),status:'PLACEMENT_DRAFT_PARTIAL_ROUTING'};
