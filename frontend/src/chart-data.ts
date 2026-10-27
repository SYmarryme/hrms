export interface CountPoint {id?:string;name:string;count:number}
export interface MonthPoint {month:string;amount:string}
export function numericTicks(max:number,whole=false):number[]{
 if(!Number.isFinite(max)||max<0)throw new Error('统计数据暂不可用，请重新查询');
 if(max===0)return [0,1];
 const raw=max/4,power=10**Math.floor(Math.log10(raw)),fraction=raw/power;
 let step=(fraction<=1?1:fraction<=2?2:fraction<=5?5:10)*power;if(whole)step=Math.max(1,Math.ceil(step));
 const count=Math.ceil(max/step);return Array.from({length:count+1},(_,i)=>Number((i*step).toPrecision(12)));
}
export const integerTicks=(max:number)=>numericTicks(max,true);
export function labelLines(value:string,size=14):string[]{const chars=Array.from(value);return Array.from({length:Math.ceil(chars.length/size)||1},(_,i)=>chars.slice(i*size,(i+1)*size).join(''));}
export function gradeColor(name:string):string{
 if(name==='G1')return '#1464f4';if(name==='其他')return '#94a3b8';
 let hash=2166136261;for(const char of name)hash=Math.imul(hash^char.codePointAt(0)!,16777619)>>>0;
 return `hsl(${hash%360} 64% ${48+(hash%3)*5}%)`;
}
export function gradeShares(rows:CountPoint[]){
 if(rows.some(row=>!Number.isSafeInteger(row.count)||row.count<0))throw new Error('职级统计暂不可用，请重新查询');
 const total=rows.reduce((sum,row)=>sum+row.count,0);if(!total)return [];
 const shares=rows.map(row=>({...row,tenths:Math.floor(row.count*1000/total),remainder:row.count*1000/total%1}));
 const order=shares.map((_,i)=>i).sort((a,b)=>shares[b].remainder-shares[a].remainder||shares[a].name.localeCompare(shares[b].name));
 for(let left=1000-shares.reduce((sum,row)=>sum+row.tenths,0),i=0;left>0;left--,i++)shares[order[i%order.length]].tenths++;
 return shares.map(row=>({...row,percent:(row.tenths/10).toFixed(1),color:gradeColor(row.name)}));
}
export function moneyLabel(value:string):string{
 if(!/^\d+(?:\.\d{1,2})?$/.test(value))throw new Error('工资统计暂不可用，请重新查询');
 const [integer,decimal='']=value.split('.');return integer.replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+decimal.padEnd(2,'0');
}
export function orderedTrend(items:MonthPoint[]):MonthPoint[]{
 const sorted=[...items].sort((a,b)=>a.month.localeCompare(b.month));
 sorted.forEach((row,i)=>{if(!/^(?:19|20)\d\d-(0[1-9]|1[0-2])$/.test(row.month))throw new Error('月份统计暂不可用');moneyLabel(row.amount);
 if(i){const index=(month:string)=>Number(month.slice(0,4))*12+Number(month.slice(5));if(index(row.month)-index(sorted[i-1].month)!==1)throw new Error('工资统计数据不完整，请重新查询');}});
 return sorted;
}
