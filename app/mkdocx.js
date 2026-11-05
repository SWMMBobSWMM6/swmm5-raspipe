const fs=require('fs');const D=require('docx');
const {Document,Packer,Paragraph,TextRun,ImageRun,AlignmentType,LevelFormat,HeadingLevel,Footer,PageNumber,ExternalHyperlink,Table,TableRow,TableCell,WidthType,ShadingType,BorderStyle}=D;
const e=JSON.parse(fs.readFileSync(process.argv[2]));
const FONT='Arial',MONO='Courier New';
function runs(s,o={}){const out=[];const re=/(`[^`]+`|\*\*[^*]+\*\*)/g;let i=0,m;
  while((m=re.exec(s))){if(m.index>i)out.push(new TextRun({text:s.slice(i,m.index),...o}));const t=m[0];
    if(t[0]==='`')out.push(new TextRun({text:t.slice(1,-1),font:MONO,size:19,...o}));else out.push(new TextRun({text:t.slice(2,-2),bold:true,...o}));i=m.index+t.length;}
  if(i<s.length)out.push(new TextRun({text:s.slice(i),...o}));return out;}
let nol=0;const kids=[],cfg=[{reference:'bul',levels:[{level:0,format:LevelFormat.BULLET,text:'•',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:400,hanging:240}}}}]}];
kids.push(new Paragraph({heading:HeadingLevel.TITLE,children:[new TextRun(e.title)]}));
kids.push(new Paragraph({spacing:{after:80},children:[new TextRun({text:e.sub,color:'475569',size:24})]}));
kids.push(new Paragraph({spacing:{after:280},children:[new TextRun({text:'SWMM5 RASPIPE 1.2. November 2026.',color:'475569',size:20})]}));
for(const b of e.blocks){
  if(b.t==='h2')kids.push(new Paragraph({heading:HeadingLevel.HEADING_1,children:[new TextRun(b.x)]}));
  else if(b.t==='p')kids.push(new Paragraph({spacing:{after:140,line:300},children:runs(b.x)}));
  else if(b.t==='code')kids.push(new Paragraph({spacing:{before:60,after:160},indent:{left:240},shading:{type:D.ShadingType.CLEAR,fill:'F1F5F9'},children:b.x.split('\n').map((l,i)=>new TextRun({text:l,font:MONO,size:18,break:i?1:0}))}));
  else if(b.t==='fig'){const [w,h]=e.sizes[b.k],W=624,H=Math.round(W*h/w);
    kids.push(new Paragraph({keepNext:true,spacing:{before:160,after:60},alignment:AlignmentType.CENTER,children:[new ImageRun({type:'png',data:fs.readFileSync(`${e.d}/fig/${b.k}.png`),transformation:{width:W,height:H},altText:{title:b.k,description:b.x,name:b.k}})]}));
    kids.push(new Paragraph({spacing:{after:220},children:[new TextRun({text:b.x,italics:true,size:19,color:'475569'})]}));}
  else if(b.t==='ul'){for(let i=0;i<b.x.length;i++){const L=b.links&&b.links[i];
      const ch=(L&&L[1])?[new ExternalHyperlink({link:L[1],children:[new TextRun({text:L[0],style:'Hyperlink',color:'1D4ED8',underline:{}})]})]:runs(L?L[0]:b.x[i]);
      kids.push(new Paragraph({numbering:{reference:'bul',level:0},spacing:{after:80,line:290},children:ch}));}}
  else if(b.t==='table'){const bd={style:BorderStyle.SINGLE,size:4,color:'CBD5E1'},B={top:bd,bottom:bd,left:bd,right:bd};
    const cell=(t,w,h)=>new TableCell({width:{size:w,type:WidthType.DXA},borders:B,margins:{top:50,bottom:50,left:70,right:70},shading:h?{type:ShadingType.CLEAR,fill:'E2E8F0'}:undefined,children:[new Paragraph({spacing:{after:0,line:250},children:runs(String(t),{size:17,bold:h||undefined})})]});
    kids.push(new Table({width:{size:9360,type:WidthType.DXA},columnWidths:b.w,rows:[new TableRow({tableHeader:true,children:b.head.map((t,i)=>cell(t,b.w[i],true))}),...b.rows.map(r=>new TableRow({cantSplit:false,children:r.map((t,i)=>cell(t,b.w[i],false))}))]}));
    kids.push(new Paragraph({spacing:{after:160},children:[]}));}
  else if(b.t==='ol'){const ref='steps'+(++nol);cfg.push({reference:ref,levels:[{level:0,format:LevelFormat.DECIMAL,text:'%1.',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:400,hanging:300}}}}]});
    for(const x of b.x)kids.push(new Paragraph({numbering:{reference:ref,level:0},spacing:{after:80,line:290},children:runs(x)}));}
}
const doc=new Document({creator:'SWMM5 RASPIPE',title:e.title,description:e.sub,
  styles:{default:{document:{run:{font:FONT,size:21,color:'1F2937'}},
    title:{run:{font:FONT,size:44,bold:true,color:'1E3A5F'},paragraph:{spacing:{before:0,after:100},keepNext:true}},
    heading1:{run:{font:FONT,size:29,bold:true,color:'1E3A5F'},paragraph:{spacing:{before:320,after:120},keepNext:true}}}},
  numbering:{config:cfg},
  sections:[{properties:{page:{size:{width:12240,height:15840},margin:{top:1296,bottom:1224,left:1440,right:1440}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[new TextRun({text:'Page ',size:17,color:'64748B'}),new TextRun({children:[PageNumber.CURRENT],size:17,color:'64748B'})]})]})},children:kids}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(process.argv[3],b);console.log('docx',b.length);});
